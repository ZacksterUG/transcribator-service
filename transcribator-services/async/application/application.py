import asyncio
from contextlib import asynccontextmanager
import json
import logging
import os
import datetime
import signal
from typing import Set
from .transcribation_model.model import IModel
from .transcribation_model.request import TranscriptionRequest
from .message_queue.abstractions.message_queue import IMessageQueue
import fsspec
from .utils import *
from .classes import *

MAX_MESSAGE_SIZE_BYTES = 1024 * 1024 
DOWNLOAD_TIMEOUT = 300  
EXTRACT_TIMEOUT = 300     
TRANSCRIPTION_TIMEOUT = 1800 
CLEANUP_TIMEOUT = 60  
SHUTDOWN_TIMEOUT = 10 

class JobProcessor:
    def __init__(self, model: IModel, storage: fsspec.AbstractFileSystem, temp_dir: str, logger: logging.Logger):
        self.model = model
        self.storage = storage
        self.temp_dir = temp_dir
        self.logger = logger

    async def process_job(self, request: Request) -> Response:
        # Вся логика обработки: загрузка, транскрибация, построение ответа
        pass

class MessageHandler:
    def __init__(self, job_processor: JobProcessor, queue: IMessageQueue, 
                 response_topic: str, logger: logging.Logger):
        self.job_processor = job_processor
        self.queue = queue
        self.response_topic = response_topic
        self.logger = logger

    async def handle_message(self, msg) -> None:
        # Парсинг, валидация, вызов job_processor, отправка ответа
        pass

class LifecycleManager:
    def __init__(self, queue: IMessageQueue, topic: str, 
                 message_handler: MessageHandler, logger: logging.Logger):
        self.queue = queue
        self.topic = topic
        self.message_handler = message_handler
        self.logger = logger
        self._shutdown_event = asyncio.Event()
        self._active_tasks = set()

    async def start(self) -> None:
        # Подписка, graceful shutdown, управление задачами
        pass

class HealthChecker:
    def __init__(self, model: IModel, storage: fsspec.AbstractFileSystem, 
                 queue: IMessageQueue, logger: logging.Logger):
        self.model = model
        self.storage = storage
        self.queue = queue
        self.logger = logger

    async def check(self) -> bool:
        # Проверка всех компонентов
        pass

class Application:
    def __init__(self, config: AppConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.components = self._build_components()

    def _build_components(self) -> dict:
        # Создание всех зависимостей
        model = ModelFactory.create(...)
        storage = StorageFactory.create(...)
        queue = QueueFactory.create(...)
        
        job_processor = JobProcessor(model, storage, self.config.temp_dir, self.logger)
        message_handler = MessageHandler(job_processor, queue, self.config.response_topic, self.logger)
        health_checker = HealthChecker(model, storage, queue, self.logger)
        lifecycle_manager = LifecycleManager(queue, self.config.request_topic, message_handler, self.logger)
        
        return {
            'job_processor': job_processor,
            'message_handler': message_handler,
            'health_checker': health_checker,
            'lifecycle_manager': lifecycle_manager
        }

    async def run(self) -> None:
        if not await self.components['health_checker'].check():
            raise RuntimeError("Health check failed")
        
        await self.components['lifecycle_manager'].start()

class App:
    def __init__(
        self,
        model: IModel,
        queue: IMessageQueue,
        storage: fsspec.AbstractFileSystem,
        request_topic: str,
        response_topic: str,
        temp_dir: str = './temp',
        logger: Optional[logging.Logger] = None,
        debug: bool = False
    ):
        self.model = model
        self.queue = queue
        self.storage = storage
        self.request_topic = request_topic
        self.response_topic = response_topic
        self.temp_dir = temp_dir
        self.logger = logger or logging.getLogger("transcriber")
        self.debug = debug
        
        # Для graceful shutdown
        self._shutdown_event = asyncio.Event()
        self._active_tasks: Set[asyncio.Task] = set()

    async def health_check(self) -> bool:
        self.logger.info('healthchecking modules...')
        try:
            if not self.model.health_check():
                raise Exception("Model health check failed")
            self.storage.info('')
            if hasattr(self.queue, 'health_check'):
                await self.queue.health_check()
            elif not (hasattr(self.queue, 'nc') and self.queue.nc is not None):
                raise Exception("Queue connection is not established")
            self.logger.info('health check successful')
            return True
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            raise

    async def run(self):
        """Основной метод запуска с правильной обработкой сигналов"""
        try:
            await self.queue.connect()
            await self.health_check()
        except Exception as e:
            self.logger.critical(f"Failed to start: {e}")
            return

        os.makedirs(self.temp_dir, exist_ok=True)

        try:
            # Подписываемся на топик запросов
            await self.queue.subscribe(self.request_topic, self.queue_raw_handler)
            self.logger.info("✅ Async Transcriber is running and waiting for messages...")
            
            # Ждём сигнала завершения
            await self._shutdown_event.wait()
                
        except Exception as e:
            self.logger.error(f"Error during operation: {e}")
        finally:
            await self._graceful_shutdown()

    async def _download_and_extract_archive(self, remote_path: str, job_temp_dir: str, local_paths: list, errors: list):
        archive_local_path = os.path.join(job_temp_dir, generate_random_filename())

        try:
            success, error = await run_with_timeout(
                asyncio.to_thread(download_file, self.storage, remote_path, archive_local_path),
                DOWNLOAD_TIMEOUT,
                f"Download archive {remote_path}"
            )
            if not success:
                errors.append(f"Failed to download archive {remote_path}: {error}")
                return
        except TimeoutError as e:
            errors.append(f"Timeout downloading archive {remote_path}: {e}")
            return

        extracted_dir = os.path.join(job_temp_dir, generate_random_filename())
        os.makedirs(extracted_dir, exist_ok=True)

        try:
            extract_success, extract_error = await run_with_timeout(
                asyncio.to_thread(extract_archive, archive_local_path, extracted_dir),
                EXTRACT_TIMEOUT,
                f"Extract archive {archive_local_path}"
            )
            if not extract_success:
                errors.append(f"Failed to extract archive {remote_path}: {extract_error}")
                return
        except TimeoutError as e:
            errors.append(f"Timeout extracting archive {remote_path}: {e}")
            return

        for idx, filename in enumerate(os.listdir(extracted_dir)):
            file_path = os.path.join(extracted_dir, filename)
            if os.path.isfile(file_path):
                new_filename = f"{generate_random_filename()}_{idx}"
                new_file_path = os.path.join(extracted_dir, new_filename)
                os.rename(file_path, new_file_path)
                local_paths.append(new_file_path)

    async def _download_file_list(self, remote_paths: list[str], job_temp_dir: str, local_paths: list, errors: list):
        for idx, remote_path in enumerate(remote_paths):
            local_filename = f"{generate_random_filename()}_{idx}"
            local_path = os.path.join(job_temp_dir, local_filename)
            
            try:
                coro = asyncio.to_thread(download_file, self.storage, remote_path, local_path)
                success, error = await run_with_timeout(
                    coro, 
                    DOWNLOAD_TIMEOUT,
                    f"Download file {remote_path}"
                )
                if success:
                    local_paths.append(local_path)
                else:
                    errors.append(f"Failed to download {remote_path}: {error}")
            except TimeoutError as e:
                errors.append(f"Timeout downloading {remote_path}: {e}")

    def _extract_request_data(self, msg):
        if hasattr(msg, 'data'):
            return msg.data
        return msg 
        
    def _cleanup_old_temp_dirs_sync(self, temp_dir: str, max_age_hours: int = 8):
        if not os.path.exists(temp_dir):
            return

        now = time.time()
        cutoff = now - (max_age_hours * 3600)

        for entry in os.scandir(temp_dir):
            if not entry.is_dir():
                continue

            try:
                if entry.stat().st_mtime < cutoff:
                    self.logger.info(f"🧹 Removing old temp dir: {entry.path}")
                    shutil.rmtree(entry.path, ignore_errors=True)
            except (OSError, FileNotFoundError) as e:
                self.logger.warning(f"⚠️ Failed to remove old temp dir {entry.path}: {e}")

    async def cleanup_old_temp_dirs(self, temp_dir: str, max_age_hours: int = 8):
        try:
            await run_with_timeout(
                asyncio.to_thread(self._cleanup_old_temp_dirs_sync, temp_dir, max_age_hours),
                CLEANUP_TIMEOUT,
                "Cleanup old temp directories"
            )
        except TimeoutError as e:
            self.logger.warning(f"Timeout during cleanup: {e}")

    def _prepare_job_directory(self, job_id: str) -> str:
        job_temp_dir = os.path.join(self.temp_dir, job_id)
        os.makedirs(job_temp_dir, exist_ok=True)
        return job_temp_dir
    
    async def _download_single_file(self, remote_path: str, job_temp_dir: str, local_paths: list, errors: list):
        local_filename = generate_random_filename()
        local_path = os.path.join(job_temp_dir, local_filename)
        
        try:
            coro = asyncio.to_thread(download_file, self.storage, remote_path, local_path)
            success, error = await run_with_timeout(
                coro,
                DOWNLOAD_TIMEOUT,
                f"Download single file {remote_path}"
            )
            if success:
                local_paths.append(local_path)
            else:
                errors.append(f"Failed to download {remote_path}: {error}")
        except TimeoutError as e:
            errors.append(f"Timeout downloading {remote_path}: {e}")

    async def _download_audio_files(self, request, job_temp_dir: str) -> tuple[list[str], list[str]]:
        local_paths = []
        errors = []

        if request.input_type == 'file':
            await self._download_single_file(request.audio_source.path, job_temp_dir, local_paths, errors)
        elif request.input_type == 'archive':
            await self._download_and_extract_archive(request.audio_source.archive, job_temp_dir, local_paths, errors)
        elif request.input_type == 'file_list':
            await self._download_file_list(request.audio_source.file_list, job_temp_dir, local_paths, errors)

        return local_paths, errors

    async def _process_audio_files(self, local_paths: list[str], request) -> list[Result]:
        results = []
        for local_path in local_paths:
            try:
                audio_bytes_coro = asyncio.to_thread(convert_audio_to_16khz, local_path)
                audio_bytes = await run_with_timeout(
                    audio_bytes_coro,
                    TRANSCRIPTION_TIMEOUT // 2,
                    f"Convert audio {local_path}"
                )
                
                transcription_request = TranscriptionRequest(
                    audio_bytes=audio_bytes,
                    language=getattr(request, 'language', None),
                    temperature=getattr(request, 'temperature', 0.0),
                    sample_rate=16000,
                    vad_filter=getattr(request, 'vad_filter', True)
                )
                
                segments_coro = asyncio.to_thread(self.model.predict, transcription_request)
                segments = await run_with_timeout(
                    segments_coro,
                    TRANSCRIPTION_TIMEOUT,
                    f"Transcribe {local_path}"
                )
                
                results.append(Result(segments=segments, error=None))
                
            except TimeoutError as e:
                results.append(Result(segments=[], error=f"Timeout processing file {local_path}: {str(e)}"))
            except Exception as e:
                results.append(Result(segments=[], error=f"Error processing file {local_path}: {str(e)}"))
        
        return results
    
    def _build_response(self, job_id: str, results: list[Result], download_errors: list[str]) -> Response:
        error = None
        if download_errors:
            error = f"Some files had download errors: {download_errors}"
        return Response(
            job_id=job_id,
            status='completed',
            completed_at=datetime.datetime.now(),
            results=results,
            error=error
        )
    
    async def _send_error_response(self, job_id: str, error_msg: str):
        error_response = Response(
            job_id=job_id,
            status='failed',
            completed_at=datetime.datetime.now(),
            error=error_msg
        )
        response_bytes = json.dumps({
            'job_id': error_response.job_id,
            'status': error_response.status,
            'completed_at': error_response.completed_at.isoformat(),
            'results': error_response.results,
            'error': error_response.error
        }).encode('utf-8')
        await self.queue.publish(self.response_topic, response_bytes)

    def _parse_request(self, request_data: bytes):
        try:
            return request_from_binary(request_data)
        except ValueError as e:
            job_id = extract_job_id_from_invalid_request(request_data)
            raise RequestParsingError(str(e), job_id)

    async def queue_raw_handler(self, msg):
        """Основной обработчик: оркестрирует выполнение"""
        task = asyncio.current_task()
        self._active_tasks.add(task)
        try:
            await self.cleanup_old_temp_dirs(self.temp_dir)
            request_data = self._extract_request_data(msg)         

            if len(request_data) > MAX_MESSAGE_SIZE_BYTES:
                job_id = extract_job_id_from_invalid_request(request_data)
                error_msg = f"Request too large: {len(request_data)} bytes (max {MAX_MESSAGE_SIZE_BYTES})"
                self.logger.error(f"❌ {error_msg}")
                await self._send_error_response(job_id, error_msg)
                return

            self.logger.info(f"📥 Received raw message")

            request = self._parse_request(request_data)
            self.logger.info(f"✅ Parsed request: job_id={request.job_id}, input_type={request.input_type}")

            job_temp_dir = self._prepare_job_directory(request.job_id)

            local_paths, download_errors = await self._download_audio_files(request, job_temp_dir)

            results = await self._process_audio_files(local_paths, request)
            for error in download_errors:
                results.append(Result(segments=[], error=error))

            response = self._build_response(request.job_id, results, download_errors)
            self.logger.info(f"✅ Built response: job_id={response.job_id}")

            response_bytes_for_log = serialize_response(response)
            response_str_for_log = response_bytes_for_log.decode('utf-8')
            self.logger.info(f"📤 Sending response: {response_str_for_log}")  # Первые 500 символов

            response_bytes = serialize_response(response)
            self.logger.info(f'📤 Sending response for job_id={request.job_id}')

            await self.queue.publish(self.response_topic, response_bytes)

            # Подтверждаем сообщение через абстракцию
            await self.queue.ack_message(msg)

        except RequestParsingError as e:
            self.logger.error(f"❌ Parsing error for job {e.job_id}: {e.message}")
            await self._send_error_response(e.job_id, e.message)
            await self.queue.nack_message(msg)
            return

        except Exception as e:
            self.logger.error(f"❌ Critical error in handler: {e}", exc_info=True)
            await self._send_error_response("unknown", f"Critical error in handler: {str(e)}")
            await self.queue.nack_message(msg)
        finally:
            self._active_tasks.discard(task)

    async def _graceful_shutdown(self):
        """Корректное завершение работы"""
        if self.debug:
            self.logger.info("Debug mode: forcing immediate shutdown")
            # Принудительно отменяем все задачи без ожидания
            for task in self._active_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self._active_tasks, return_exceptions=True)

            # Закрываем соединение
            try:
                await self.queue.close()
                self.logger.info("Queue connection closed (debug mode)")
            except Exception as e:
                self.logger.error(f"Error closing queue: {e}")
            return

        # Обычный graceful shutdown
        self.logger.info(f"Starting graceful shutdown with {SHUTDOWN_TIMEOUT}s timeout...")

        # Ждём завершения активных задач
        if self._active_tasks:
            self.logger.info(f"Waiting for {len(self._active_tasks)} active tasks to complete...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._active_tasks, return_exceptions=True),
                    timeout=SHUTDOWN_TIMEOUT
                )
                self.logger.info("All active tasks completed")
            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout waiting for tasks, cancelling {len(self._active_tasks)} tasks")
                for task in self._active_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._active_tasks, return_exceptions=True)

        # Закрываем соединение с очередью
        try:
            await self.queue.close()
            self.logger.info("Queue connection closed")
        except Exception as e:
            self.logger.error(f"Error closing queue: {e}")

    async def run(self):
        try:
            await self.queue.connect()
            await self.health_check()
            
            # Гарантируем существование топиков
            await self.queue.ensure_topics_exist([
                self.request_topic,
                self.response_topic
            ])
            
        except Exception as e:
            self.logger.critical(f"Failed to start: {e}")
            return

        os.makedirs(self.temp_dir, exist_ok=True)

        try:
            await self.queue.subscribe(self.request_topic, self.queue_raw_handler)
            self.logger.info("✅ Async Transcriber is running and waiting for messages...")
            await self._shutdown_event.wait()
                
        except Exception as e:
            self.logger.error(f"Error during operation: {e}")
        finally:
            await self._graceful_shutdown()
