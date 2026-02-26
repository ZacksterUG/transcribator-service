from typing import Dict, Any

from ..queue_creator.base_creator import IQueueCreator
from ..abstractions.message_queue import IMessageQueue

from ..implementations.nats_queue import NatsQueueCreator
from ..implementations.rabbitmq_queue import RabbitMQQueueCreator

class QueueFactory:

    @classmethod
    def create(cls, creator: IQueueCreator, params: Dict[str, Any]) -> IMessageQueue:
        return creator.create_queue(params)