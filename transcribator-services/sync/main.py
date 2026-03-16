from typing import Optional

import nats
import redis
from nats.aio.client import Client
from nats.aio.subscription import Subscription
from sherpa_onnx import OnlineRecognizer
import asyncio
from config import Config
from app import App
from logger import setup_logger


async def main():
    cfg = Config()
    logger = setup_logger("transcriber_sync", level=cfg.log_level)

    rb = redis.Redis(
        host=cfg.redis_host,
        port=cfg.redis_port,
        db=cfg.redis_db,
        password=cfg.redis_password
    )
    nc: Client = await nats.connect(servers=cfg.nats_servers)
    recognizer = OnlineRecognizer().from_transducer(
        tokens=cfg.model_tokens,
        encoder=cfg.model_encoder,
        decoder=cfg.model_decoder,
        joiner=cfg.model_joiner,
        num_threads=cfg.model_num_threads,
        sample_rate=cfg.sample_rate,
        feature_dim=cfg.feature_dim,
        decoding_method=cfg.decoding_method,
        enable_endpoint_detection=cfg.enable_endpoint_detection,
        rule1_min_trailing_silence=cfg.rule1_min_trailing_silence,
        rule2_min_trailing_silence=cfg.rule2_min_trailing_silence,
        rule3_min_utterance_length=cfg.rule3_min_utterance_length
    )
    sub: Optional[Subscription] = None

    app = App(redis_db=rb, recognizer=recognizer, nats_client=nc, config=cfg, logger=logger)

    logger.info(f'Nats connected {nc.is_connected}')

    try:
        await app.run()
    except KeyboardInterrupt:
        if sub is not None: await sub.unsubscribe()
        await nc.close()
        logger.info('Closed connection')

    except Exception as e:
        logger.exception('Unhandled exception occurred: %s', str(e))


if __name__ == '__main__':
    asyncio.run(main())
