import json
import os
import datetime
import asyncio
import uuid

import nats
from nats.js.api import RetentionPolicy, StorageType

from fsspec import filesystem

MINIO_URL = "http://127.0.0.1:9000"
MINIO_USER = "rootuser"
MINIO_PASSWORD = "rootpassword"
MINIO_BUCKET = "transcribe"

NATS_SERVERS = ['nats://localhost:4222']
REQUEST_TOPIC = "transcriber.async.request"
RESPONSE_TOPIC = "transcriber.async.response"  # добавьте этот топик в .env

JOB_ID = str(uuid.uuid4())
FILE_PATH = "audio_extended.mp4"
# audio.mp3
# audio_extended.mp4
# archive.zip
FILE_NAME = os.path.basename(FILE_PATH)

def upload_to_minio():
    fs = filesystem(
        's3',
        key=MINIO_USER,
        secret=MINIO_PASSWORD,
        client_kwargs={
            'endpoint_url': MINIO_URL,
            'region_name': 'us-east-1'
        }
    )

    remote_path = f"transcribe/{JOB_ID}/{FILE_NAME}"

    print(f"📁 Uploading {FILE_PATH} to s3:///{remote_path}")

    with open(FILE_PATH, 'rb') as local_file:
        with fs.open(f"/{remote_path}", 'wb') as remote_file:
            remote_file.write(local_file.read())

    print(f"✅ File uploaded successfully")
    return remote_path

async def publish_to_nats_jetstream(remote_path):
    """Публикует сообщение через JetStream"""
    nc = await nats.connect(servers=NATS_SERVERS)
    js = nc.jetstream()
    
    # ИСПОЛЬЗУЕМ ТО ЖЕ ИМЯ СТРИМА, ЧТО И В NATSQUEUE!
    STREAM_NAME = f"STREAM_{REQUEST_TOPIC.replace('.', '_').upper()}"  # ← КЛЮЧЕВОЕ ИЗМЕНЕНИЕ
    
    # Гарантируем существование стримов
    try:
        await js.add_stream(
            name=STREAM_NAME,  # ← ИСПРАВЛЕНО
            subjects=[REQUEST_TOPIC],
            retention=RetentionPolicy.LIMITS,
            max_age=72 * 3600,
            storage=StorageType.FILE
        )
        print(f"✅ Stream {STREAM_NAME} ensured")
    except Exception as e:
        if "already in use" not in str(e).lower():
            print(f"⚠️ Failed to create stream: {e}")

    request_data = {
        "job_id": JOB_ID,
        "input_type": "file",
        "audio_source": {
            "path": remote_path
        },
        "created_at": datetime.datetime.now().isoformat()
    }

    message = json.dumps(request_data).encode('utf-8')
    print(f"📨 Publishing to JetStream topic '{REQUEST_TOPIC}' in stream '{STREAM_NAME}'")
    
    await js.publish(REQUEST_TOPIC, message)
    print("✅ Message published via JetStream")

    await nc.close()

async def main():
    try:
        remote_path = upload_to_minio()
        await publish_to_nats_jetstream(remote_path)
        print(f"\n🎉 Job sent successfully via JetStream. Job ID: {JOB_ID}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())