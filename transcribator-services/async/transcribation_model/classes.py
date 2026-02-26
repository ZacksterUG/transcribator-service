from typing import Optional, Any
from typing import List, Optional

class Word:
    start: float
    end: float
    word: str
    probability: float
    def __init__(self, start: float, end: float, word: str, probability: float):
        self.start = start
        self.end = end
        self.word = word
        self.probability = probability

class Segment:
    id: int
    seek: int
    start: float
    end: float
    text: str
    tokens: List[int]
    avg_logprob: float
    compression_ratio: float
    no_speech_prob: float
    words: Optional[List[Word]]
    temperature: Optional[float]
    def __init__(self, id: int, seek:int, start: float, end: float, text: str, tokens: List[int],
                 avg_logprob: float, compression_ratio: float, no_speech_prob: float,
                 words: Optional[List[Word]], temperature: Optional[float]) -> None:
        self.id = id
        self.seek = seek
        self.start = start
        self.end = end
        self.text = text
        self.tokens = tokens
        self.avg_logprob = avg_logprob
        self.compression_ratio = compression_ratio
        self.no_speech_prob = no_speech_prob
        self.words = words
        self.temperature = temperature


class TranscriptionRequest:
    audio_bytes: bytes
    language: Optional[str] = None
    temperature: float = 0.0
    sample_rate: int = 16000
    vad_filter: bool = True
    ctx: Optional[Any] = None

    def __init__(self, audio_bytes: bytes, temperature: float, sample_rate: int, vad_filter: bool, language: str = None,
                 ctx: Any = None):
        self.audio_bytes = audio_bytes
        self.temperature = temperature
        self.sample_rate = sample_rate
        self.vad_filter = vad_filter
        self.language = language
        self.ctx = ctx


class TranscriptionError(Exception):
    pass

class ModelNotReadyError(TranscriptionError):
    pass

class InvalidAudioError(TranscriptionError):
    pass