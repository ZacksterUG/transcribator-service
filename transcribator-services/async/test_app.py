import json
import os
import datetime
import asyncio
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

JOB_ID = "test-job-123"
FILE_PATH = "audio.mp3"
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

    print(f"📁 Uploading {FILE_PATH} to s3://{MINIO_BUCKET}/{remote_path}")

    with open(FILE_PATH, 'rb') as local_file:
        with fs.open(f"{MINIO_BUCKET}/{remote_path}", 'wb') as remote_file:
            remote_file.write(local_file.read())

    print(f"✅ File uploaded successfully")
    return remote_path

async def publish_to_nats_jetstream(remote_path):
    """Публикует сообщение через JetStream"""
    nc = await nats.connect(servers=NATS_SERVERS)
    js = nc.jetstream()
    
    # Гарантируем существование стримов
    try:
        # Стрим для запросов
        await js.add_stream(
            name="TRANSCRIBE_REQUESTS",
            subjects=[REQUEST_TOPIC],
            retention=RetentionPolicy.LIMITS,
            max_age=72 * 3600,  # 72 часа
            storage=StorageType.FILE
        )
        print("✅ Request stream ensured")
    except Exception as e:
        if "already in use" not in str(e).lower():
            print(f"⚠️  Failed to create request stream: {e}")
    
    try:
        # Стрим для ответов
        await js.add_stream(
            name="TRANSCRIBE_RESPONSES",
            subjects=[RESPONSE_TOPIC],
            retention=RetentionPolicy.LIMITS,
            max_age=24 * 3600,  # 24 часа
            storage=StorageType.FILE
        )
        print("✅ Response stream ensured")
    except Exception as e:
        if "already in use" not in str(e).lower():
            print(f"⚠️  Failed to create response stream: {e}")

    request_data = {
        "job_id": JOB_ID,
        "input_type": "file",
        "audio_source": {
            "path": remote_path
        },
        "created_at": datetime.datetime.now().isoformat()
    }

    message = json.dumps(request_data).encode('utf-8')

    print(f"📨 Publishing to JetStream topic '{REQUEST_TOPIC}'")
    await js.publish(REQUEST_TOPIC, message)  # ← Используем js.publish, не nc.publish!
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