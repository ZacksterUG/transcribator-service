import asyncio
import logging
from typing import Any, Dict, Callable, List, Optional
from ..abstractions.message_queue import IMessageQueue
from ..queue_creator.base_creator import IQueueCreator
import nats
from nats.aio.client import Client
from nats.js import JetStreamContext
from nats.js.api import ConsumerConfig, AckPolicy
from nats.aio.msg import Msg


class NatsQueue(IMessageQueue):
    def __init__(self, servers: list, use_jetstream: bool = False,
                 ack_wait: int = 60, max_concurrent: int = 10, **kwargs):
        if not nats:
            raise RuntimeError("nats-py is not installed")
        self.servers = servers
        self.use_jetstream = use_jetstream
        self.ack_wait = ack_wait  # <-- Время ожидания ACK
        self.max_concurrent = max_concurrent  # <-- Лимит параллельных задач
        self.nc: Client = None
        self.js: Optional[JetStreamContext] = None
        self.kwargs = kwargs
        self._subscriptions: List[Any] = []
        self.logger = logging.getLogger(__name__)  # <-- FIX: инициализация логгера

    async def connect(self) -> None:
        self.nc = await nats.connect(servers=self.servers, **self.kwargs)
        if self.use_jetstream:
            self.js = self.nc.jetstream()

    async def publish(self, topic: str, message: bytes) -> None:
        if not self.nc:
            raise RuntimeError("Not connected to NATS")

        if self.use_jetstream:
            if not self.js:
                raise RuntimeError("JetStream not initialized")
            await self.js.publish(topic, message)
        else:
            await self.nc.publish(topic, message)

    async def subscribe(self, topic: str, handler: Callable) -> None:
        if not self.nc:
            raise RuntimeError("Not connected to NATS")

        if self.use_jetstream:
            if not self.js:
                raise RuntimeError("JetStream not initialized")

            # ФИКСИРОВАННОЕ имя для всех реплик
            durable_name = "transcriber-workers"
            stream_name = f"STREAM_{topic.replace('.', '_').upper()}"

            psub = await self.js.pull_subscribe(
                subject=topic,
                durable=durable_name,
                stream=stream_name,
                config=ConsumerConfig(
                    ack_policy=AckPolicy.EXPLICIT,
                    ack_wait=self.ack_wait,  # <-- 60 секунд
                    max_ack_pending=self.max_concurrent  # <-- Лимит на уровне сервера
                )
            )

            # Semaphore для ограничения конкурентности
            semaphore = asyncio.Semaphore(self.max_concurrent)

            async def handler_with_heartbeat(msg: Msg):
                heartbeat_task = None
                try:
                    # Запускаем heartbeat если поддерживается
                    if hasattr(msg, 'in_progress'):
                        async def heartbeat():
                            try:
                                while True:
                                    await asyncio.sleep(self.ack_wait / 3)
                                    await msg.in_progress()
                            except asyncio.CancelledError:
                                raise
                            except Exception as e:
                                self.logger.warning(f"Heartbeat error: {e}")

                        heartbeat_task = asyncio.create_task(heartbeat())

                    # Вызываем оригинальный handler
                    await handler(msg)

                    # ✅ ACK только после успешного завершения handler
                    await msg.ack()
                    self.logger.debug(f"Message acknowledged: {msg.subject}")

                except Exception as e:
                    self.logger.error(f"Handler error: {e}", exc_info=True)
                    # ✅ NAK при ошибке (сообщение вернётся в очередь)
                    try:
                        await msg.nak()
                        self.logger.debug(f"Message nacked, will redeliver")
                    except Exception as nak_err:
                        self.logger.error(f"Failed to nak: {nak_err}")
                    raise  # Пробрасываем исключение дальше
                finally:
                    # Отменяем heartbeat
                    if heartbeat_task:
                        heartbeat_task.cancel()
                        try:
                            await heartbeat_task
                        except asyncio.CancelledError:
                            pass

            async def pull_loop():
                while True:
                    try:
                        # Ограничиваем конкурентность на уровне клиента
                        async with semaphore:
                            messages = await psub.fetch(1, timeout=5)
                            for msg in messages:
                                asyncio.create_task(handler_with_heartbeat(msg))
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        self.logger.error(f"Pull error: {e}", exc_info=True)
                        await asyncio.sleep(1)

            task = asyncio.create_task(pull_loop())
            self._subscriptions.append(task)

        else:
            # Core NATS
            sub = await self.nc.queue_subscribe(
                subject=topic,
                queue="transcriber-workers",
                cb=handler
            )
            self._subscriptions.append(sub)

    async def close(self) -> None:
        if not self.nc:
            return

        for sub_or_task in self._subscriptions:
            try:
                if isinstance(sub_or_task, asyncio.Task):
                    sub_or_task.cancel()
                    await sub_or_task
                else:
                    await sub_or_task.unsubscribe()
            except Exception:
                pass

        self._subscriptions.clear()

        try:
            await self.nc.drain()
        except Exception:
            pass

        try:
            await self.nc.close()
        except Exception:
            pass

        self.nc = None
        self.js = None

    async def health_check(self) -> bool:
        if not self.nc:
            return False
        try:
            if not self.nc.is_connected and not self.nc.is_reconnecting:
                return False
            await self.nc.flush(timeout=5)
            return True
        except Exception:
            return False

    async def ack_message(self, message_context: Any) -> None:
        """Подтверждает сообщение если это JetStream."""
        # <-- FIX: ACK теперь внутри handler_with_heartbeat, этот метод можно удалить
        # или оставить для совместимости с интерфейсом
        if self.use_jetstream and hasattr(message_context, 'ack'):
            try:
                await message_context.ack()
            except Exception as e:
                self.logger.debug(f"Failed to ack message: {e}")

    async def nack_message(self, message_context: Any) -> None:
        """Отклоняет сообщение если это JetStream."""
        if self.use_jetstream and hasattr(message_context, 'nak'):
            try:
                await message_context.nak()
            except Exception as e:
                self.logger.debug(f"Failed to nak message: {e}")

    async def ensure_topic_exists(self, topic: str, **kwargs) -> None:
        if not self.use_jetstream:
            return

        if not self.js:
            raise RuntimeError("JetStream not initialized")

        try:
            retention = kwargs.get('retention', nats.js.api.RetentionPolicy.LIMITS)
            max_age = kwargs.get('max_age', 72 * 3600)
            storage = kwargs.get('storage', nats.js.api.StorageType.FILE)
            max_msgs = kwargs.get('max_msgs', 2)

            await self.js.add_stream(
                name=f"STREAM_{topic.replace('.', '_').upper()}",
                subjects=[topic],
                retention=retention,
                max_age=max_age,
                storage=storage,
                max_msgs=max_msgs,
                num_replicas=1,
            )
        except Exception as e:
            if "already in use" in str(e).lower():
                pass
            else:
                raise

    async def ensure_topics_exist(self, topics: List[str], **kwargs) -> None:
        for topic in topics:
            await self.ensure_topic_exists(topic, **kwargs)

    async def get_name(self) -> str:
        return 'Nats'
        
class NatsQueueCreator(IQueueCreator):
    def create_queue(self, params: Dict[str, Any]) -> IMessageQueue:
        required = {"servers"}
        if not required.issubset(params.keys()):
            raise ValueError(f"NATS requires: {required}")
        
        # Извлекаем специфичные параметры
        servers = params["servers"]
        use_jetstream = params.get("use_jetstream", False)
        ack_wait = params.get("ack_wait", 60)  # <-- FIX: параметр из конфига
        max_concurrent = params.get("max_concurrent", 10)

        other_params = {
            k: v for k, v in params.items()
            if k not in ["servers", "use_jetstream", "ack_wait", "max_concurrent"]
        }
        
        return NatsQueue(
            servers=servers, 
            use_jetstream=use_jetstream,
            ack_wait=ack_wait,
            max_concurrent=max_concurrent,
            **other_params
        )
    
