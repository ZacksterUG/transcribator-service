import os
from typing import Optional, Dict, Any
from .enums import ModelType


def _required(key: str) -> str:
    val = os.getenv(key)
    if val is None:
        raise ValueError(f"Required env var not set: {key}")
    return val


def _optional(key: str, default: str) -> str:
    return os.getenv(key, default)


def _to_bool(val: str) -> bool:
    return val.lower() in ('true', '1', 'yes', 'on')


def load_config() -> Dict[str, Any]:
    """Загружает конфигурацию из ENV. Возвращает плоский dict для совместимости с фабриками."""

    model_type = ModelType.from_string(_required('MODEL_TYPE'))

    # Базовые параметры
    config = {
        'model_type': model_type,
        'nats_servers': _required('NATS_SERVERS'),
        'nats_verbose': _to_bool(_optional('NATS_VERBOSE', 'True')),
        'nats_pedantic': _to_bool(_optional('NATS_PEDANTIC', 'False')),
        'nats_jetstream': _to_bool(_optional('NATS_USE_JETSTREAM', 'True')),
        'minio_url': _required('MINIO_URL'),
        'minio_user': _required('MINIO_USER'),
        'minio_password': _required('MINIO_PASSWORD'),
        'minio_bucket': _required('MINIO_BUCKET'),
        'redis_host': _required('REDIS_HOST'),
        'redis_port': int(_required('REDIS_PORT')),
        'redis_db': int(_optional('REDIS_DB', '0')),
        'redis_password': os.getenv('REDIS_PASSWORD'),
        'request_topic': _required('REQUEST_TOPIC'),
        'response_topic': _required('RESPONSE_TOPIC'),
        'temp_dir': _required('TEMP_DIR'),
        'debug': _to_bool(_optional('DEBUG', 'False')),
        'log_level': _optional('LOG_LEVEL', 'INFO'),
    }

    # Параметры модели — только нужные для выбранного типа
    if model_type == ModelType.FASTER_WHISPER:
        config.update({
            'model_path_or_size': _required('MODEL_PATH_OR_SIZE'),
            'model_device': _required('MODEL_DEVICE'),
            'model_compute_type': _required('MODEL_COMPUTE_TYPE'),
            'model_num_workers': int(_optional('MODEL_NUM_WORKERS', '1')),
        })
    elif model_type == ModelType.CROC_WHISPER:
        config.update({
            'croc_api_url': _required('CROC_API_URL'),
            'croc_ssl_verify': _to_bool(_optional('CROC_SSL_VERIFY', 'True')),  # 🆕
            'croc_poll_interval': float(_optional('CROC_POLL_INTERVAL', '2.0')),
            'croc_poll_timeout': int(_optional('CROC_POLL_TIMEOUT', '1800')),
            'croc_request_timeout': int(_optional('CROC_REQUEST_TIMEOUT', '30')),
        })

    return config