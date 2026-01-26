from abc import ABC, abstractmethod
from typing import Dict, Any
from .model import IModel

class IModelCreator(ABC):
    @abstractmethod
    def create_model(self, params: Dict[str, Any]) -> IModel:
        """
        Создаёт экземпляр модели транскрибации на основе переданных параметров.
        Параметры зависят от конкретной реализации (например, путь к весам, device, URL Triton и т.д.).
        """
        pass

class ModelFactory:
    """
    Фабрика для создания моделей транскрибации.
    Делегирует создание экземпляра конкретному IModelCreator.
    """
    @classmethod
    def create(cls, creator: IModelCreator, params: Dict[str, Any]) -> IModel:
        """
        Создаёт модель с использованием указанного creator'а.

        :param creator: реализация IModelCreator (например, FasterWhisperModelCreator)
        :param params: параметры инициализации модели (зависят от creator'а)
        :return: экземпляр IModel
        :raises TranscriptionError: при ошибках создания (пробрасываются из creator'а)
        """
        return creator.create_model(params)