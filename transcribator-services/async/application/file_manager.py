import asyncio
import os
from pathlib import Path
import shutil
from typing import List, Tuple
from fsspec import AbstractFileSystem
from .utils import download_file, extract_archive, generate_random_filename, run_with_timeout
from .classes import Request

DOWNLOAD_TIMEOUT = 300
EXTRACT_TIMEOUT = 300
MAX_ARCHIVE_SIZE = 100 * 1024 * 1024  # 100 МБ максимум для архива
MAX_ARCHIVE_UNCOMPRESSED_SIZE = 1_073_741_824  # 1 ГБ
MAX_ARCHIVE_FILES = 1000
MAX_COMPRESSION_RATIO = 100.0  # 1:100


class FileManager:
    """
    Manages downloading and extracting files from storage.
    """
    
    def __init__(self, storage: AbstractFileSystem, logger=None):
        
        self.storage = storage
        self.logger = logger or __import__('logging').getLogger(__name__)

    async def download_single_file(self, remote_path: str, job_temp_dir: str) -> Tuple[List[str], List[str]]:
        """
        Downloads a single file from remote storage.
        
        Args:
            remote_path: Path to the remote file
            job_temp_dir: Directory to download the file to
            
        Returns:
            Tuple of (list of local paths, list of errors)
        """
        local_paths = []
        errors = []
        
        local_filename = generate_random_filename()
        local_path = os.path.join(job_temp_dir, local_filename)

        try:
            coro = asyncio.to_thread(download_file, self.storage, remote_path, local_path)
            success, error = await run_with_timeout(
                coro,
                DOWNLOAD_TIMEOUT,
                f"Download single file {remote_path}"
            )
            if success:
                local_paths.append(local_path)
            else:
                errors.append(f"Failed to download {remote_path}: {error}")
        except TimeoutError as e:
            errors.append(f"Timeout downloading {remote_path}: {e}")
            
        return local_paths, errors

    async def download_and_extract_archive(self, remote_path: str, job_temp_dir: str) -> Tuple[List[str], List[str]]:
         """
         Downloads and extracts an archive from remote storage.

         Args:
             remote_path: Path to the remote archive
             job_temp_dir: Directory to extract the archive to

         Returns:
             Tuple of (list of local paths, list of errors)
         """
         local_paths = []
         errors = []

         # 🔑 Сохраняем оригинальное расширение из remote_path
         original_filename = os.path.basename(remote_path)
         ext = "".join(Path(original_filename).suffixes)  # поддержка .tar.gz, .zip и т.д.
         archive_local_name = generate_random_filename() + ext
         archive_local_path = os.path.join(job_temp_dir, archive_local_name)

         try:
             success, error = await run_with_timeout(
                 asyncio.to_thread(download_file, self.storage, remote_path, archive_local_path),
                 DOWNLOAD_TIMEOUT,
                 f"Download archive {remote_path}"
             )
             if not success:
                 errors.append(f"Failed to download archive {remote_path}: {error}")
                 return local_paths, errors
         except TimeoutError as e:
             errors.append(f"Timeout downloading archive {remote_path}: {e}")
             return local_paths, errors

         # 🔒 Слой 0: Проверка размера архива ДО распаковки
         archive_size = os.path.getsize(archive_local_path)
         if archive_size > MAX_ARCHIVE_SIZE:
             errors.append(
                 f"Archive too large: {archive_size / 1024 / 1024:.1f} MB > "
                 f"{MAX_ARCHIVE_SIZE / 1024 / 1024} MB limit"
             )
             return local_paths, errors

         extracted_dir = os.path.join(job_temp_dir, generate_random_filename())
         os.makedirs(extracted_dir, exist_ok=True)

         try:
             # Передаём параметры защиты в extract_archive
             extract_success, extract_error = await run_with_timeout(
                 asyncio.to_thread(
                     extract_archive,
                     archive_local_path,
                     extracted_dir,
                     max_total_size_bytes=MAX_ARCHIVE_UNCOMPRESSED_SIZE,
                     max_files=MAX_ARCHIVE_FILES,
                     max_compression_ratio=MAX_COMPRESSION_RATIO
                 ),
                 EXTRACT_TIMEOUT,
                 f"Extract archive {archive_local_path}"
             )
             if not extract_success:
                 errors.append(f"Failed to extract archive {remote_path}: {extract_error}")
                 return local_paths, errors
         except TimeoutError as e:
             errors.append(f"Timeout extracting archive {remote_path}: {e}")
             return local_paths, errors

         # Собираем распакованные файлы
         for idx, filename in enumerate(os.listdir(extracted_dir)):
             file_path = os.path.join(extracted_dir, filename)
             if os.path.isfile(file_path):
                 # 🔒 Дополнительная проверка: не исполняемый файл
                 if filename.lower().endswith(('.exe', '.bat', '.sh', '.py', '.js')):
                     errors.append(f"Executable files are not allowed: {filename}")
                     continue
                 
                 new_filename = f"{generate_random_filename()}_{idx}"
                 new_file_path = os.path.join(extracted_dir, new_filename)
                 os.rename(file_path, new_file_path)
                 local_paths.append(new_file_path)

         return local_paths, errors

    async def download_file_list(self, remote_paths: List[str], job_temp_dir: str) -> Tuple[List[str], List[str]]:
        """
        Downloads a list of files from remote storage.
        
        Args:
            remote_paths: List of paths to remote files
            job_temp_dir: Directory to download the files to
            
        Returns:
            Tuple of (list of local paths, list of errors)
        """
        local_paths = []
        errors = []
        
        for idx, remote_path in enumerate(remote_paths):
            local_filename = f"{generate_random_filename()}_{idx}"
            local_path = os.path.join(job_temp_dir, local_filename)

            try:
                coro = asyncio.to_thread(download_file, self.storage, remote_path, local_path)
                success, error = await run_with_timeout(
                    coro,
                    DOWNLOAD_TIMEOUT,
                    f"Download file {remote_path}"
                )
                if success:
                    local_paths.append(local_path)
                else:
                    errors.append(f"Failed to download {remote_path}: {error}")
            except TimeoutError as e:
                errors.append(f"Timeout downloading {remote_path}: {e}")
                
        return local_paths, errors
    
    async def upload_result_json(self, data: str, remote_path: str):
        with self.storage.open(remote_path, 'w') as file:
            file.write(data)

    async def download_audio_files(self, request: Request, job_temp_dir: str) -> Tuple[List[str], List[str]]:
        """
        Downloads audio files based on the request type.
        
        Args:
            request: The transcription request
            job_temp_dir: Directory to download files to
            
        Returns:
            Tuple of (list of local paths, list of errors)
        """
        if request.input_type == 'file':
            return await self.download_single_file(request.audio_source.path, job_temp_dir)
        elif request.input_type == 'archive':
            return await self.download_and_extract_archive(request.audio_source.archive, job_temp_dir)
        elif request.input_type == 'file_list':
            return await self.download_file_list(request.audio_source.file_list, job_temp_dir)
        
        return [], [f"Unknown input type: {request.input_type}"]