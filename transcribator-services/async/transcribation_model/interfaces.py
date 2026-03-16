from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict
from .classes import TranscriptionRequest, Segment

class IModel(ABC):
    @abstractmethod
    def predict(self, request: TranscriptionRequest, ctx: Any = None) -> List[Segment]:
        """
        Выполняет транскрибацию аудио.
            ctx: Произвольный контекст, который можно передать модели
        Выбрасывает TranscriptionError.
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_version(self) -> str:
        pass

    def warmup(self, request: Optional[TranscriptionRequest] = None) -> None:
        """Опциональный прогрев модели. Реализуется по необходимости."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

class IModelCreator(ABC):
    @abstractmethod
    def create_model(self, params: Dict[str, Any]) -> IModel:
        """
        Создаёт экземпляр модели транскрибации на основе переданных параметров.
        Параметры зависят от конкретной реализации (например, путь к весам, device, URL Triton и т.д.).
        """
        pass

