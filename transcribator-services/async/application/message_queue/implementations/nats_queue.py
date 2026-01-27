import asyncio
from typing import Any, Dict, Callable, List, Optional
from ..abstractions.message_queue import IMessageQueue
from ..queue_creator.base_creator import IQueueCreator
import nats
from nats.aio.client import Client
from nats.js import JetStreamContext
from nats.js.api import KeyValueConfig

class NatsQueue(IMessageQueue):
    def __init__(self, servers: list, use_jetstream: bool = False, **kwargs):
        if not nats:
            raise RuntimeError("nats-py is not installed")
        self.servers = servers
        self.use_jetstream = use_jetstream  # <-- НОВЫЙ ПАРАМЕТР
        self.nc: Client = None
        self.js: Optional[JetStreamContext] = None
        self.kwargs = kwargs
        self._subscriptions: List[Any] = []

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
            
            psub = await self.js.pull_subscribe(
                subject=topic,
                durable=durable_name,
                stream=f"STREAM_{topic.replace('.', '_').upper()}"
            )
            
            # Обёртка над handler с поддержкой in_progress
            async def handler_with_heartbeat(msg):
                # Запускаем heartbeat если поддерживается
                heartbeat_task = None
                if hasattr(msg, 'in_progress'):
                    async def heartbeat():
                        try:
                            while True:
                                await msg.in_progress()
                                await asyncio.sleep(3)  # каждые 3 секунды
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            pass  # игнорируем ошибки heartbeat
                        
                    heartbeat_task = asyncio.create_task(heartbeat())
                
                try:
                    # Вызываем оригинальный handler
                    await handler(msg)
                finally:
                    # Отменяем heartbeat
                    if heartbeat_task:
                        heartbeat_task.cancel()
                        try:
                            await heartbeat_task
                        except asyncio.CancelledError:
                            pass
                        
            # Запускаем фоновую задачу для pull-обработки
            async def pull_loop():
                while True:
                    try:
                        messages = await psub.fetch(1, timeout=5)
                        for msg in messages:
                            # Запускаем обработку как отдельную задачу
                            asyncio.create_task(handler_with_heartbeat(msg))
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        print(f"Pull error: {e}")
                        await asyncio.sleep(1)
            
            task = asyncio.create_task(pull_loop())
            self._subscriptions.append(task)
            
        else:
            # core NATS
            sub = await self.nc.queue_subscribe(
                subject=topic,
                queue="transcriber-workers",
                cb=handler
            )
            self._subscriptions.append(sub)

    async def close(self) -> None:
        """Корректное закрытие NATS соединения"""
        if not self.nc:
            return

        # Отменяем все подписки и задачи
        for sub_or_task in self._subscriptions:
            try:
                if isinstance(sub_or_task, asyncio.Task):
                    sub_or_task.cancel()
                    await sub_or_task
                else:
                    # Это подписка (для core NATS)
                    await sub_or_task.unsubscribe()
            except Exception:
                pass
            
        self._subscriptions.clear()

        # Закрываем соединение
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
        """Создаёт JetStream стрим для топика, если используется JetStream."""
        if not self.use_jetstream:
            # Core NATS не требует создания топиков
            return
        
        if not self.js:
            raise RuntimeError("JetStream not initialized")
        
        try:
            # Параметры по умолчанию, можно переопределить через kwargs
            retention = kwargs.get('retention', nats.js.api.RetentionPolicy.LIMITS)
            max_age = kwargs.get('max_age', 72 * 3600)  # 72 часа
            storage = kwargs.get('storage', nats.js.api.StorageType.FILE)
            max_msgs = kwargs.get('max_msgs', -1)
            
            await self.js.add_stream(
                name=f"STREAM_{topic.replace('.', '_').upper()}",
                subjects=[topic],
                retention=retention,
                max_age=max_age,
                storage=storage,
                max_msgs=max_msgs,
                num_replicas=1
            )
        except Exception as e:
            if "already in use" in str(e).lower():
                # Стрим уже существует - это нормально
                pass
            else:
                raise
            
    async def ensure_topics_exist(self, topics: List[str], **kwargs) -> None:
        """Гарантирует существование нескольких топиков."""
        for topic in topics:
            await self.ensure_topic_exists(topic, **kwargs)
        
class NatsQueueCreator(IQueueCreator):
    def create_queue(self, params: Dict[str, Any]) -> IMessageQueue:
        required = {"servers"}
        if not required.issubset(params.keys()):
            raise ValueError(f"NATS requires: {required}")
        
        # Извлекаем специфичные параметры
        servers = params["servers"]
        use_jetstream = params.get("use_jetstream", False)
        
        # Остальные параметры передаём как есть
        other_params = {
            k: v for k, v in params.items() 
            if k not in ["servers", "use_jetstream"]
        }
        
        return NatsQueue(
            servers=servers, 
            use_jetstream=use_jetstream,
            **other_params
        )
    
