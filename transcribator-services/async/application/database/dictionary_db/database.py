from abc import ABC, abstractmethod
from typing import Any, Optional, Dict
from contextlib import contextmanager
from redis.lock import Lock as RedisLock


class DictionaryDatabase(ABC):
    """
    Абстрактный базовый класс для работы с хранилищем ключ-значение.
    
    Определяет интерфейс для базовых операций (CRUD) и механизмов блокировок.
    Позволяет абстрагироваться от конкретной реализации (Redis, Memcached, 
    in-memory хранилище и т.д.) и легко подменять их в тестах.
    
    Пример использования:
        db = RedisDatabase()  # или другая реализация
        db.set('user:1', {'name': 'Alice'})
        data = db.get('user:1')
    """

    @abstractmethod
    def get(self, key: str) -> Any:
        """
        Получение значения по ключу.
        
        Args:
            key: Уникальный идентификатор записи.
            
        Returns:
            Значение, связанное с ключом, или None если ключ не найден.
        """
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Запись значения по ключу.
        
        Args:
            key: Уникальный идентификатор записи.
            value: Данные для сохранения (сериализуемый объект).
            ttl: Время жизни ключа в секундах (опционально).
            
        Returns:
            True если запись успешна, False в случае ошибки.
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Удаление записи по ключу.
        
        Args:
            key: Уникальный идентификатор записи.
            
        Returns:
            True если ключ существовал и был удален, 
            False если ключ не был найден.
        """
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        Проверка существования ключа в хранилище.
        
        Args:
            key: Уникальный идентификатор записи.
            
        Returns:
            True если ключ существует, False иначе.
        """
        pass

    @abstractmethod
    def rlock(self, key: str, ttl: int = 30) -> Optional['LockContext']:
        """
        Захват блокировки на чтение (Read Lock).
        
        Args:
            key: Ключ ресурса, который нужно заблокировать.
            ttl: Время жизни блокировки в секундах.
            
        Returns:
            Контекстный менеджер блокировки или None если не удалось захватить.
        """
        pass

    @abstractmethod
    def rwlock(self, key: str, ttl: int = 30) -> Optional['LockContext']:
        """
        Захват эксклюзивной блокировки на запись (Read-Write Lock).
        
        Args:
            key: Ключ ресурса, который нужно заблокировать.
            ttl: Время жизни блокировки в секундах.
            
        Returns:
            Контекстный менеджер блокировки или None если не удалось захватить.
        """
        pass

    @abstractmethod
    def name(self) -> str:
        """
        Наименование экземпляра.

        Returns:
            Возвращает строку с именем.
        """
        pass

    @abstractmethod
    def ping(self) -> bool:
        """
        Проверка подключения к БД.

        Returns:
            Возвращает True, если подключение удалось, иначе false.
        """
        pass


class LockContext:
    """
    Контекстный менеджер для безопасной работы с блокировками.
    """

    def __init__(self, lock: Any, acquired: bool):
        self._lock = lock
        self._acquired = acquired

    def __enter__(self) -> 'LockContext':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._acquired and self._lock:
            try:
                self._lock.release()
            except Exception:
                pass

    def extend_ttl(self, additional_time: int) -> bool:
        """
        Продлевает TTL активной блокировки.

        Args:
            additional_time: Дополнительное время в секундах.

        Returns:
            True если продление успешно, False если не поддерживается или не удалось.
        """
        if not self._acquired or not self._lock:
            return False
        # Делегируем реализацию конкретному классу блокировки
        if hasattr(self._lock, 'extend_ttl'):
            try:
                return bool(self._lock.extend_ttl(additional_time))
            except Exception:
                return False
        return False  # По умолчанию — операция не поддерживается

    @property
    def acquired(self) -> bool:
        return self._acquired
    

class DictionaryDatabaseCreator(ABC):
    @abstractmethod
    def create(self, params: Dict[str, Any]) -> DictionaryDatabase:
        pass

