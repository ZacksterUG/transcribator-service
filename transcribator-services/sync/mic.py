#!/usr/bin/env python3
"""
Тестовый клиент для потоковой транскрибации (адаптирован под архитектуру):
- Запись с микрофона (sounddevice)
- Отправка чанков в NATS: transcriber.sync.processing.{job_id}
- Приём результатов из: transcriber.sync.response.{job_id}
- Формат: {'bytes': base64_float32, 'finish': bool}
"""

import asyncio
import base64
import json
import sys
import signal
from typing import Optional

import nats
import numpy as np
import sounddevice as sd
from nats.aio.client import Client, Msg

# === Конфигурация (должна совпадать с сервером) ===
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_DURATION = 0.16  # 160ms ≈ 2560 семплов
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)

NATS_URL = 'nats://localhost:4222'
BASE_TOPIC = 'transcriber.sync'


class MicStreamer:
    """Асинхронный стример: микрофон → NATS → консоль"""

    def __init__(self, job_id: str):
        self.job_id = job_id
        self.nc: Optional[Client] = None

        # Топики (соответствуют серверу)
        self.init_topic = f'{BASE_TOPIC}.init'
        self.processing_topic = f'{BASE_TOPIC}.processing.{job_id}'
        self.response_topic = f'{BASE_TOPIC}.response.{job_id}'
        self.status_topic = f'{BASE_TOPIC}.status.{job_id}'

        self.running = False
        self.queue: asyncio.Queue = asyncio.Queue()

        # Состояние отображения
        self.current_text = ''
        self.final_segments: list[str] = []
        self._line_length = 0

    async def connect(self):
        """Подключение к NATS"""
        self.nc = await nats.connect(servers=NATS_URL, reconnect_time_wait=1.0)
        print(f'✅ NATS connected: {self.nc.is_connected}')

        # Подписка на ответы
        await self.nc.subscribe(self.response_topic, cb=self._handle_response)
        print(f'✅ Subscribed to {self.response_topic}')

    async def _handle_response(self, msg: Msg):
        """Обработчик результатов от сервера"""
        try:
            data = json.loads(msg.data.decode())

            # Ошибка от сервера
            if data.get('error'):
                print(f'\n❌ Server error: {data.get("message")}')
                return

            result = data.get('result', {})
            text = result.get('text', '').strip()
            is_endpoint = result.get('is_endpoint', False)

            if not text:
                return

            if is_endpoint:
                # Фраза завершена — сохраняем и сбрасываем буфер
                if text and text != self.current_text:
                    self.final_segments.append(text)
                self.current_text = ''
                self._render_output(final=True)
            else:
                # Промежуточный результат — обновляем на лету
                if text != self.current_text:
                    self.current_text = text
                    self._render_output()

        except json.JSONDecodeError as e:
            print(f'⚠️ Invalid JSON: {e}')
        except Exception as e:
            print(f'⚠️ Response error: {e}')

    def _render_output(self, final: bool = False):
        """Вывод в консоль с обновлением строки"""
        # Очищаем предыдущий partial-текст
        if self._line_length > 0:
            sys.stdout.write('\r' + ' ' * self._line_length + '\r')
            self._line_length = 0

        # Финальные сегменты
        if self.final_segments:
            print('📝 Transcribed:')
            for i, seg in enumerate(self.final_segments, 1):
                print(f'  [{i:02d}] {seg}')
            print()

        # Промежуточный текст
        if self.current_text:
            line = f'🔄 Listening: {self.current_text}█'
            sys.stdout.write(line)
            sys.stdout.flush()
            self._line_length = len(line)
        elif final and self.final_segments:
            print('✨ Done.')

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Callback sounddevice (выполняется в отдельном потоке!)"""
        if status:
            print(f'⚠️ Audio: {status}')

        # Конвертируем в float32 [mono] и кладём в очередь
        chunk = indata[:, 0].astype(np.float32)
        self.queue.put_nowait(chunk)

    async def _send_chunks(self):
        """Отправка аудио-чанков в NATS"""
        while self.running:
            try:
                waveform = await asyncio.wait_for(self.queue.get(), timeout=0.3)

                # Кодируем: float32 → bytes → base64
                audio_b64 = base64.b64encode(waveform.tobytes()).decode('ascii')

                # Формат, который ожидает сервер
                payload = {
                    'bytes': audio_b64
                    # 'finish' добавляется отдельно при завершении
                }

                await self.nc.publish(
                    self.processing_topic,
                    json.dumps(payload).encode()
                )

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f'⚠️ Send error: {e}')

    async def _init_session(self):
        """Инициализация задачи на сервере"""
        init_payload = {'job_id': self.job_id}

        print(f'📤 Initializing job: {self.job_id}')
        await self.nc.publish(self.init_topic, json.dumps(init_payload).encode())

        # Опционально: ждём статус (если сервер отвечает)
        try:
            msg = await asyncio.wait_for(
                self.nc.request(self.status_topic, json.dumps(init_payload).encode()),
                timeout=1.0
            )
            status = json.loads(msg.data.decode())
            if status.get('error'):
                print(f'⚠️ Init warning: {status["error"]}')
            else:
                print(f'✅ Server ready')
        except asyncio.TimeoutError:
            print('⚠️ No status response (non-critical)')
        except Exception as e:
            print(f'⚠️ Status error: {e}')

    async def _finish_session(self):
        """Завершение сессии: сигнал финиша"""
        if not self.nc or not self.nc.is_connected:
            return

        # Отправляем финальный сигнал (без аудио)
        finish_payload = {'finish': True}
        await self.nc.publish(
            self.processing_topic,
            json.dumps(finish_payload).encode()
        )
        print('\n🏁 Finish signal sent')

        # Даём время на обработку последних результатов
        await asyncio.sleep(0.5)

    async def run(self, duration: Optional[float] = None):
        """Основной цикл"""
        await self.connect()
        await self._init_session()

        self.running = True

        # Фоновая задача отправки чанков
        sender_task = asyncio.create_task(self._send_chunks())

        # Запуск записи в отдельном потоке (sounddevice блокирующий)
        def record_loop():
            with sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    blocksize=CHUNK_SIZE,
                    callback=self._audio_callback,
                    dtype='float32',
                    latency='low'
            ):
                while self.running:
                    sd.sleep(int(CHUNK_DURATION * 1000))

        loop = asyncio.get_running_loop()
        record_task = loop.run_in_executor(None, record_loop)

        print('🎤 Recording... Press Ctrl+C to stop\n')

        try:
            if duration:
                await asyncio.sleep(duration)
            else:
                # Бесконечная запись до сигнала
                while self.running:
                    await asyncio.sleep(1)

        except KeyboardInterrupt:
            print('\n⏹️ Stopping...')
        finally:
            # Корректная остановка
            self.running = False
            sd.stop()

            await asyncio.sleep(0.2)  # Дослать последние чанки

            # Отправляем финиш-сигнал
            await self._finish_session()

            # Отменяем отправку
            sender_task.cancel()
            with suppress(asyncio.CancelledError):
                await sender_task

            # Финальный рендер
            self._render_output(final=True)
            if self.final_segments:
                print('\n✨ Full transcript:')
                print(' '.join(self.final_segments))

            # Закрытие соединения
            if self.nc and self.nc.is_connected:
                await self.nc.close()
            print('🔌 Disconnected')


from contextlib import suppress


async def main():
    # Инфо об аудио-устройствах
    print('🔊 Available audio devices:')
    for i, dev in enumerate(sd.query_devices()):
        marker = ' ← default' if i == sd.default.device[0] else ''
        print(f'  [{i}] {dev["name"]}{marker}')
    print()

    # Генерация job_id (можно фиксировать для отладки)
    job_id = f'test-{asyncio.get_event_loop().time():.0f}'

    streamer = MicStreamer(job_id=job_id)
    await streamer.run(duration=None)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n👋 Bye!')
    except Exception as e:
        print(f'💥 Fatal error: {e}')
        sys.exit(1)