class TranscriptionError(Exception):
    pass

class ModelNotReadyError(TranscriptionError):
    pass

class InvalidAudioError(TranscriptionError):
    pass