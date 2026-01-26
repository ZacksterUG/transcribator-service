from typing import Optional

class TranscriptionRequest:
    audio_bytes: bytes
    language: Optional[str] = None
    temperature: float = 0.0
    sample_rate: int = 16000
    vad_filter: bool = True

    def __init__(self, audio_bytes: bytes, temperature: float, sample_rate: int, vad_filter: bool, language: str = None):
        self.audio_bytes = audio_bytes
        self.temperature = temperature
        self.sample_rate = sample_rate
        self.vad_filter = vad_filter
        self.language = language
        