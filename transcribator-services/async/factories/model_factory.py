from typing import Dict, Any
from transcribation_model.interfaces import IModelCreator, IModel
from config.enums import ModelType
from transcribation_model.faster_whisper_model import FasterWhisperCreator
from transcribation_model.croc_whisper import CrocWhisperModelCreator

class ModelFactory:
    """
    Фабрика выбора модели транскрибации.

    Следует паттерну ваших QueueFactory/StorageFactory:
    create(creator: IModelCreator, params: Dict) -> IModel

    Для выбора модели используется вспомогательный метод create_by_type().
    """

    @classmethod
    def create(cls, creator: IModelCreator, params: Dict[str, Any]) -> IModel:
        """Создаёт модель через переданный creator (прямой вызов, как в QueueFactory)."""
        return creator.create_model(params)

    @classmethod
    def create_by_type(
            cls,
            model_type: ModelType,
            params: Dict[str, Any],
            redis_db: Any = None,
    ) -> IModel:
        """
        Выбирает creator на основе типа модели и создаёт экземпляр.

        :param model_type: ModelType.FASTER_WHISPER | ModelType.CROC_WHISPER
        :param params: параметры из config/settings.py (плоский dict)
        :param redis_db: экземпляр DictionaryDatabase (обязателен для CROC)
        """
        if model_type == ModelType.FASTER_WHISPER:
            creator = FasterWhisperCreator()
            model_params = {
                'model_size_or_path': params['model_path_or_size'],
                'device': params['model_device'],
                'compute_type': params['model_compute_type'],
                'num_workers': params.get('model_num_workers', 1),
            }
            return cls.create(creator, model_params)

        elif model_type == ModelType.CROC_WHISPER:
            if redis_db is None:
                raise ValueError("redis_db is required for CROC_WHISPER model")

            creator = CrocWhisperModelCreator()
            model_params = {
                'api_base_url': params['croc_api_url'],
                'redis_db': redis_db,
                'ssl_verify': params.get('croc_ssl_verify', True),  # 🆕
                'poll_interval': params.get('croc_poll_interval', 2.0),
                'poll_timeout': params.get('croc_poll_timeout', 1800),
                'request_timeout': params.get('croc_request_timeout', 30),
            }

            return cls.create(creator, model_params)

        else:
            raise ValueError(f"Unsupported model type: {model_type}")