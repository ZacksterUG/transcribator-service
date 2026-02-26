from typing import Dict, Any
import fsspec

from ..storage_creator.storage_creator import IStorageCreator


class StorageFactory:
    """
    Фабрика для создания файловых хранилищ.
    """
    @classmethod
    def create(cls, creator: IStorageCreator, params: Dict[str, Any]) -> fsspec.AbstractFileSystem:
        """
        Создаёт файловую систему указанного типа.

        :param Creator: тип хранилища ('local', 's3')
        :param params: параметры инициализации (зависят от типа)
        :return: экземпляр fsspec.AbstractFileSystem
        :raises ValueError: если тип не поддерживается
        """
        return creator.create_storage(params)