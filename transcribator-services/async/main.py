import asyncio
import sys
import fsspec
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from application.message_queue.queue_factory.queue_factory import QueueFactory
from application.message_queue.implementations.nats_queue import NatsQueueCreator

from application.storage.storage_factory.storage_factory import StorageFactory
from application.storage.storage_creator.s3_storage.s3_storage import S3StorageCreator

from application.transcribation_model.model_factory import ModelFactory
from application.transcribation_model.faster_whisper_model import FasterWhisperCreator

from application.database.dictionary_db.redis.redis import RedisDatabaseCreator

from application.application import App
from logger import setup_logger
import os


async def main():
    logger = setup_logger("transcriber", level="INFO")

    nats_servers = os.environ['NATS_SERVERS']
    queue_creator = NatsQueueCreator()
    queue_params = {"servers": nats_servers, "verbose": True, "pedantic":True, "use_jetstream": True}
    queue = QueueFactory.create(queue_creator, queue_params)

    storage_url = os.environ['MINIO_URL']
    storage_user = os.environ['MINIO_USER']
    storage_password = os.environ['MINIO_PASSWORD']
    storage_bucket = os.environ['MINIO_BUCKET']
    storage_creator = S3StorageCreator()
    storage_params = {"key": storage_user, "secret": storage_password, "endpoint_url": storage_url, "bucket": storage_bucket}
    storage = StorageFactory.create(storage_creator, storage_params)

    model_name = os.environ['MODEL_NAME']
    model_path_or_size = os.environ['MODEL_PATH_OR_SIZE']
    model_device = os.environ['MODEL_DEVICE']
    model_compute_type = os.environ['MODEL_COMPUTE_TYPE']
    model_num_workers = int(os.environ['MODEL_NUM_WORKERS'])

    model_creator = FasterWhisperCreator()
    model_params = {"model_size_or_path": model_path_or_size, "device": model_device, "compute_type": model_compute_type, "num_workers": model_num_workers}
    model = ModelFactory.create(model_creator, model_params)

    redis_host = os.environ['REDIS_HOST']
    redis_port = int(os.environ['REDIS_PORT'])
    redis_db = int(os.environ['REDIS_DB'])
    redis_password = os.environ['REDIS_PASSWORD']
    rdc = RedisDatabaseCreator()
    redis_db = rdc.create(params={
        "host": redis_host,
        "port": redis_port,
        "db": redis_db,
        "password": redis_password
    })

    request_topic = os.environ['REQUEST_TOPIC']
    response_topic = os.environ['RESPONSE_TOPIC']
    temp_dir = os.environ['TEMP_DIR']

    
    app = App(model=model, 
              queue=queue, 
              storage=storage, 
              request_topic=request_topic, 
              response_topic=response_topic, 
              temp_dir=temp_dir, 
              logger=logger,
              debug=True,
              dict_db=redis_db)

    await app.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApplication terminated by user")
        sys.exit(0)