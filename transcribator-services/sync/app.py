import base64
import json
from datetime import datetime, timedelta
from typing import Optional, Dict
import numpy as np
from nats.aio.client import Msg
import redis
from nats.aio.client import Client
from nats.aio.subscription import Subscription
from redis.lock import Lock
from sherpa_onnx import OnlineRecognizer
import asyncio
from logging import Logger, getLogger
from utils import check_job_id
from exceptions import RedisJobLocker, MaximumPoolReached, HandleInitJobIdError, BytesNotProvidedError
from config import Config

class App:
    def __init__(self,
                 redis_db: redis.Redis,
                 nats_client: Client,
                 recognizer: OnlineRecognizer,
                 config: Config,
                 logger: Logger = None) -> None:
        self.redis_db = redis_db
        self.nats_client = nats_client
        self.recognizer = recognizer
        self.config = config

        self.current_active_streams = 0
        self.pool_lock = asyncio.Lock()
        self.init_sub: Optional[Subscription] = None

        if logger is None:
            self.logger = getLogger('transcriber_async')
        else:
            self.logger = logger

    async def handle_init(self, message: Msg):
        job_id: Optional[str] = None
        err_message: str = ''

        try:
            data = message.data.decode()
            data_json: Dict = json.loads(data)
            self.logger.info(data_json)

            job_id = data_json.get('job_id', None)

            if job_id is None:
                raise HandleInitJobIdError('job_id is not provided')

            if not check_job_id(job_id):
                raise HandleInitJobIdError('job_id is not valid')

            async with self.pool_lock:
                if self.current_active_streams >= self.config.max_active_streams:
                    raise MaximumPoolReached('maximum pool reached')

            lock = self.redis_db.lock(f'transcriber.sync.{job_id}', blocking=False, timeout=10)

            if not lock.acquire(blocking=False):
                raise RedisJobLocker(f'job with {job_id} is already running')

            asyncio.create_task(self.handle_messages(lock, job_id))

        except json.JSONDecodeError as e:
            err_message = f'Failed to decode JSON data: {str(e)}'
            self.logger.error(err_message)

        except HandleInitJobIdError as e:
            err_message = f'Failed to handle job id error: {str(e)}'
            self.logger.error(err_message)

        except RedisJobLocker as e:
            err_message = f'Redis locked: {str(e)}'
            self.logger.error(err_message)

        except MaximumPoolReached as e:
            err_message = f'Failed to create job handle: {str(e)}'
            self.logger.warning(err_message)

        finally:
            if job_id is not None and job_id != '' and err_message != '':
                status_data = {
                    'status': 'failed',
                    'error': err_message
                }

                await self.nats_client.publish(f'{self.config.status_topic_prefix}.{job_id}', json.dumps(status_data).encode())

    async def handle_messages(self, lock: Lock, job_id: str) -> None:
        self.logger.info(f'start processing job {job_id}...')
        is_finished = False

        async with self.pool_lock:
            self.current_active_streams += 1

        sub_handle: Optional[Subscription] = None

        async def extend_lock():
            while True:
                try:
                    if lock.locked():
                        lock.extend(additional_time=10, replace_ttl=True)
                except Exception as e:
                    self.logger.error(f"Failed to extend lock {job_id}: {e}")
                    break
                await asyncio.sleep(5)

        task_extend_lock = asyncio.create_task(extend_lock())
        task_check_timeout: asyncio.Task
        streamer = self.recognizer.create_stream()

        async def finish():
            nonlocal is_finished

            if is_finished:
                return

            is_finished = True

            self.logger.info(f'Finished processing job {job_id}')
            task_extend_lock.cancel()
            task_check_timeout.cancel()
            if lock.locked():
                try:
                    lock.release()
                except Exception:
                    pass

            try:
                await sub_handle.unsubscribe()
            except Exception:
                pass

            async with self.pool_lock:
                self.current_active_streams -= 1
        last_message_date = datetime.now()

        async def check_timeout():
            while True:
                now = datetime.now()

                if now >= last_message_date + timedelta(seconds=self.config.job_active_timeout):
                    await finish()
                    break

                await asyncio.sleep(3)

        task_check_timeout = asyncio.create_task(check_timeout())

        async def handle_byte_message(msg: Msg) -> None:
            nonlocal last_message_date
            last_message_date = datetime.now()

            try:
                data_json = json.loads(msg.data)

                if data_json.get('finish'):
                    await finish()

                    data_status_finished = {
                        'status': 'finished',
                        'error': None
                    }

                    await self.nats_client.publish(f'{self.config.status_topic_prefix}.{job_id}', json.dumps(data_status_finished).encode())
                    return

                audio_b64 = data_json.get('bytes')

                if not audio_b64:
                    raise BytesNotProvidedError('attribute bytes must be provided')

                waveform = np.frombuffer(base64.b64decode(audio_b64), dtype=np.float32)
                streamer.accept_waveform(sample_rate=self.config.sample_rate, waveform=waveform)

                while self.recognizer.is_ready(streamer):
                    self.recognizer.decode_stream(streamer)

                # Получаем результат
                result_obj = self.recognizer.get_result(streamer)
                is_endpoint = self.recognizer.is_endpoint(streamer)

                if is_endpoint:
                    self.recognizer.reset(streamer)

                text = result_obj.strip()

                transcription = {
                    'text': text,
                    'is_endpoint': is_endpoint,
                }

                response_json = {
                    'error': None,
                    'result': transcription
                }

                await self.nats_client.publish(f'{self.config.response_topic_prefix}.{job_id}', json.dumps(response_json).encode())

            except Exception as e:

                error_message = f'Failed on handling audio chunk: {str(e)}'
                self.logger.error(error_message)

                error_data = {
                    'error': True,
                    'message': error_message,
                }

                await self.nats_client.publish(f'{self.config.response_topic_prefix}.{job_id}', json.dumps(error_data).encode())

        sub_handle = await self.nats_client.subscribe(f'{self.config.processing_topic_prefix}.{job_id}', cb=handle_byte_message)

        ready_json_data = {
            'status': 'ready',
            'error': None
        }

        await self.nats_client.publish(f'{self.config.status_topic_prefix}.{job_id}', json.dumps(ready_json_data).encode())

    async def run(self) -> None:
        try:
            self.init_sub = await self.nats_client.subscribe(self.config.init_topic, cb=self.handle_init)

            while True:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError as e:
            await self.init_sub.unsubscribe()
            self.logger.error(f'Error occurred while attempting handling jobs: {str(e)}')