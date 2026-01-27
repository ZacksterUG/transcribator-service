import asyncio
import datetime
from typing import List
from .transcribation_model.model import IModel
from .transcribation_model.request import TranscriptionRequest
from .utils import convert_audio_to_16khz, run_with_timeout
from .classes import Result

TRANSCRIPTION_TIMEOUT = 1800


class AudioProcessor:
    """
    Processes audio files by converting them and running transcription.
    """
    
    def __init__(self, model: IModel, logger=None):
        self.model = model
        self.logger = logger or __import__('logging').getLogger(__name__)

    async def process_audio_file(self, local_path: str, language=None, temperature=0.0, vad_filter=True) -> Result:
        """
        Processes a single audio file by converting it and running transcription.
        
        Args:
            local_path: Path to the local audio file
            language: Language for transcription
            temperature: Temperature setting for model
            vad_filter: Whether to use VAD filter
            
        Returns:
            Result object with transcription segments or error
        """
        try:
            audio_bytes_coro = asyncio.to_thread(convert_audio_to_16khz, local_path)
            audio_bytes = await run_with_timeout(
                audio_bytes_coro,
                TRANSCRIPTION_TIMEOUT // 2,
                f"Convert audio {local_path}"
            )

            transcription_request = TranscriptionRequest(
                audio_bytes=audio_bytes,
                language=language,
                temperature=temperature,
                sample_rate=16000,
                vad_filter=vad_filter
            )

            segments_coro = asyncio.to_thread(self.model.predict, transcription_request)
            segments = await run_with_timeout(
                segments_coro,
                TRANSCRIPTION_TIMEOUT,
                f"Transcribe {local_path}"
            )

            return Result(segments=segments, error=None)

        except TimeoutError as e:
            return Result(segments=[], error=f"Timeout processing file {local_path}: {str(e)}")
        except Exception as e:
            return Result(segments=[], error=f"Error processing file {local_path}: {str(e)}")

    async def process_audio_files(self, local_paths: List[str], request) -> List[Result]:
        """
        Processes multiple audio files.
        
        Args:
            local_paths: List of paths to local audio files
            request: The original request containing settings
            
        Returns:
            List of Result objects
        """
        results = []
        for local_path in local_paths:
            result = await self.process_audio_file(
                local_path,
                language=getattr(request, 'language', None),
                temperature=getattr(request, 'temperature', 0.0),
                vad_filter=getattr(request, 'vad_filter', True)
            )
            results.append(result)
            
        return results