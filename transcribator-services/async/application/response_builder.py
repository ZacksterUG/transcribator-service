import datetime
from typing import List
from .classes import Response, Result
from .utils import serialize_response


class ResponseBuilder:
    """
    Builds response objects for the transcriber service.
    """
    
    def __init__(self, response_topic: str, queue, logger=None):
        self.response_topic = response_topic
        self.queue = queue
        self.logger = logger or __import__('logging').getLogger(__name__)

    def build_response(self, job_id: str, results: List[Result], download_errors: List[str] = None) -> Response:
        """
        Builds a response object.
        
        Args:
            job_id: ID of the job
            results: List of result objects
            download_errors: List of download errors (if any)
            
        Returns:
            Response object
        """
        error = None
        if download_errors:
            error = f"Some files had download errors: {download_errors}"
        return Response(
            job_id=job_id,
            status='completed',
            completed_at=datetime.datetime.now(),
            results=results,
            error=error
        )
    
    def build_error_response(self, job_id: str, error_message: str) -> Response:
        return Response(
            job_id=job_id,
            status="failed",
            completed_at=datetime.datetime.now(datetime.timezone.utc),
            results=[],
            error=error_message
        )

    async def send_error_response(self, job_id: str, error_msg: str):
        """
        Sends an error response to the response topic.
        
        Args:
            job_id: ID of the job
            error_msg: Error message to send
        """
        error_response = Response(
            job_id=job_id,
            status='failed',
            completed_at=datetime.datetime.now(),
            results=[],
            error=error_msg
        )
        response_bytes = serialize_response(error_response)
        await self.queue.publish(self.response_topic, response_bytes)