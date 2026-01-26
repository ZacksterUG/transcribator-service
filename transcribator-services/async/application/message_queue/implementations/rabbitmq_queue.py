import asyncio
from typing import Any, Dict, Callable, List
from ..abstractions.message_queue import IMessageQueue
from ..queue_creator.base_creator import IQueueCreator

try:
    import aio_pika
except ImportError:
    aio_pika = None

class RabbitMQQueue(IMessageQueue):
    def __init__(self, url: str, **kwargs):
        if not aio_pika:
            raise RuntimeError("aio-pika is not installed")
        self.url = url
        self.connection = None
        self.channel = None
        self.kwargs = kwargs

    async def connect(self) -> None:
        self.connection = await aio_pika.connect_robust(self.url)
        self.channel = await self.connection.channel()

    async def publish(self, topic: str, message: bytes) -> None:
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ")
        exchange = await self.channel.declare_exchange(
            name="transcribe", type=aio_pika.ExchangeType.TOPIC, durable=True
        )
        await exchange.publish(aio_pika.Message(body=message), routing_key=topic)

    async def subscribe(self, topic: str, handler: Callable) -> None:
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ")
        exchange = await self.channel.declare_exchange(
            name="transcribe", type=aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await self.channel.declare_queue(durable=True)
        await queue.bind(exchange, routing_key=topic)

        async with queue.iterator() as q_iter:
            async for message in q_iter:
                async with message.process():
                    await handler(message)

    async def close(self) -> None:
        if self.connection:
            await self.connection.close()

    async def health_check(self) -> None:
        """
        Проверяет работоспособность соединения с RabbitMQ.
        Выбрасывает исключение, если соединение недоступно или неработоспособно.
        """
        if not self.connection:
            raise ConnectionError("RabbitMQ connection is not established")

        if self.connection.is_closed:
            raise ConnectionError("RabbitMQ connection is closed")

        if not self.channel or self.channel.is_closed:
            raise ConnectionError("RabbitMQ channel is not open or closed")

        try:
            # Попробуем создать и удалить временный обменник — чтобы проверить доступ к брокеру
            test_exchange = await self.channel.declare_exchange(
                "health_check", aio_pika.ExchangeType.FANOUT, auto_delete=True
            )
            await test_exchange.delete()
        except Exception as e:
            raise ConnectionError(f"RabbitMQ health check failed: {str(e)}") from e
        
    async def ack_message(self, message_context: Any) -> None:
        """RabbitMQ автоматически подтверждает через message.process() контекст."""
        # В текущей реализации RabbitMQ использует async with message.process(),
        # поэтому явное подтверждение не нужно
        pass
    
    async def nack_message(self, message_context: Any) -> None:
        """RabbitMQ автоматически отклоняет при исключении в message.process()."""
        pass
    async def ensure_topic_exists(self, topic: str, **kwargs) -> None:
        """
        RabbitMQ: гарантируем существование exchange и queue.
        """
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ")
        
        # Создаём exchange
        exchange = await self.channel.declare_exchange(
            name="transcribe", 
            type=aio_pika.ExchangeType.TOPIC, 
            durable=True
        )
        
        # Создаём очередь (если нужно)
        queue_name = f"queue_{topic.replace('.', '_')}"
        queue = await self.channel.declare_queue(
            name=queue_name,
            durable=True,
            arguments={"x-message-ttl": 72 * 3600 * 1000}  # 72 часа в миллисекундах
        )
        
        # Привязываем очередь к exchange
        await queue.bind(exchange, routing_key=topic)
    
    async def ensure_topics_exist(self, topics: List[str], **kwargs) -> None:
        for topic in topics:
            await self.ensure_topic_exists(topic, **kwargs)

class RabbitMQQueueCreator(IQueueCreator):
    def create_queue(self, params: Dict[str, Any]) -> IMessageQueue:
        if "url" not in params:
            raise ValueError("RabbitMQ requires 'url'")
        return RabbitMQQueue(url=params["url"])