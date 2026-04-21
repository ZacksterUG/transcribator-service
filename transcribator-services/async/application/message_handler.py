import datetime
import logging
from datetime import timezone

from .file_manager import FileManager
from message_queue.abstractions.message_queue import IMessageQueue
from .audio_processor import AudioProcessor
from .response_builder import ResponseBuilder
from .temp_file_manager import TempFileManager
from .utils import *
from .classes import Result
from database.dictionary_db.database import DictionaryDatabase

MAX_MESSAGE_SIZE_BYTES = 1024 * 1024
MAX_ALLOWED_FILES = 50  # Жёсткий лимит для продакшена

class MessageHandler:
    """
    Handles incoming messages from the queue.
    """
    
    def __init__(
        self,
        file_manager: FileManager,
        audio_processor: AudioProcessor,
        response_builder: ResponseBuilder,
        temp_file_manager: TempFileManager,
        dict_db: DictionaryDatabase,
        logger: Optional[logging.Logger] = None
    ):
        self.file_manager = file_manager
        self.audio_processor = audio_processor
        self.response_builder = response_builder
        self.temp_file_manager = temp_file_manager
        self.dict_db = dict_db
        self.logger = logger or logging.getLogger(__name__)

    def _extract_request_data(self, msg):
        """
        Extracts request data from the message.
        
        Args:
            msg: Incoming message
            
        Returns:
            Request data bytes
        """
        if hasattr(msg, 'data'):
            return msg.data
        return msg

    def _parse_request(self, request_data: bytes):
        """
        Parses the request data.
        
        Args:
            request_data: Raw request data
            
        Returns:
            Parsed request object
            
        Raises:
            RequestParsingError: If parsing fails
        """
        try:
            return request_from_binary(request_data)
        except ValueError as e:
            job_id = extract_job_id_from_invalid_request(request_data)
            raise RequestParsingError(str(e), job_id)

    async def handle_message(self, msg, queue: IMessageQueue):
        """
        Handles an incoming message with idempotency guarantees.
        ✅ Job помечается 'done' ТОЛЬКО при успешном завершении обработки.
        """
        job_id = "unknown"
        request_data = self._extract_request_data(msg)
        response_json = ""
        parent_dir = ""
        job_completed_successfully = False  # ✅ Флаг успешного завершения
        lock_ctx = None

        # --- 1-2. Валидация (без изменений) ---
        if len(request_data) > MAX_MESSAGE_SIZE_BYTES:
            job_id = extract_job_id_from_invalid_request(request_data) or "unknown"
            error_msg = f"Request too large: {len(request_data)} bytes"
            self.logger.error(f"❌ {error_msg} (job_id={job_id})")
            await self.response_builder.send_error_response(job_id, error_msg)
            return  # ✅ Валидационные ошибки — это "успешная" обработка (сообщение не нужно возвращать)

        try:
            temp_json = json.loads(request_data.decode('utf-8'))
            job_id = temp_json.get('job_id', 'unknown')
            if temp_json.get('input_type') == 'file_list':
                file_list = temp_json.get('audio_source', {}).get('file_list', [])
                if len(file_list) > MAX_ALLOWED_FILES:
                    error_msg = f"Too many files: {len(file_list)} > {MAX_ALLOWED_FILES}"
                    self.logger.error(f"❌ {error_msg} (job_id={job_id})")
                    await self.response_builder.send_error_response(job_id, error_msg)
                    return
        except Exception:
            pass

        if job_id == 'unknown':
            error_msg = "Couldn't acquire job_id from request"
            self.logger.error(f"❌ {error_msg}")
            await self.response_builder.send_error_response(job_id, error_msg)
            return

        # --- 3. Проверка на уже обработанный джоб ---
        lock_key = f"async-jobs:{job_id}"

        if self.dict_db.get(lock_key) == "done":
            self.logger.info(f"✅ Job {job_id} already processed (status=done), skipping")
            return

        # --- 4. Захват блокировки ---
        lock_ctx = self.dict_db.rwlock(lock_key, ttl=15)
        if lock_ctx is None or not lock_ctx.acquired:
            self.logger.warning(f"⚠️ Job {job_id} is already locked by another worker")
            return

        # --- 5. Фоновая задача продления TTL ---
        stop_extension = asyncio.Event()

        async def extend_lock_periodically():
            while not stop_extension.is_set():
                try:
                    await asyncio.sleep(5)
                    if stop_extension.is_set():
                        break
                    if not lock_ctx.extend_ttl(15):
                        self.logger.warning(f"⚠️ Lock extension failed for {job_id}")
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.warning(f"⚠️ Error extending lock for {job_id}: {e}")

        extension_task = asyncio.create_task(extend_lock_periodically())

        try:
            with lock_ctx:
                # Double-check
                if self.dict_db.get(lock_key) == "done":
                    self.logger.info(f"✅ Job {job_id} marked done by another worker")
                    return

                self.logger.info(f"📥 Processing message (job_id={job_id})")

                async def _publish_ack():
                    try:
                        ack_payload = json.dumps({
                            "job_id": job_id,
                            "status": "in_progress",
                            "completed_at": datetime.datetime.now(timezone.utc).isoformat(),
                            "error_message": ""
                        }, separators=(',', ':')).encode('utf-8')

                        await queue.publish(self.response_builder.response_topic, ack_payload)
                    except Exception as e:
                        self.logger.error(f"❌ Failed to publish ACK: {e}")

                asyncio.create_task(_publish_ack())

                try:
                    # --- 6. Основная обработка ---
                    request = self._parse_request(request_data)
                    job_id = request.job_id
                    parent_dir = request.audio_source.get_parent_dir()

                    await self.temp_file_manager.cleanup_old_temp_dirs()
                    job_temp_dir = self.temp_file_manager.prepare_job_directory(job_id)
                    local_paths, download_errors = await self.file_manager.download_audio_files(request, job_temp_dir)
                    
                    ctx = {
                        'job_id': job_id,
                        'logger': self.logger,
                    }
                    results = await self.audio_processor.process_audio_files(local_paths, request, ctx=ctx)

                    for error in download_errors:
                        results.append(Result(segments=[], error=error))

                    response = self.response_builder.build_response(job_id, results, download_errors)
                    response_bytes = serialize_response(response)
                    response_json = response_bytes.decode('utf-8')

                    await queue.publish(self.response_builder.response_topic, response_bytes)

                    # ✅ Помечаем флаг успешного завершения ТОЛЬКО после публикации ответа
                    job_completed_successfully = True

                except RequestParsingError as e:
                    job_id = e.job_id
                    self.logger.error(f"❌ Parsing error for job {job_id}: {e.message}")
                    error_response = self.response_builder.build_error_response(job_id, e.message)
                    response_bytes = serialize_response(error_response)
                    response_json = response_bytes.decode('utf-8')
                    await self.response_builder.send_error_response(job_id, e.message)
                    # ✅ Валидационная ошибка — считаем "успешной" обработкой (сообщение не возвращаем)
                    job_completed_successfully = True

                except Exception as e:
                    self.logger.error(f"❌ Critical error for job {job_id}: {e}", exc_info=True)
                    error_response = self.response_builder.build_error_response(job_id, f"Critical error: {str(e)}")
                    response_bytes = serialize_response(error_response)
                    response_json = response_bytes.decode('utf-8')
                    await self.response_builder.send_error_response(job_id, str(e))
                    # ❌ Критическая ошибка — НЕ помечаем как завершённую, пусть вернётся в очередь
                    job_completed_successfully = False
                    raise  # ✅ Пробрасываем для nak() в NatsQueue

                finally:
                    # ✅ Помечаем 'done' ТОЛЬКО если задача действительно завершена
                    if job_completed_successfully:
                        self.dict_db.set(lock_key, "done", ttl=3600)
                        self.logger.info(f"🔒 Job {job_id} marked as done (completed successfully)")
                    else:
                        self.logger.warning(f"⚠️ Job {job_id} NOT marked as done (incomplete, will redeliver)")

        finally:
            # ✅ Остановка задачи продления TTL
            stop_extension.set()
            if extension_task and not extension_task.done():
                extension_task.cancel()
                try:
                    await extension_task
                except asyncio.CancelledError:
                    pass
            # ✅ LockContext.__exit__ освободит блокировку

        # --- 7. Загрузка result.json (вне блокировки) ---
        if job_completed_successfully and response_json:
            try:
                remote_path = os.path.join(parent_dir, "result.json").replace("\\", "/")
                await self.file_manager.upload_result_json(response_json, remote_path)
                self.logger.info(f"☁️ Uploaded result.json to {remote_path}")
            except Exception as save_err:
                self.logger.warning(f"⚠️ Failed to upload result.json for job {job_id}: {save_err}", exc_info=True)
                # ❌ Не помечаем как failed — результат уже отправлен в топик