from typing import Dict, Any

from ..queue_creator.base_creator import IQueueCreator
from ..abstractions.message_queue import IMessageQueue

class QueueFactory:

    @classmethod
    def create(cls, creator: IQueueCreator, params: Dict[str, Any]) -> IMessageQueue:
        return creator.create_queue(params)