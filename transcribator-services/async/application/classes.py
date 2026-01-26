import datetime
from typing import List, Literal, Optional, Union
from .transcribation_model.segment import Segment


class AudioSource:
    path: Optional[str]
    archive: Optional[str]
    file_list: Optional[List[str]]

    def __init__(self, path: Optional[str] = None, archive: Optional[str] = None, file_list: Optional[List[str]] = None):
        self.path = path
        self.archive = archive
        self.file_list = file_list

class Request:
    job_id: str
    input_type: Literal['file', 'archive', 'file_list']
    audio_source: AudioSource
    created_at: datetime.datetime

    def __init__(self, job_id: str, input_type: Literal['file', 'archive', 'file_list'], audio_source: AudioSource, created_at: datetime.datetime):
        self.job_id = job_id
        self.input_type = input_type
        self.audio_source = audio_source
        self.created_at = created_at

class RequestParsingError(Exception):
    """Исключение, возникающее при ошибке парсинга входящего запроса из очереди."""

    def __init__(self, message: str, job_id: str = "unknown"):
        super().__init__(message)
        self.message = message
        self.job_id = job_id

    def __str__(self):
        return f"RequestParsingError(job_id='{self.job_id}'): {self.message}"


class Result:
    def __init__(self, segments: List[Segment], error: Union[str, None] = None):
        self.segments = segments
        self.error = error

class Response:
    def __init__(self, job_id: str, status: Literal['completed', 'failed'], completed_at: datetime.datetime,
                 results: Optional[List[Result]] = None, error: Union[str, None] = None):
        self.job_id = job_id
        self.status = status
        self.completed_at = completed_at
        self.results = results
        self.error = error
    
