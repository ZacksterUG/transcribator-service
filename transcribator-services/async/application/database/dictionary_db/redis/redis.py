import json
import redis
from typing import Any, Optional, Dict
from redis.lock import Lock as RedisLock

from ..database import DictionaryDatabase, LockContext, DictionaryDatabaseCreator


class RedisReadLock:
    """
    Вспомогательный класс для реализации Read Lock через счетчик в Redis.
    Позволяет множественным читателям, но блокируется при наличии писателя.
    """
    def __init__(self, client: redis.Redis, key: str, ttl: int):
        self.client = client
        self.key = key
        self.ttl = ttl
        self.read_key = f"{key}:readers"
        self.write_key = f"{key}:write" # Имя ключа, которое использует RedisLock для записи
        self._acquired = False
        
        # Lua скрипт для безопасного захвата read lock
        # Проверяет, нет ли write lock, и инкрементирует счетчик читателей
        self._acquire_script = client.register_script("""
            local write_key = KEYS[1]
            local read_key = KEYS[2]
            local ttl = tonumber(ARGV[1])
            
            -- Если есть эксклюзивный лок на запись, отказываем
            if redis.call('EXISTS', write_key) == 1 then
                return 0
            end
            
            -- Инкрементируем счетчик читателей и обновляем TTL
            redis.call('INCR', read_key)
            redis.call('EXPIRE', read_key, ttl)
            return 1
        """)
        
        # Lua скрипт для освобождения
        self._release_script = client.register_script("""
            local read_key = KEYS[1]
            redis.call('DECR', read_key)
        """)

        # Попытка захвата
        try:
            result = self._acquire_script(keys=[self.write_key, self.read_key], args=[self.ttl])
            self._acquired = bool(result)
        except Exception:
            self._acquired = False

    def extend_ttl(self, additional_time: int) -> bool:
        """
        Продлевает TTL read-lock'а через обновление TTL счетчика читателей.
        Для простоты просто обновляем TTL до исходного значения.
        """
        if not self._acquired:
            return False
        try:
            # Просто освежаем TTL, не накапливая время
            self.client.expire(self.read_key, self.ttl)
            return True
        except Exception:
            return False

    def release(self) -> None:
        if self._acquired:
            try:
                self._release_script(keys=[self.read_key])
            except Exception:
                pass # Игнорируем ошибки при освобождении в finally блоках
            finally:
                self._acquired = False


class RedisWriteLock:
    """
    Обертка над стандартным RedisLock с дополнительной проверкой активных читателей.
    """
    def __init__(self, client: redis.Redis, key: str, ttl: int):
        self.client = client
        self.key = key
        self.ttl = ttl
        self.read_key = f"{key}:readers"
        self._lock = RedisLock(client, key, timeout=ttl)
        self._acquired = False

        # Lua скрипт проверки отсутствия активных читателей
        self._check_readers_script = client.register_script("""
            local read_key = KEYS[1]
            local count = tonumber(redis.call('GET', read_key))
            if count == nil or count <= 0 then
                return 1
            end
            return 0
        """)

        # Попытка захвата
        try:
            # Сначала проверяем, нет ли активных читателей
            readers_active = self._check_readers_script(keys=[self.read_key])
            if not readers_active:
                # Если читатели есть, не пытаемся захватить основной лок (fail fast)
                # В продакшене здесь можно добавить retry logic
                self._acquired = False
            else:
                # Попытка захватить стандартный эксклюзивный лок
                # blocking=False для соответствия сигнатуре (возврат None если не удалось)
                # RedisLock по умолчанию блокирует. Нам нужно поведение non-blocking для возврата Optional
                if self._lock.acquire(blocking=False):
                    self._acquired = True
                else:
                    self._acquired = False
        except Exception:
            self._acquired = False

    def extend_ttl(self, additional_time: int) -> bool:
        """Продлевает TTL эксклюзивной блокировки через redis-py extend()."""
        if not self._acquired or not self._lock:
            return False
        try:
            # redis.lock.Lock.extend(additional_time, replace_ttl=False)
            self._lock.extend(additional_time=self.ttl, replace_ttl=True)
            return True
        except Exception:
            return False

    def release(self) -> None:
        if self._acquired and self._lock:
            try:
                self._lock.release()
            except Exception:
                pass
            finally:
                self._acquired = False


class RedisDatabase(DictionaryDatabase):
    """
    Реализация DictionaryDatabase на основе Redis.
    """

    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0, 
                 password: Optional[str] = None, decode_responses: bool = False,
                 client: Optional[redis.Redis] = None):
        """
        Инициализация подключения к Redis.
        
        Args:
            host, port, db, password: Параметры подключения.
            decode_responses: Если False, данные возвращаются как bytes (требуется декодирование).
            client: Готовый инстанс redis.Redis (приоритет над параметрами подключения).
        """
        if client:
            self._client = client
        else:
            self._client = redis.Redis(
                host=host, 
                port=port, 
                db=db, 
                password=password, 
                decode_responses=decode_responses,
                socket_connect_timeout=5
            )

    def _serialize(self, value: Any) -> str:
        """Сериализация Python объекта в JSON строку."""
        if value is None:
            return None
        return json.dumps(value, default=str, ensure_ascii=False)

    def _deserialize(self, data: Optional[str]) -> Any:
        """Десериализация JSON строки в Python объект."""
        if data is None:
            return None
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            # Если в хранилище попали не JSON данные, возвращаем как есть
            return data

    def get(self, key: str) -> Any:
        try:
            data = self._client.get(key)
            return self._deserialize(data)
        except redis.RedisError:
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        try:
            serialized = self._serialize(value)
            if ttl:
                return bool(self._client.setex(key, ttl, serialized))
            else:
                return bool(self._client.set(key, serialized))
        except redis.RedisError:
            return False

    def delete(self, key: str) -> bool:
        try:
            # Возвращает количество удаленных ключей
            return self._client.delete(key) > 0
        except redis.RedisError:
            return False

    def exists(self, key: str) -> bool:
        try:
            return bool(self._client.exists(key))
        except redis.RedisError:
            return False

    def rlock(self, key: str, ttl: int = 30) -> Optional[LockContext]:
        """
        Захват блокировки на чтение.
        Реализовано через счетчик активных читателей.
        """
        lock_obj = RedisReadLock(self._client, key, ttl)
        if lock_obj._acquired:
            return LockContext(lock_obj, True)
        else:
            # Освобождаем ресурсы, если не удалось захватить
            lock_obj.release()
            return None

    def rwlock(self, key: str, ttl: int = 30) -> Optional[LockContext]:
        """
        Захват эксклюзивной блокировки на запись.
        Проверяет отсутствие активных читателей перед захватом.
        """
        lock_obj = RedisWriteLock(self._client, key, ttl)
        if lock_obj._acquired:
            return LockContext(lock_obj, True)
        else:
            lock_obj.release()
            return None

    def ping(self) -> bool:
        try:
            return self._client.ping()
        except redis.RedisError:
            return False

    def name(self) -> str:
        return 'redis'


class RedisDatabaseCreator(DictionaryDatabaseCreator):
    """
    Фабрика для создания экземпляров RedisDictionaryDatabase.
    """
    
    def create(self, params: Dict[str, Any]) -> DictionaryDatabase:
        """
        Создает подключение на основе словаря параметров.
        
        Ожидаемые ключи в params:
            - host (str)
            - port (int)
            - db (int)
            - password (str, optional)
            - client (redis.Redis, optional) - если передан, остальные игнорируются
        """
        # Извлекаем параметры с дефолтными значениями
        host = params.get('host', 'localhost')
        port = int(params.get('port', 6379))
        db = int(params.get('db', 0))
        password = params.get('password', None)
        client = params.get('client', None)
        
        return RedisDatabase(
            host=host,
            port=port,
            db=db,
            password=password,
            client=client
        )