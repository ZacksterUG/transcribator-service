class HandleInitJobIdError(Exception):
    pass

class RedisJobLocker(Exception):
    pass

class MaximumPoolReached(Exception):
    pass

class BytesNotProvidedError(Exception):
    pass