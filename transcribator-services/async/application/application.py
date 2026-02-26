import asyncio
from contextlib import asynccontextmanager
import json
import logging
import os
import datetime
import signal
from typing import Set, Optional
from .transcribation_model.model import IModel
from .message_queue.abstractions.message_queue import IMessageQueue
import fsspec
from .utils import *
from .classes import *
from .file_manager import FileManager
from .audio_processor import AudioProcessor
from .response_builder import ResponseBuilder
from .temp_file_manager import TempFileManager
from .message_handler import MessageHandler
from .database.dictionary_db.database import DictionaryDatabase

SHUTDOWN_TIMEOUT = 10


class App:
    def __init__(
        self,
        model: IModel,
        queue: IMessageQueue,
        storage: fsspec.AbstractFileSystem,
        request_topic: str,
        response_topic: str,
        dict_db: DictionaryDatabase,
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
        self.dict_db = dict_db
        self.logger = logger or logging.getLogger("transcriber")
        self.debug = debug

        # Initialize the component managers
        self.file_download_manager = FileManager(storage, self.logger)
        self.audio_processor = AudioProcessor(model, self.logger)
        self.response_builder = ResponseBuilder(response_topic, queue, self.logger)
        self.temp_file_manager = TempFileManager(temp_dir, self.logger)
        self.message_handler = MessageHandler(
            self.file_download_manager,
            self.audio_processor,
            self.response_builder,
            self.temp_file_manager,
            dict_db,
            self.logger
        )

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

            if not self.dict_db.ping():
                raise Exception(f"failed to connect to dict db {self.dict_db.name()}")
            self.logger.info('health check successful')
            return True
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            raise

    async def queue_raw_handler(self, msg):
        """Main handler: orchestrates execution"""
        task = asyncio.current_task()
        self._active_tasks.add(task)
        try:
            await self.message_handler.handle_message(msg, self.queue)
        finally:
            self._active_tasks.discard(task)

    async def _graceful_shutdown(self):
        """Graceful shutdown"""
        if self.debug:
            self.logger.info("Debug mode: forcing immediate shutdown")
            # Cancel all tasks without waiting
            for task in self._active_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self._active_tasks, return_exceptions=True)

            # Close connection
            try:
                await self.queue.close()
                self.logger.info("Queue connection closed (debug mode)")
            except Exception as e:
                self.logger.error(f"Error closing queue: {e}")
            return

        # Normal graceful shutdown
        self.logger.info(f"Starting graceful shutdown with {SHUTDOWN_TIMEOUT}s timeout...")

        # Wait for active tasks to complete
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

        # Close queue connection
        try:
            await self.queue.close()
            self.logger.info("Queue connection closed")
        except Exception as e:
            self.logger.error(f"Error closing queue: {e}")

    async def run(self):
        try:
            await self.queue.connect()
            await self.health_check()

            # Ensure topics exist
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