import time
import hashlib
import logging
from logging import Logger
from typing import List, Optional, Any, Dict

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from database.dictionary_db.database import DictionaryDatabase

from .interfaces import IModel, IModelCreator
from .classes import TranscriptionRequest, TranscriptionError, Segment, Word


logger = logging.getLogger(__name__)


class CrocWhisperModel(IModel):
    """
    Модель-адаптер для внешнего API whisper.croc.ru.

    Особенности:
    • Идемпотентность: один файл → один task_id через хэш + job_id
    • Отказоустойчивость: при перезапуске реплики продолжается polling
    • Масштабируемость: несколько файлов в job_id не конфликтуют
    • Production-ready: retry, таймауты, health-check, graceful shutdown
    """

    def __init__(
            self,
            api_base_url: str,
            redis_db: Any,
            poll_interval: float = 2.0,
            poll_timeout: int = 1800,
            request_timeout: int = 30,
            ssl_verify: bool = True,  # 🆕
            model_name: str = "croc-whisper",
            model_version: str = "1.0.0",
    ):
        self.api_base_url = api_base_url.rstrip('/')
        self.redis = redis_db
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout
        self.request_timeout = request_timeout
        self.ssl_verify = ssl_verify  # 🆕
        self._model_name = model_name
        self._model_version = model_version

        self._session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=['POST', 'GET']
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount('http://', adapter)
        self._session.mount('https://', adapter)

    # ───────── Redis-ключи ─────────
    def _key_tasks(self, job_id: str) -> str:
        """SET со всеми task_id для job_id: async-jobs:<job_id>:api_tasks"""
        return f"async-jobs:{job_id}:api_tasks"

    def _key_result(self, job_id: str) -> str:
        """Кэш итогового результата: async-jobs:<job_id>"""
        return f"async-jobs:{job_id}"

    def _key_mapping(self, job_id: str, file_hash: str) -> str:
        """Маппинг файл → task_id: async-jobs:<job_id>:file_map:<hash>"""
        return f"async-jobs:{job_id}:file_map:{file_hash}"

    # ───────── Вспомогательные методы ─────────
    def _file_hash(self, audio_bytes: bytes) -> str:
        """Короткий хэш файла для идемпотентности."""
        return hashlib.sha256(audio_bytes).hexdigest()[:16]

    def _get_existing_task(self, job_id: str, fhash: str) -> Optional[str]:
        """Проверяет, есть ли уже запущенная задача для этого файла."""
        return self.redis.get(self._key_mapping(job_id, fhash))

    def _register_task(self, job_id: str, fhash: str, task_id: str) -> bool:
        """Сохраняет task_id в Redis для восстановления после сбоя."""
        try:
            # Маппинг файл → task_id (TTL 1 час)
            if not self.redis.set(self._key_mapping(job_id, fhash), task_id, ttl=600):
                return False
            # Добавляем в SET всех задач job_id (для мониторинга/отладки)
            tasks_key = self._key_tasks(job_id)
            existing = self.redis.get(tasks_key) or []
            if not isinstance(existing, list):
                existing = []
            if task_id not in existing:
                existing.append(task_id)
                self.redis.set(tasks_key, existing, ttl=600)
            return True
        except Exception as e:
            logger.error(f"Redis register failed: {e}")
            return False

    def _submit(self, audio_bytes: bytes, language: Optional[str]) -> str:
        url = f"{self.api_base_url}/gateway/transcribe"
        files = {'file': ('audio.wav', audio_bytes, 'audio/wav')}
        data = {'language': language} if language else {}

        try:
            # 🆕 Передаём ssl_verify во все запросы
            resp = self._session.post(url, files=files, data=data, timeout=self.request_timeout, verify=self.ssl_verify)
            resp.raise_for_status()
            result = resp.json()
            if not result.get('task_id'):
                raise TranscriptionError(f"API missing task_id: {result}")
            return result['task_id']
        except requests.RequestException as e:
            raise TranscriptionError(f"Submit failed: {e}")

    def _poll(self, task_id: str) -> Dict[str, Any]:
        url = f"{self.api_base_url}/gateway/status/{task_id}"
        try:
            resp = self._session.get(url, timeout=self.request_timeout, verify=self.ssl_verify)  # 🆕
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            raise TranscriptionError(f"Poll failed: {e}")

    def _fetch_result(self, task_id: str) -> Dict[str, Any]:
        url = f"{self.api_base_url}/gateway/results/{task_id}/json"
        try:
            resp = self._session.get(url, timeout=self.request_timeout, verify=self.ssl_verify)  # 🆕
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            raise TranscriptionError(f"Fetch failed: {e}")

    def _parse(self, api_result: Dict[str, Any]) -> List[Segment]:
        """Конвертация ответа API в доменные объекты."""
        segments = []
        for i, seg in enumerate(api_result.get('segments', [])):
            words = [
                Word(
                    start=w['start'],
                    end=w['end'],
                    word=w['word'],
                    probability=w.get('score', w.get('probability', 0.0))
                    # ⚠️ API возвращает 'speaker', но Word пока не поддерживает.
                    # При необходимости расширьте класс Word.
                )
                for w in seg.get('words', [])
            ]
            segments.append(Segment(
                id=i, seek=0,
                start=seg['start'], end=seg['end'],
                text=seg['text'], tokens=[],
                avg_logprob=0.0, compression_ratio=0.0, no_speech_prob=0.0,
                words=words if words else None,
                temperature=0.0
            ))
        return segments

    def _cache_result(self, job_id: str, segments: List[Segment]) -> None:
        """Кэширует результат, чтобы избежать повторной обработки."""
        try:
            data = {
                'segments': [
                    {
                        'start': s.start, 'end': s.end, 'text': s.text,
                        'words': [
                            {'start': w.start, 'end': w.end, 'word': w.word, 'probability': w.probability}
                            for w in (s.words or [])
                        ]
                    } for s in segments
                ]
            }
            self.redis.set(self._key_result(job_id), data, ttl=7200)  # 2 часа
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")

    def _get_cached(self, job_id: str) -> Optional[List[Segment]]:
        """Пытается вернуть закэшированный результат."""
        try:
            cached = self.redis.get(self._key_result(job_id))
            if not cached:
                return None
            segments = []
            for i, seg in enumerate(cached.get('segments', [])):
                words = [Word(**w) for w in seg.get('words', [])]
                segments.append(Segment(
                    id=i, seek=0,
                    start=seg['start'], end=seg['end'],
                    text=seg['text'], tokens=[],
                    avg_logprob=0.0, compression_ratio=0.0, no_speech_prob=0.0,
                    words=words if words else None,
                    temperature=0.0
                ))
            return segments
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")
            return None

    # ───────── IModel интерфейс ─────────
    def predict(self, request: TranscriptionRequest, ctx: Any = None) -> List[Segment]:
        # Извлекаем job_id из контекста

        job_id = ctx.get('job_id') if isinstance(ctx, dict) else None
        log = ctx.get('logger') if isinstance(ctx, dict) and isinstance(ctx.get('logger'), Logger) else None
        if not job_id:
            raise TranscriptionError("job_id required in context")

        fhash = self._file_hash(request.audio_bytes)

        # 1. Проверяем кэш готового результата
        if cached := self._get_cached(job_id):
            log.info(f"Cache hit for job {job_id}")
            return cached

        # 2. Проверяем, не запущена ли уже задача
        task_id = self._get_existing_task(job_id, fhash)


        if not task_id:
            # 3. Новая задача: отправляем в API
            task_id = self._submit(request.audio_bytes, request.language)
            if not self._register_task(job_id, fhash, task_id):
                log.warning(f"Redis registration failed, but continuing with task_id={task_id}")

        log.info(f"Handling task {task_id}")

        # 4. Polling с таймаутом
        start = time.time()
        log.debug(f"Polling task {task_id}")

        while time.time() - start < self.poll_timeout:
            status_resp = self._poll(task_id)
            status = status_resp.get('status')

            if status == 'SUCCESS':
                logger.info(f"Task {task_id} done")
                api_result = self._fetch_result(task_id)
                # Логируем метрики обработки из API (опционально)
                if timings := api_result.get('processing_times_s'):
                    logger.debug(f"Processing times: {timings}")
                segments = self._parse(api_result)
                self._cache_result(job_id, segments)
                return segments

            elif status == 'PROGRESS':
                progress = status_resp.get('progress_percent', 0)
                step = status_resp.get('current_step', '')
                logger.debug(f"Task {task_id}: {progress}% - {step}")
                time.sleep(self.poll_interval)

            else:
                # Неизвестный статус или ошибка
                if err := status_resp.get('error_info'):
                    raise TranscriptionError(f"Task failed: {err}")
                # Неизвестный статус — ждём дольше, чтобы не спамить API
                time.sleep(self.poll_interval * 2)

        raise TranscriptionError(f"Timeout: task {task_id} not completed in {self.poll_timeout}s")

    def health_check(self) -> bool:
        try:
            # 🆕 Передаём ssl_verify
            api_ok = self._session.get(f"{self.api_base_url}", timeout=5,
                                       verify=self.ssl_verify).status_code == 200
        except:
            api_ok = False
        redis_ok = self.redis.ping()
        return api_ok and redis_ok

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_version(self) -> str:
        return self._model_version

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._session.close()
        return False


class CrocWhisperModelCreator(IModelCreator):
    """
    Фабрика для CrocWhisperModel.

    Ожидаемые params:
    - api_base_url: str (обязательно)
    - redis_db: DictionaryDatabase (обязательно)
    - poll_interval: float (опционально, default=2.0)
    - poll_timeout: int (опционально, default=1800)
    - request_timeout: int (опционально, default=30)
    """

    def create_model(self, params: Dict[str, Any]) -> IModel:
        required = ['api_base_url', 'redis_db']
        for key in required:
            if key not in params:
                raise ValueError(f"CrocWhisperModel requires param: {key}")

        return CrocWhisperModel(
            api_base_url=params['api_base_url'],
            redis_db=params['redis_db'],
            ssl_verify=params.get('ssl_verify', True),  # 🆕
            poll_interval=params.get('poll_interval', 2.0),
            poll_timeout=params.get('poll_timeout', 1800),
            request_timeout=params.get('request_timeout', 30),
        )