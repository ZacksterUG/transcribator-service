from abc import ABC, abstractmethod
from typing import Any, Callable, List

class IMessageQueue(ABC):
    """
    Абстрактный интерфейс для работы с системой сообщений.
    Реализации должны поддерживать асинхронное подключение, публикацию и подписку.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Устанавливает соединение с брокером."""
        pass

    @abstractmethod
    async def publish(self, topic: str, message: bytes) -> None:
        """Публикует сообщение в указанный топик/очередь."""
        pass

    @abstractmethod
    async def subscribe(self, topic: str, handler: Callable) -> None:
        """
        Подписывается на топик и передаёт входящие сообщения в обработчик.
        Обработчик должен принимать один аргумент — сообщение (bytes или объект).
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Закрывает соединение с брокером."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Проверяет работоспособность соединения с брокером.
        Возвращает True, если соединение активно и готово к работе.
        """
        pass

    @abstractmethod
    async def ack_message(self, message_context: Any) -> None:
        """Подтверждает обработку сообщения (если поддерживается)."""
        pass

    @abstractmethod
    async def nack_message(self, message_context: Any) -> None:
        """Отклоняет сообщение для повторной обработки (если поддерживается)."""
        pass

    @abstractmethod
    async def ensure_topic_exists(self, topic: str, **kwargs) -> None:
        """
        Гарантирует существование топика/стрима с заданными параметрами.
        Для брокеров без явного управления топиками (например, core NATS) — no-op.
        """
        pass

    @abstractmethod
    async def ensure_topics_exist(self, topics: List[str], **kwargs) -> None:
        """
        Гарантирует существование нескольких топиков.
        """
        pass

    @abstractmethod
    async def get_name(self) -> str:
        """
        Имя экземпляра
        """
        pass