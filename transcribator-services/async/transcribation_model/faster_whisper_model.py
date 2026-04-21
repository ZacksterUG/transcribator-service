from typing import List, Optional, Dict, Any
from io import BytesIO
import librosa
from faster_whisper import WhisperModel

from .interfaces import IModel, IModelCreator
from .classes import TranscriptionRequest, TranscriptionError, Segment, Word, ModelNotReadyError


class FasterWhisperModel(IModel):
    """
    Реализация IModel для модели Whisper с использованием библиотеки faster-whisper
    """
    
    def __init__(self, model_size_or_path: str = "base", device: str = "cpu", 
                 compute_type: str = "float32", num_workers: int = 1, **kwargs):
        """
        Инициализирует модель Whisper
        
        Args:
            model_size_or_path: Размер модели (tiny, base, small, medium, large, large-v1, large-v2, turbo) 
                               или путь к модели
            device: Устройство для вычислений (cpu, cuda)
            compute_type: Тип вычислений (float32, float16, int8_float16)
            num_workers: Количество воркеров для декодирования
            **kwargs: Дополнительные параметры для WhisperModel
        """
        self._model_size_or_path = model_size_or_path
        self._device = device
        self._compute_type = compute_type
        self._num_workers = num_workers
        self._model: Optional[WhisperModel] = None
        self._model_name = f"faster-whisper-{model_size_or_path}"
        self._model_version = "1.0.0"
        
        # Дополнительные параметры
        self._extra_kwargs = kwargs
        
        # Загружаем модель
        try:
            
            self._model = WhisperModel(
                model_size_or_path=model_size_or_path,
                device=device,
                compute_type=compute_type,
                num_workers=num_workers,
                **kwargs
            )
        except Exception as e:
            raise ModelNotReadyError(f"Failed to initialize Whisper model: {str(e)}")
    
    def predict(self, request: TranscriptionRequest, ctx: Any = None) -> List[Segment]:
        """
        Выполняет транскрибацию аудио
        
        Args:
            request: Запрос на транскрибацию с аудио и параметрами
            ctx: Заданный контекст для модели
            
        Returns:
            Список сегментов транскрибации
            
        Raises:
            TranscriptionError: При ошибках транскрибации
            InvalidAudioError: При некорректном аудио
        """
        if not self._model:
            raise ModelNotReadyError("Model is not initialized")
        
        try:
            # Загружаем аудио из байтов
            audio_buffer = BytesIO(request.audio_bytes)
            
            # Загружаем аудио с помощью librosa
            audio_array, sample_rate = librosa.load(audio_buffer, sr=request.sample_rate)
            
            # Подготовка параметров для транскрибации
            whisper_options = {
                "beam_size": 5,
                "vad_filter": request.vad_filter,
                "temperature": request.temperature,
            }
            
            # Добавляем язык, если указан
            if request.language:
                whisper_options["language"] = request.language
            
            # Выполняем транскрибацию
            segments, info = self._model.transcribe(
                audio_array,
                **whisper_options
            )
            
            # Преобразуем результаты в список сегментов
            result_segments = []
            for idx, segment in enumerate(segments):
                # Преобразуем слова, если они доступны
                words = None
                if hasattr(segment, 'words') and segment.words:
                    words = [
                        Word(
                            start=word.start,
                            end=word.end,
                            word=word.word,
                            probability=getattr(word, 'probability', 0.0)
                        ) for word in segment.words
                    ]
                
                # Создаем объект сегмента
                result_segment = Segment(
                    id=idx,
                    seek = getattr(segment, 'seek', 0),
                    start = segment.start,
                    end = segment.end,
                    text = segment.text,
                    tokens = getattr(segment, 'tokens', []),
                    avg_logprob = getattr(segment, 'avg_logprob', 0.0),
                    compression_ratio = getattr(segment, 'compression_ratio', 0.0),
                    no_speech_prob = getattr(segment, 'no_speech_prob', 0.0),
                    words = words,
                    temperature = getattr(segment, 'temperature', request.temperature),
                )

                result_segments.append(result_segment)
            
            return result_segments
            
        except Exception as e:
            raise TranscriptionError(f"Transcription failed: {str(e)}")
    
    def health_check(self) -> bool:
        """
        Проверяет, готова ли модель к работе
        
        Returns:
            True, если модель готова, иначе False
        """
        if self._model is not None: return True
        
        raise ModelNotReadyError("Model is not initialized")
    
    @property
    def model_name(self) -> str:
        """Возвращает имя модели"""
        return self._model_name
    
    @property
    def model_version(self) -> str:
        """Возвращает версию модели"""
        return self._model_version
    
    def warmup(self, request: Optional[TranscriptionRequest] = None) -> None:
        """
        Прогрев модели (опционально)
        """
        # Можно выполнить прогрев, если передан тестовый запрос
        if request:
            try:
                _ = self.predict(request)
            except:
                pass  # Игнорируем ошибки во время прогрева
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Освобождаем ресурсы модели, если необходимо
        self._model = None


class FasterWhisperCreator(IModelCreator):
    """
    Класс-создатель для модели FasterWhisper
    """
    
    def create_model(self, params: Dict[str, Any]) -> IModel:
        """
        Создаёт экземпляр модели FasterWhisper на основе переданных параметров.
        
        Args:
            params: Словарь параметров для инициализации модели
                   Поддерживаемые параметры:
                   - model_size_or_path: размер модели или путь к модели (по умолчанию "base")
                   - device: устройство для вычислений (по умолчанию "cpu")
                   - compute_type: тип вычислений (по умолчанию "float32")
                   - num_workers: количество воркеров (по умолчанию 1)
                   - и другие дополнительные параметры для WhisperModel
        
        Returns:
            Экземпляр класса FasterWhisperModel
        """
        # Извлекаем параметры с значениями по умолчанию
        model_size_or_path = params.get("model_size_or_path", "base")
        device = params.get("device", "cpu")
        compute_type = params.get("compute_type", "float32")
        num_workers = params.get("num_workers", None)
        
        # Остальные параметры передаем как есть
        extra_params = {k: v for k, v in params.items() 
                       if k not in ["model_size_or_path", "device", "compute_type", "num_workers"]}
        
        # Создаем и возвращаем экземпляр модели
        return FasterWhisperModel(
            model_size_or_path=model_size_or_path,
            device=device,
            compute_type=compute_type,
            num_workers=num_workers,
            **extra_params
        )