import asyncio
import json
import logging
from typing import Optional
from .file_download_manager import FileDownloadManager
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
        file_download_manager: FileDownloadManager,
        audio_processor: AudioProcessor,
        response_builder: ResponseBuilder,
        temp_file_manager: TempFileManager,
        logger: Optional[logging.Logger] = None
    ):
        self.file_download_manager = file_download_manager
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
        request_data = self._extract_request_data(msg)
        
        # Check message size
        if len(request_data) > MAX_MESSAGE_SIZE_BYTES:
            job_id = extract_job_id_from_invalid_request(request_data)
            error_msg = f"Request too large: {len(request_data)} bytes (max {MAX_MESSAGE_SIZE_BYTES})"
            self.logger.error(f"❌ {error_msg}")
            await self.response_builder.send_error_response(job_id, error_msg)
            await queue.nack_message(msg)
            return
        
        try:
            temp_json = json.loads(request_data.decode('utf-8'))
            job_id = temp_json.get('job_id', 'unknown')

            if temp_json.get('input_type') == 'file_list':
                file_list = temp_json.get('audio_source', {}).get('file_list', [])
                
                if len(file_list) > MAX_ALLOWED_FILES:
                    error_msg = f"Too many files in file_list: {len(file_list)} > {MAX_ALLOWED_FILES}"
                    self.logger.error(f"❌ {error_msg} (job_id={job_id})")
                    await self.response_builder.send_error_response(job_id, error_msg)
                    await queue.nack_message(msg)
                    return
        except Exception:
            pass  # Пропускаем — основная валидация будет в _parse_request

        self.logger.info(f"📥 Received raw message")

        try:
            # Parse the request
            request = self._parse_request(request_data)
            self.logger.info(f"✅ Parsed request: job_id={request.job_id}, input_type={request.input_type}")

            # Clean up old temp directories
            await self.temp_file_manager.cleanup_old_temp_dirs()

            # Prepare job directory
            job_temp_dir = self.temp_file_manager.prepare_job_directory(request.job_id)

            # Download audio files
            local_paths, download_errors = await self.file_download_manager.download_audio_files(request, job_temp_dir)

            # Process audio files
            results = await self.audio_processor.process_audio_files(local_paths, request)
            
            # Add download errors to results
            for error in download_errors:
                results.append(Result(segments=[], error=error))

            # Build and send response
            response = self.response_builder.build_response(request.job_id, results, download_errors)
            self.logger.info(f"✅ Built response: job_id={response.job_id}")

            response_bytes = serialize_response(response)
            self.logger.info(f'📤 Sending response for job_id={request.job_id}')

            await queue.publish(self.response_builder.response_topic, response_bytes)

            # Acknowledge the message
            await queue.ack_message(msg)

        except RequestParsingError as e:
            self.logger.error(f"❌ Parsing error for job {e.job_id}: {e.message}")
            await self.response_builder.send_error_response(e.job_id, e.message)
            await queue.nack_message(msg)
        except Exception as e:
            self.logger.error(f"❌ Critical error in handler: {e}", exc_info=True)
            await self.response_builder.send_error_response("unknown", f"Critical error in handler: {str(e)}")
            await queue.nack_message(msg)