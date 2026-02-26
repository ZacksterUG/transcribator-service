
import fsspec
from ..storage_creator import IStorageCreator

class LocalStorageCreator(IStorageCreator):
    def create_storage(self, params: dict) -> fsspec.AbstractFileSystem:
        # Локальная ФС не требует специальных параметров, но можно добавить root_path и т.п.
        root = params.get("root", "")
        return fsspec.filesystem("file", auto_mkdir=True)