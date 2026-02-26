from enum import Enum, auto


class ModelType(Enum):
    FASTER_WHISPER = auto()  # Локальная модель через faster-whisper
    CROC_WHISPER = auto()  # Внешний API whisper.croc.ru

    @classmethod
    def from_string(cls, value: str) -> 'ModelType':
        mapping = {
            'faster-whisper': cls.FASTER_WHISPER,
            'faster_whisper': cls.FASTER_WHISPER,
            'croc-whisper': cls.CROC_WHISPER,
            'croc_whisper': cls.CROC_WHISPER,
        }
        if value not in mapping:
            raise ValueError(f"Unknown model type: {value}. Allowed: {list(mapping.keys())}")
        return mapping[value]