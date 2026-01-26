# test_app.py — pytest-версия

import pytest
import tempfile
import os
import json
import datetime
import numpy as np
from unittest.mock import Mock, MagicMock, patch

# Импорты из вашего проекта
from application import App, Request, AudioSource, Result, Response, request_from_binary


# --- Моки ---
class MockModel:
    """Mock для IModel"""
    def __init__(self):
        self.health_check_called = False
        self.predict_return_value = []

    def health_check(self):
        self.health_check_called = True
        return True

    def predict(self, request):
        return self.predict_return_value

    @property
    def model_name(self):
        return "mock-model"

    @property
    def model_version(self):
        return "1.0.0"


class MockQueue:
    """Mock для IMessageQueue"""
    def __init__(self):
        self.subscribe_called_with = []
        self.publish_called_with = []
        self.health_check_called = False

    async def connect(self):
        pass

    async def publish(self, topic, message):
        self.publish_called_with.append((topic, message))

    async def subscribe(self, topic, handler):
        self.subscribe_called_with.append((topic, handler))

    async def close(self):
        pass

    async def health_check(self):
        self.health_check_called = True
        return True


class MockStorage:
    """Mock для fsspec.AbstractFileSystem"""
    def __init__(self):
        self.info_called_with = []
        self.open_called_with = []
        self.files_content = {}  # Словарь для хранения содержимого файлов

    def info(self, path):
        self.info_called_with.append(path)

        # Обработка корневой директории
        if path == './':
            return {'type': 'directory', 'size': 0}

        # Для остальных путей — проверяем наличие
        if path not in self.files_content:
            raise FileNotFoundError(f"File {path} not found")

        return {'type': 'file', 'size': len(self.files_content[path])}

    def open(self, path, mode='r'):
        self.open_called_with.append((path, mode))
        if path in self.files_content:
            content = self.files_content[path]
            if 'rb' in mode:
                return MockFile(content, mode, is_binary=True)
            else:
                return MockFile(content, mode)
        else:
            raise FileNotFoundError(f"File {path} not found")


class MockFile:
    """Mock для файла"""
    def __init__(self, content, mode, is_binary=False):
        self.content = content
        self.mode = mode
        self.is_binary = is_binary
        self.position = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def read(self):
        if self.is_binary:
            return self.content
        else:
            return self.content.encode('utf-8') if isinstance(self.content, str) else self.content

    def write(self, data):
        if self.is_binary and isinstance(data, bytes):
            self.content = data
        elif not self.is_binary and isinstance(data, str):
            self.content = data
        else:
            self.content = data.decode('utf-8') if isinstance(data, bytes) else str(data)


# --- Тесты ---

@pytest.mark.asyncio
async def test_health_check_success():
    """Тест проверки работоспособности компонентов"""
    mock_model = MockModel()
    mock_queue = MockQueue()
    mock_storage = MockStorage()
    temp_dir = tempfile.mkdtemp()

    app = App(
        model=mock_model,
        queue=mock_queue,
        storage=mock_storage,
        request_topic='test_request_topic',
        response_topic='test_response_topic',
        temp_dir=temp_dir
    )

    with patch('application.librosa.load') as mock_librosa_load:
        mock_librosa_load.return_value = (np.array([0.1, 0.2, 0.3]), 16000)

        result = await app.health_check()
        assert result is True
        assert mock_model.health_check_called is True
        assert mock_queue.health_check_called is True
        assert './' in mock_storage.info_called_with


@pytest.mark.asyncio
async def test_queue_raw_handler_valid_request():
    """Тест обработчика очереди с валидным запросом"""
    mock_model = MockModel()
    mock_queue = MockQueue()
    mock_storage = MockStorage()
    temp_dir = tempfile.mkdtemp()

    app = App(
        model=mock_model,
        queue=mock_queue,
        storage=mock_storage,
        request_topic='test_request_topic',
        response_topic='test_response_topic',
        temp_dir=temp_dir
    )

    # Создаем валидный запрос
    request_obj = Request(
        job_id='test_job_123',
        input_type='file',
        audio_source=AudioSource(path='/remote/audio.wav'),
        created_at=datetime.datetime.now()
    )

    # Сериализуем в JSON и затем в байты
    request_data = {
        'job_id': request_obj.job_id,
        'input_type': request_obj.input_type,
        'audio_source': {
            'path': request_obj.audio_source.path
        },
        'created_at': request_obj.created_at.isoformat()
    }
    request_bytes = json.dumps(request_data).encode('utf-8')

    # Мокаем методы, чтобы избежать реальной загрузки файлов
    with patch.object(app, 'download_file', return_value=(True, None)), \
         patch.object(app, 'convert_audio_to_16khz', return_value=b'test_audio_bytes'), \
         patch.object(app.model, 'predict', return_value=[]):

        # Создаем mock-сообщение
        mock_msg = MagicMock()
        mock_msg.data = request_bytes

        # Вызываем обработчик
        await app.queue_raw_handler(mock_msg)

    # Проверяем, что результат был опубликован в очередь
    assert len(mock_queue.publish_called_with) == 1
    published_topic, published_data = mock_queue.publish_called_with[0]
    assert published_topic == app.response_topic

    # Десериализуем опубликованный ответ
    response_data = json.loads(published_data.decode('utf-8'))
    assert response_data['job_id'] == request_obj.job_id
    assert response_data['status'] == 'completed'


@pytest.mark.asyncio
async def test_queue_raw_handler_invalid_request():
    """Тест обработчика очереди с невалидным запросом (нет job_id)"""
    mock_model = MockModel()
    mock_queue = MockQueue()
    mock_storage = MockStorage()
    temp_dir = tempfile.mkdtemp()

    app = App(
        model=mock_model,
        queue=mock_queue,
        storage=mock_storage,
        request_topic='test_request_topic',
        response_topic='test_response_topic',
        temp_dir=temp_dir
    )

    # Создаем невалидный запрос (без job_id)
    invalid_request_data = {
        'input_type': 'file',
        'audio_source': {
            'path': '/remote/audio.wav'
        },
        'created_at': datetime.datetime.now().isoformat()
    }
    request_bytes = json.dumps(invalid_request_data).encode('utf-8')

    # Создаем mock-сообщение
    mock_msg = MagicMock()
    mock_msg.data = request_bytes

    # Вызываем обработчик
    await app.queue_raw_handler(mock_msg)

    # Проверяем, что результат с ошибкой был опубликован в очередь
    assert len(mock_queue.publish_called_with) == 1
    published_topic, published_data = mock_queue.publish_called_with[0]
    assert published_topic == app.response_topic

    # Десериализуем опубликованный ответ
    response_data = json.loads(published_data.decode('utf-8'))
    assert response_data['status'] == 'failed'
    assert 'Missing required field: job_id' in response_data['error']


@pytest.mark.asyncio
async def test_queue_raw_handler_invalid_request_with_job_id():
    """Тест обработчика очереди с невалидным запросом, но с job_id (неверный input_type)"""
    mock_model = MockModel()
    mock_queue = MockQueue()
    mock_storage = MockStorage()
    temp_dir = tempfile.mkdtemp()

    app = App(
        model=mock_model,
        queue=mock_queue,
        storage=mock_storage,
        request_topic='test_request_topic',
        response_topic='test_response_topic',
        temp_dir=temp_dir
    )

    # Создаем невалидный запрос, но с job_id
    invalid_request_data = {
        'job_id': 'test_job_456',
        'input_type': 'invalid_type',  # Невалидный тип
        'audio_source': {
            'path': '/remote/audio.wav'
        },
        'created_at': datetime.datetime.now().isoformat()
    }
    request_bytes = json.dumps(invalid_request_data).encode('utf-8')

    # Создаем mock-сообщение
    mock_msg = MagicMock()
    mock_msg.data = request_bytes

    # Вызываем обработчик
    await app.queue_raw_handler(mock_msg)

    # Проверяем, что результат с ошибкой был опубликован в очередь
    assert len(mock_queue.publish_called_with) == 1
    published_topic, published_data = mock_queue.publish_called_with[0]
    assert published_topic == app.response_topic

    # Десериализуем опубликованный ответ
    response_data = json.loads(published_data.decode('utf-8'))
    assert response_data['job_id'] == 'test_job_456'
    assert response_data['status'] == 'failed'
    assert 'Invalid input_type:' in response_data['error']


def test_download_file_success():
    """Тест успешной загрузки файла"""
    mock_storage = MockStorage()
    temp_dir = tempfile.mkdtemp()
    app = App(
        model=None,
        queue=None,
        storage=mock_storage,
        request_topic='',
        response_topic='',
        temp_dir=temp_dir
    )

    remote_path = '/remote/test.wav'
    local_path = os.path.join(temp_dir, 'local_test.wav')
    mock_storage.files_content[remote_path] = b'test_audio_content'

    success, error = app.download_file(remote_path, local_path)

    assert success is True
    assert error is None
    assert (remote_path, 'rb') in mock_storage.open_called_with
    assert os.path.exists(local_path)


def test_download_file_failure():
    """Тест неудачной загрузки файла"""
    mock_storage = MockStorage()
    temp_dir = tempfile.mkdtemp()
    app = App(
        model=None,
        queue=None,
        storage=mock_storage,
        request_topic='',
        response_topic='',
        temp_dir=temp_dir
    )

    remote_path = '/nonexistent/test.wav'
    local_path = os.path.join(temp_dir, 'local_test.wav')

    success, error = app.download_file(remote_path, local_path)

    assert success is False
    assert error is not None


@patch('builtins.open', new_callable=MagicMock)
def test_extract_archive_zip(mock_open):
    """Тест распаковки ZIP-архива"""
    import zipfile

    mock_storage = MockStorage()
    temp_dir = tempfile.mkdtemp()
    app = App(
        model=None,
        queue=None,
        storage=mock_storage,
        request_topic='',
        response_topic='',
        temp_dir=temp_dir
    )

    # Создаем временный архив
    archive_path = os.path.join(temp_dir, 'test.zip')
    extract_to = os.path.join(temp_dir, 'extracted')

    # Мокаем zipfile
    with patch('application.zipfile.ZipFile') as mock_zipfile:
        mock_zip_instance = MagicMock()
        mock_zipfile.return_value.__enter__.return_value = mock_zip_instance

        success, error = app.extract_archive(archive_path, extract_to)

        assert success is True
        assert error is None
        mock_zipfile.assert_called_once_with(archive_path, 'r')
        mock_zip_instance.extractall.assert_called_once_with(extract_to)


def test_generate_random_filename():
    """Тест генерации случайного имени файла"""
    mock_storage = MockStorage()
    temp_dir = tempfile.mkdtemp()
    app = App(
        model=None,
        queue=None,
        storage=mock_storage,
        request_topic='',
        response_topic='',
        temp_dir=temp_dir
    )

    filename = app.generate_random_filename()
    assert len(filename) == 64  # По умолчанию 64 символа

    filename_custom = app.generate_random_filename(32)
    assert len(filename_custom) == 32


@patch('application.librosa.load')
@patch('scipy.io.wavfile.write')
def test_convert_audio_to_16khz(mock_wavfile_write, mock_librosa_load):
    """Тест конвертации аудио в 16 кГц"""
    mock_librosa_load.return_value = (np.array([0.1, 0.2, 0.3]), 16000)
    mock_wavfile_write.return_value = None

    mock_storage = MockStorage()
    temp_dir = tempfile.mkdtemp()
    app = App(
        model=None,
        queue=None,
        storage=mock_storage,
        request_topic='',
        response_topic='',
        temp_dir=temp_dir
    )

    audio_path = os.path.join(temp_dir, 'test.wav')

    # Создаем тестовый файл
    with open(audio_path, 'wb') as f:
        f.write(b'test_audio')

    result = app.convert_audio_to_16khz(audio_path)

    assert isinstance(result, bytes)
    mock_librosa_load.assert_called_once_with(audio_path, sr=16000)


def test_request_from_binary_valid():
    """Тест десериализации валидного запроса"""
    request_data = {
        'job_id': 'test_job_789',
        'input_type': 'file',
        'audio_source': {
            'path': '/remote/audio.wav'
        },
        'created_at': datetime.datetime.now().isoformat()
    }
    request_bytes = json.dumps(request_data).encode('utf-8')

    request = request_from_binary(request_bytes)

    assert request.job_id == 'test_job_789'
    assert request.input_type == 'file'
    assert request.audio_source.path == '/remote/audio.wav'


def test_request_from_binary_invalid_json():
    """Тест десериализации невалидного JSON"""
    invalid_bytes = b'invalid json data'

    with pytest.raises(ValueError):
        request_from_binary(invalid_bytes)


def test_request_from_binary_missing_field():
    """Тест десериализации запроса с отсутствующим полем"""
    request_data = {
        'input_type': 'file',  # Нет job_id
        'audio_source': {
            'path': '/remote/audio.wav'
        },
        'created_at': datetime.datetime.now().isoformat()
    }
    request_bytes = json.dumps(request_data).encode('utf-8')

    with pytest.raises(ValueError) as context:
        request_from_binary(request_bytes)

    assert 'Missing required field: job_id' in str(context.value)


if __name__ == '__main__':
    pytest.main()