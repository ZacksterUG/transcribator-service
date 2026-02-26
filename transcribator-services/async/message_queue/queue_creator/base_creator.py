from abc import ABC, abstractmethod
from typing import Any, Dict

from ..abstractions.message_queue import IMessageQueue

class IQueueCreator(ABC):
    """Абстрактная фабрика для создания экземпляров очередей."""
    
    @abstractmethod
    def create_queue(self, params: Dict[str, Any]) -> IMessageQueue:
        pass