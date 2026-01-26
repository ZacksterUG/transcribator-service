from abc import ABC, abstractmethod
import fsspec

class IStorageCreator(ABC):
    @abstractmethod
    def create_storage(self, params: dict) -> fsspec.AbstractFileSystem:
        """
        Создаёт экземпляр файловой системы на основе переданных параметров.
        """
        pass