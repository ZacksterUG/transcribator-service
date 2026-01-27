

import asyncio
from functools import wraps
from io import BytesIO
import json
import os
import random
import shutil
import string
import tarfile
import time
import zipfile

from fsspec import AbstractFileSystem
import librosa
import numpy as np
from .classes import *


def generate_random_filename(length=64):
    """Генерирует случайное имя файла заданной длины"""
    letters = string.ascii_letters + string.digits
    return ''.join(random.choice(letters) for _ in range(length))

def convert_audio_to_16khz(audio_path: str):
    """Конвертирует аудиофайл в 16 кГц и возвращает байты"""
    try:
        # Загружаем аудио с помощью librosa
        audio_data, original_sr = librosa.load(audio_path, sr=16000)

        # Конвертируем в байты
        audio_bytes_io = BytesIO()
        # librosa не записывает в BytesIO напрямую, поэтому используем scipy
        from scipy.io import wavfile
        wavfile.write(audio_bytes_io, 16000, (audio_data * 32767).astype(np.int16))

        return audio_bytes_io.getvalue()
    except Exception as e:
        raise Exception(f"Failed to convert audio to 16kHz: {str(e)}")
    
def extract_archive(    archive_path: str, 
    extract_to: str,
    max_total_size_bytes: int = 1_073_741_824,  # 1 ГБ по умолчанию
    max_files: int = 1000,
    max_compression_ratio: float = 100.0  # 1:100 — подозрительно
    ):
    """
    Распаковывает архив с защитой от zip-bomb атак.
    
    Args:
        archive_path: Путь к архиву
        extract_to: Целевая директория
        max_total_size_bytes: Максимальный общий размер распакованных файлов
        max_files: Максимальное количество файлов в архиве
        max_compression_ratio: Максимальное соотношение сжатия (распакованный_размер / архив_размер)
    
    Returns:
        (успех: bool, ошибка: str | None)
    """
    try:
        extract_to = os.path.abspath(extract_to)
        os.makedirs(extract_to, exist_ok=True)
        
        archive_size = os.path.getsize(archive_path)
        
        # 🔒 Слой 1: Быстрая проверка соотношения сжатия ДО распаковки
        if archive_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                # Проверяем количество файлов
                if len(zip_ref.namelist()) > max_files:
                    return False, f"Too many files in archive: {len(zip_ref.namelist())} > {max_files}"
                
                # Предварительная оценка общего размера
                total_uncompressed = sum(info.file_size for info in zip_ref.infolist())
                
                # Проверка соотношения сжатия
                if archive_size > 0:
                    ratio = total_uncompressed / archive_size
                    if ratio > max_compression_ratio:
                        return False, (
                            f"Suspicious compression ratio: {ratio:.1f}x "
                            f"({total_uncompressed / 1024 / 1024:.1f} MB uncompressed vs "
                            f"{archive_size / 1024 / 1024:.1f} MB archive)"
                        )
                
                # Проверка общего размера
                if total_uncompressed > max_total_size_bytes:
                    return False, (
                        f"Total uncompressed size exceeds limit: "
                        f"{total_uncompressed / 1024 / 1024:.1f} MB > "
                        f"{max_total_size_bytes / 1024 / 1024:.1f} MB"
                    )
                
                # 🔒 Слой 2: Распаковка с контролем размера в реальном времени
                accumulated_size = 0
                for member in zip_ref.namelist():
                    member_path = os.path.join(extract_to, member)
                    
                    # Защита от path traversal
                    if not os.path.abspath(member_path).startswith(extract_to):
                        return False, f"Path traversal detected: {member}"
                    
                    # Получаем информацию о файле
                    info = zip_ref.getinfo(member)
                    
                    # Пропускаем директории
                    if info.is_dir():
                        os.makedirs(member_path, exist_ok=True)
                        continue
                    
                    # Контроль накопленного размера
                    accumulated_size += info.file_size
                    if accumulated_size > max_total_size_bytes:
                        return False, (
                            f"Extraction aborted: total size would exceed "
                            f"{max_total_size_bytes / 1024 / 1024:.1f} MB limit"
                        )
                    
                    # Распаковываем файл по частям для контроля памяти
                    with zip_ref.open(member) as source, open(member_path, 'wb') as target:
                        while True:
                            chunk = source.read(8192)
                            if not chunk:
                                break
                            target.write(chunk)
        
        elif archive_path.endswith(('.tar', '.tar.gz', '.tgz')):
            with tarfile.open(archive_path, 'r') as tar_ref:
                members = tar_ref.getmembers()
                
                # Проверка количества файлов
                if len(members) > max_files:
                    return False, f"Too many files in archive: {len(members)} > {max_files}"
                
                # Предварительная оценка размера
                total_uncompressed = sum(m.size for m in members if m.isfile())
                
                # Проверка соотношения сжатия
                if archive_size > 0:
                    ratio = total_uncompressed / archive_size if archive_size > 0 else 0
                    if ratio > max_compression_ratio:
                        return False, (
                            f"Suspicious compression ratio: {ratio:.1f}x "
                            f"({total_uncompressed / 1024 / 1024:.1f} MB uncompressed vs "
                            f"{archive_size / 1024 / 1024:.1f} MB archive)"
                        )
                
                # Проверка общего размера
                if total_uncompressed > max_total_size_bytes:
                    return False, (
                        f"Total uncompressed size exceeds limit: "
                        f"{total_uncompressed / 1024 / 1024:.1f} MB > "
                        f"{max_total_size_bytes / 1024 / 1024:.1f} MB"
                    )
                
                # 🔒 Слой 2: Распаковка с контролем
                accumulated_size = 0
                for member in members:
                    member_path = os.path.join(extract_to, member.name)
                    
                    # Защита от path traversal
                    if not os.path.abspath(member_path).startswith(extract_to):
                        return False, f"Path traversal detected: {member.name}"
                    
                    # Пропускаем символические ссылки (потенциальная уязвимость)
                    if member.issym() or member.islnk():
                        continue
                    
                    if member.isfile():
                        accumulated_size += member.size
                        if accumulated_size > max_total_size_bytes:
                            return False, (
                                f"Extraction aborted: total size would exceed "
                                f"{max_total_size_bytes / 1024 / 1024:.1f} MB limit"
                            )
                        
                        # Извлекаем с контролем памяти
                        tar_ref.extract(member, extract_to)
                        # Устанавливаем правильные права (без выполнения)
                        if os.path.isfile(member_path):
                            os.chmod(member_path, 0o644)
        
        else:
            return False, f"Unsupported archive format: {archive_path}"
        
        return True, None
    
    except Exception as e:
        return False, f"Extraction failed: {str(e)}"
    
def download_file(storage: AbstractFileSystem, remote_path: str, local_path: str):
    """Скачивает файл из удаленного хранилища в локальный путь"""
    try:
        with storage.open(remote_path, 'rb') as remote_file:
            with open(local_path, 'wb') as local_file:
                local_file.write(remote_file.read())
        return True, None
    except Exception as e:
        return False, str(e)
    

def request_from_binary(data: bytes) -> Request:
    """
    Десериализует бинарные данные в объект Request.
    Выбрасывает ValueError, если структура неверна.
    """
    try:
        data_str = data.decode('utf-8')
        data_json = json.loads(data_str)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"Failed to decode request: {e}")

    # Проверка обязательных полей
    required_fields = ['job_id', 'input_type', 'audio_source', 'created_at']
    for field in required_fields:
        if field not in data_json:
            raise ValueError(f"Missing required field: {field}")

    job_id = data_json['job_id']
    input_type = data_json['input_type']
    audio_source_data = data_json['audio_source']
    created_at_str = data_json['created_at']

    # Валидация job_id
    if not isinstance(job_id, str) or len(job_id.strip()) == 0:
        raise ValueError("job_id must be a non-empty string")

    # Валидация input_type
    if input_type not in ('file', 'archive', 'file_list'):
        raise ValueError(f"Invalid input_type: {input_type}. Must be one of: file, archive, file_list")

    # Валидация created_at
    try:
        created_at = datetime.datetime.fromisoformat(created_at_str)
    except ValueError as e:
        raise ValueError(f"Invalid created_at format: {created_at_str}") from e

    # Валидация audio_source в зависимости от input_type
    if input_type == 'file':
        if not isinstance(audio_source_data, dict):
            raise ValueError("audio_source must be an object for input_type='file'")
        path = audio_source_data.get('path')
        if not isinstance(path, str) or len(path.strip()) == 0:
            raise ValueError("audio_source.path is required and must be a non-empty string for input_type='file'")
        audio_source = AudioSource(path=path)

    elif input_type == 'archive':
        if not isinstance(audio_source_data, dict):
            raise ValueError("audio_source must be an object for input_type='archive'")
        archive = audio_source_data.get('archive')
        if not isinstance(archive, str) or len(archive.strip()) == 0:
            raise ValueError("audio_source.archive is required and must be a non-empty string for input_type='archive'")
        audio_source = AudioSource(archive=archive)

    elif input_type == 'file_list':
        if not isinstance(audio_source_data, dict):
            raise ValueError("audio_source must be an object for input_type='file_list'")
        file_list = audio_source_data.get('file_list')
        if not isinstance(file_list, list):
            raise ValueError("audio_source.file_list is required and must be a list for input_type='file_list'")
        if len(file_list) == 0:
            raise ValueError("audio_source.file_list cannot be empty")
        MAX_FILE_LIST_LENGTH = 100
        if len(file_list) > MAX_FILE_LIST_LENGTH:
            raise ValueError(f"audio_source.file_list too long: {len(file_list)} > {MAX_FILE_LIST_LENGTH}")

        for i, item in enumerate(file_list):
            if not isinstance(item, str) or len(item.strip()) == 0:
                raise ValueError(f"audio_source.file_list[{i}] must be a non-empty string")
        audio_source = AudioSource(file_list=file_list)

    else:
        # На случай, если добавится новый тип — не должно сработать
        raise ValueError(f"Unknown input_type: {input_type}")

    return Request(
        job_id=job_id,
        input_type=input_type,
        audio_source=audio_source,
        created_at=created_at
    )

def serialize_results(results: list[Result]) -> list[dict]:
    serialized = []
    for result in results:
        result_dict = {'error': result.error, 'segments': []}
        for seg in result.segments:
            seg_dict = {
                'id': seg.id,
                'seek': seg.seek,
                'start': seg.start,
                'end': seg.end,
                'text': seg.text,
                'tokens': seg.tokens,
                'avg_logprob': seg.avg_logprob,
                'compression_ratio': seg.compression_ratio,
                'no_speech_prob': seg.no_speech_prob,
                'temperature': seg.temperature
            }
            if hasattr(seg, 'words') and seg.words:
                seg_dict['words'] = [
                    {'start': w.start, 'end': w.end, 'word': w.word, 'probability': w.probability}
                    for w in seg.words
                ]
            result_dict['segments'].append(seg_dict)
        serialized.append(result_dict)
    return serialized

def serialize_response(response: Response) -> bytes:
    response_dict = {
        'job_id': response.job_id,
        'status': response.status,
        'completed_at': response.completed_at.isoformat(),
        'results': serialize_results(response.results)
    }
    if response.error:
        response_dict['error'] = response.error
    return json.dumps(response_dict, ensure_ascii=False).encode('utf-8')

def extract_job_id_from_invalid_request(request_data: bytes) -> str:
    try:
        data_str = request_data.decode('utf-8')
        data_json = json.loads(data_str)
        if isinstance(data_json.get('job_id'), str):
            return data_json['job_id']
    except Exception:
        pass
    return "unknown"

def with_timeout(timeout_seconds: int):
    """Декоратор для добавления таймаута к асинхронной функции"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Operation timed out after {timeout_seconds} seconds")
        return wrapper
    return decorator

async def run_with_timeout(coro, timeout_seconds: int, operation_name: str = "operation"):
    """Утилита для запуска корутины с таймаутом и логированием"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise TimeoutError(f"{operation_name} timed out after {timeout_seconds} seconds")