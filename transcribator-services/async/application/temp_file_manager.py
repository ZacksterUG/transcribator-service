import os
import time
import shutil
from typing import Optional
import asyncio
from .utils import generate_random_filename, run_with_timeout

CLEANUP_TIMEOUT = 60


class TempFileManager:
    """
    Manages temporary files and directories for the transcriber service.
    """
    
    def __init__(self, temp_dir: str = './temp', logger=None):
        self.temp_dir = temp_dir
        self.logger = logger or __import__('logging').getLogger(__name__)
        os.makedirs(self.temp_dir, exist_ok=True)

    def prepare_job_directory(self, job_id: str) -> str:
        """
        Creates a temporary directory for a job.
        
        Args:
            job_id: ID of the job
            
        Returns:
            Path to the job's temporary directory
        """
        job_temp_dir = os.path.join(self.temp_dir, job_id)
        os.makedirs(job_temp_dir, exist_ok=True)
        return job_temp_dir

    def _cleanup_old_temp_dirs_sync(self, temp_dir: str, max_age_hours: int = 8):
        """
        Synchronously removes old temporary directories.
        
        Args:
            temp_dir: Directory to clean up
            max_age_hours: Maximum age in hours for keeping directories
        """
        if not os.path.exists(temp_dir):
            return

        now = time.time()
        cutoff = now - (max_age_hours * 3600)

        for entry in os.scandir(temp_dir):
            if not entry.is_dir():
                continue

            try:
                if entry.stat().st_mtime < cutoff:
                    self.logger.info(f"🧹 Removing old temp dir: {entry.path}")
                    shutil.rmtree(entry.path, ignore_errors=True)
            except (OSError, FileNotFoundError) as e:
                self.logger.warning(f"⚠️ Failed to remove old temp dir {entry.path}: {e}")

    async def cleanup_old_temp_dirs(self, temp_dir: Optional[str] = None, max_age_hours: int = 8):
        """
        Removes old temporary directories asynchronously.
        
        Args:
            temp_dir: Directory to clean up (uses self.temp_dir if not provided)
            max_age_hours: Maximum age in hours for keeping directories
        """
        cleanup_dir = temp_dir or self.temp_dir
        try:
            await run_with_timeout(
                asyncio.to_thread(self._cleanup_old_temp_dirs_sync, cleanup_dir, max_age_hours),
                CLEANUP_TIMEOUT,
                "Cleanup old temp directories"
            )
        except TimeoutError as e:
            self.logger.warning(f"Timeout during cleanup: {e}")