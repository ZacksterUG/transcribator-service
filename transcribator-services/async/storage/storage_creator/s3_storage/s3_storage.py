import fsspec
from ..storage_creator import IStorageCreator

class S3StorageCreator(IStorageCreator):
    def create_storage(self, params: dict) -> fsspec.AbstractFileSystem:
        required_keys = {"key", "secret", "endpoint_url", "bucket"}
        if not required_keys.issubset(params.keys()):
            raise ValueError(f"S3 storage requires: {required_keys}")

        fs = fsspec.filesystem(
            "s3",
            key=params["key"],
            secret=params["secret"],
            client_kwargs={"endpoint_url": params["endpoint_url"]},
            use_ssl=params.get("use_ssl", True),
            default_cache_type=params.get("cache_type", "readahead"),
        )
        #  убедимся, что бакет существует
        bucket = params["bucket"]
        if not fs.exists(bucket):
            fs.mkdir(bucket)
        return fs