import os
from dotenv import load_dotenv


class Config:
    """Конфигурация сервиса из переменных окружения."""

    def __init__(self):
        # Загружаем переменные окружения при создании экземпляра
        load_dotenv()

        # NATS
        self.NATS_SERVERS = os.getenv("NATS_SERVERS", "nats://localhost:4222")

        # Redis
        self.REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
        self.REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
        self.REDIS_DB = int(os.getenv("REDIS_DB", "0"))
        self.REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

        # Модель - пути к файлам
        self.MODEL_TOKENS = os.getenv("MODEL_TOKENS", "../../models/vosk-model-streaming-ru/tokens.txt")
        self.MODEL_ENCODER = os.getenv("MODEL_ENCODER", "../../models/vosk-model-streaming-ru/encoder.onnx")
        self.MODEL_DECODER = os.getenv("MODEL_DECODER", "../../models/vosk-model-streaming-ru/decoder.onnx")
        self.MODEL_JOINER = os.getenv("MODEL_JOINER", "../../models/vosk-model-streaming-ru/joiner.onnx")

        # Параметры модели
        self.SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))
        self.MODEL_NUM_THREADS = int(os.getenv("MODEL_NUM_THREADS", "4"))
        self.FEATURE_DIM = int(os.getenv("FEATURE_DIM", "80"))
        self.DECODING_METHOD = os.getenv("DECODING_METHOD", "greedy_search")

        # Endpoint Detection
        self.ENABLE_ENDPOINT_DETECTION = os.getenv("ENABLE_ENDPOINT_DETECTION", "true").lower() == "true"
        self.RULE1_MIN_TRAILING_SILENCE = float(os.getenv("RULE1_MIN_TRAILING_SILENCE", "2.4"))
        self.RULE2_MIN_TRAILING_SILENCE = float(os.getenv("RULE2_MIN_TRAILING_SILENCE", "1.2"))
        self.RULE3_MIN_UTTERANCE_LENGTH = float(os.getenv("RULE3_MIN_UTTERANCE_LENGTH", "20.0"))

        # Топики
        self.BASE_TOPIC = os.getenv("BASE_TOPIC", "transcriber.sync")
        self.INIT_TOPIC = os.getenv("INIT_TOPIC", "transcriber.sync.init")
        self.PROCESSING_TOPIC_PREFIX = os.getenv("PROCESSING_TOPIC_PREFIX", "transcriber.sync.processing")
        self.RESPONSE_TOPIC_PREFIX = os.getenv("RESPONSE_TOPIC_PREFIX", "transcriber.sync.response")
        self.STATUS_TOPIC_PREFIX = os.getenv("STATUS_TOPIC_PREFIX", "transcriber.sync.status")

        # Сессии
        self.MAX_ACTIVE_STREAMS = int(os.getenv("MAX_ACTIVE_STREAMS", "100"))
        self.JOB_ACTIVE_TIMEOUT = int(os.getenv("JOB_ACTIVE_TIMEOUT", "20"))

        # Логирование
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

    # Properties для удобного доступа (lowercase)
    @property
    def nats_servers(self) -> str:
        return self.NATS_SERVERS

    @property
    def redis_host(self) -> str:
        return self.REDIS_HOST

    @property
    def redis_port(self) -> int:
        return self.REDIS_PORT

    @property
    def redis_db(self) -> int:
        return self.REDIS_DB

    @property
    def redis_password(self) -> str:
        return self.REDIS_PASSWORD

    @property
    def model_tokens(self) -> str:
        return self.MODEL_TOKENS

    @property
    def model_encoder(self) -> str:
        return self.MODEL_ENCODER

    @property
    def model_decoder(self) -> str:
        return self.MODEL_DECODER

    @property
    def model_joiner(self) -> str:
        return self.MODEL_JOINER

    @property
    def sample_rate(self) -> int:
        return self.SAMPLE_RATE

    @property
    def model_num_threads(self) -> int:
        return self.MODEL_NUM_THREADS

    @property
    def feature_dim(self) -> int:
        return self.FEATURE_DIM

    @property
    def decoding_method(self) -> str:
        return self.DECODING_METHOD

    @property
    def enable_endpoint_detection(self) -> bool:
        return self.ENABLE_ENDPOINT_DETECTION

    @property
    def rule1_min_trailing_silence(self) -> float:
        return self.RULE1_MIN_TRAILING_SILENCE

    @property
    def rule2_min_trailing_silence(self) -> float:
        return self.RULE2_MIN_TRAILING_SILENCE

    @property
    def rule3_min_utterance_length(self) -> float:
        return self.RULE3_MIN_UTTERANCE_LENGTH

    @property
    def base_topic(self) -> str:
        return self.BASE_TOPIC

    @property
    def init_topic(self) -> str:
        return self.INIT_TOPIC

    @property
    def processing_topic_prefix(self) -> str:
        return self.PROCESSING_TOPIC_PREFIX

    @property
    def response_topic_prefix(self) -> str:
        return self.RESPONSE_TOPIC_PREFIX

    @property
    def status_topic_prefix(self) -> str:
        return self.STATUS_TOPIC_PREFIX

    @property
    def max_active_streams(self) -> int:
        return self.MAX_ACTIVE_STREAMS

    @property
    def job_active_timeout(self) -> int:
        return self.JOB_ACTIVE_TIMEOUT

    @property
    def log_level(self) -> str:
        return self.LOG_LEVEL