import asyncio
import sys
from dotenv import load_dotenv

from logger import setup_logger
from config.settings import load_config

# Ваши существующие фабрики
from message_queue.queue_factory.queue_factory import QueueFactory
from message_queue.implementations.nats_queue import NatsQueueCreator

from storage.storage_factory.storage_factory import StorageFactory
from storage.storage_creator.s3_storage.s3_storage import S3StorageCreator

from database.dictionary_db.redis.redis import RedisDatabaseCreator

# Новая фабрика моделей
from factories.model_factory import ModelFactory

from application.application import App


async def main():
    # 1. Загрузка конфига
    load_dotenv()
    cfg = load_config()

    # 2. Логгер
    logger = setup_logger("transcriber", level=cfg['log_level'])
    logger.info(f"Starting with model: {cfg['model_type'].name}")

    try:
        # 3. Queue (ваша фабрика)
        queue = QueueFactory.create(
            NatsQueueCreator(),
            params={
                "servers": cfg['nats_servers'],
                "verbose": cfg['nats_verbose'],
                "pedantic": cfg['nats_pedantic'],
                "use_jetstream": cfg['nats_jetstream'],
            }
        )

        # 4. Storage (ваша фабрика)
        storage = StorageFactory.create(
            S3StorageCreator(),
            params={
                "key": cfg['minio_user'],
                "secret": cfg['minio_password'],
                "endpoint_url": cfg['minio_url'],
                "bucket": cfg['minio_bucket'],
            }
        )

        # 5. Redis (прямое создание через Creator)
        redis_db = RedisDatabaseCreator().create(params={
            "host": cfg['redis_host'],
            "port": cfg['redis_port'],
            "db": cfg['redis_db'],
            "password": cfg['redis_password'],
        })

        # 6. Model (новая фабрика с выбором типа)
        model = ModelFactory.create_by_type(
            model_type=cfg['model_type'],
            params=cfg,
            redis_db=redis_db,  # Критично для Croc-модели
        )

        # 7. Запуск приложения
        app = App(
            model=model,
            queue=queue,
            storage=storage,
            request_topic=cfg['request_topic'],
            response_topic=cfg['response_topic'],
            temp_dir=cfg['temp_dir'],
            logger=logger,
            debug=cfg['debug'],
            dict_db=redis_db,
        )

        await app.run()

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception("Startup failed")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTerminated by user")
        sys.exit(0)