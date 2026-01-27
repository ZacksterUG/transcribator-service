import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from typing import Optional
from .file_manager import FileManager
from .message_queue.abstractions.message_queue import IMessageQueue
from .audio_processor import AudioProcessor
from .response_builder import ResponseBuilder
from .temp_file_manager import TempFileManager
from .utils import *
from .classes import Request, Result
import datetime

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
        logger: Optional[logging.Logger] = None
    ):
        self.file_manager = file_manager
        self.audio_processor = audio_processor
        self.response_builder = response_builder
        self.temp_file_manager = temp_file_manager
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
        Handles an incoming message from the queue.

        Args:
            msg: Incoming message
            queue: Message queue instance
        """
        job_id = "unknown"
        request_data = self._extract_request_data(msg)
        response_json = ""
        parent_dir = ""

        # --- 1. Ранняя валидация: размер сообщения ---
        if len(request_data) > MAX_MESSAGE_SIZE_BYTES:
            job_id = extract_job_id_from_invalid_request(request_data) or "unknown"
            error_msg = f"Request too large: {len(request_data)} bytes (max {MAX_MESSAGE_SIZE_BYTES})"
            self.logger.error(f"❌ {error_msg} (job_id={job_id})")
            await self.response_builder.send_error_response(job_id, error_msg)
            await queue.ack_message(msg)
            return

        # --- 2. Извлечение job_id и ранняя проверка file_list ---
        try:
            temp_json = json.loads(request_data.decode('utf-8'))
            job_id = temp_json.get('job_id', 'unknown')

            if temp_json.get('input_type') == 'file_list':
                file_list = temp_json.get('audio_source', {}).get('file_list', [])
                if len(file_list) > MAX_ALLOWED_FILES:
                    error_msg = f"Too many files in file_list: {len(file_list)} > {MAX_ALLOWED_FILES}"
                    self.logger.error(f"❌ {error_msg} (job_id={job_id})")
                    await self.response_builder.send_error_response(job_id, error_msg)
                    await queue.ack_message(msg)
                    return
        except Exception:
            pass  # Детальная валидация — в _parse_request

        self.logger.info(f"📥 Received message (job_id={job_id})")

        try:
            # --- 3. Основная обработка ---
            request = self._parse_request(request_data)
            job_id = request.job_id
            parent_dir = request.audio_source.get_parent_dir()
            self.logger.info(f"✅ Parsed request: job_id={job_id}, input_type={request.input_type}")

            # Очистка старых временных директорий
            await self.temp_file_manager.cleanup_old_temp_dirs()

            # Подготовка локальной временной директории (только для обработки!)
            job_temp_dir = self.temp_file_manager.prepare_job_directory(job_id)

            # Загрузка и обработка
            local_paths, download_errors = await self.file_manager.download_audio_files(request, job_temp_dir)

            results = await self.audio_processor.process_audio_files(local_paths, request)

            for error in download_errors:
                results.append(Result(segments=[], error=error))


            # Успешный ответ
            response = self.response_builder.build_response(job_id, results, download_errors)
            response_bytes = serialize_response(response)
            response_json = response_bytes.decode('utf-8')  # ← используем UTF-8, а не windows-1251

            self.logger.info(f'📤 Sending response for job_id={job_id}')
            await queue.publish(self.response_builder.response_topic, response_bytes)
            await queue.ack_message(msg)

        except RequestParsingError as e:
            # Валидационная ошибка — не повторяем
            job_id = e.job_id
            self.logger.error(f"❌ Parsing error for job {job_id}: {e.message}")

            # Строим единообразный объект ответа
            error_response = self.response_builder.build_error_response(job_id, e.message)
            response_bytes = serialize_response(error_response)
            response_json = response_bytes.decode('utf-8')

            await self.response_builder.send_error_response(job_id, e.message)
            await queue.ack_message(msg)

        except Exception as e:
            # Критическая ошибка — не подтверждаем (NATS JetStream повторит)
            self.logger.error(f"❌ Critical error in handler for job {job_id}: {e}", exc_info=True)

            # Строим ответ с ошибкой для сохранения
            error_response = self.response_builder.build_error_response(
                job_id, 
                f"Critical error in handler: {str(e)}"
            )
            response_bytes = serialize_response(error_response)
            response_json = response_bytes.decode('utf-8')

            await self.response_builder.send_error_response(job_id, str(e))
            await queue.ack_message(msg)

        finally:
            if job_id != "unknown" and response_json:
                try:
                    remote_path = os.path.join(parent_dir, f"result_{time.strftime('%Y%m%d_%H%M%S')}.json").replace("\\", "/")

                    await self.file_manager.upload_result_json(response_json, remote_path)
                    self.logger.info(f"☁️ Uploaded result.json to {remote_path}")

                except Exception as save_err:
                    self.logger.warning(
                        f"⚠️ Failed to upload result.json for job {job_id}: {save_err}",
                        exc_info=True
                    )