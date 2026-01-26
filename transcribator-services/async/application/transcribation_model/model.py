from abc import ABC, abstractmethod
from typing import List, Optional
from .segment import Segment
from .request import TranscriptionRequest
from .exceptions import TranscriptionError

class IModel(ABC):
    @abstractmethod
    def predict(self, request: TranscriptionRequest) -> List[Segment]:
        """
        Выполняет транскрибацию аудио.
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

