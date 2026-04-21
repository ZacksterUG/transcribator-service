# API Design

## PostgreSQL Tables

```sql
CREATE TABLE jobs.transcription_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('sync', 'async')),
    job_folder TEXT,              -- только для async (nullable)
    file_name TEXT,              -- только для async (nullable)
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);
```

### Endpoints (async)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/async-jobs` | Загрузить файл на транскрибацию |
| GET | `/api/async-jobs` | Список задач пользователя |
| GET | `/api/async-jobs/{id}` | Получить задачу |
| DELETE | `/api/async-jobs/{id}` | Удалить задачу |

---

## Sync (WebSocket)

## POST /api/async-jobs

Загрузить файл на транскрибацию.

**Request:** multipart/form-data
- `file` — аудиофайл

**Response (201):**
```json
{
  "id": "uuid",
  "user_id": "user123",
  "job_folder": "uuid/",
  "file_name": "audio.wav",
  "created_at": "2026-01-01T00:00:00Z"
}
```

---

## GET /api/async-jobs

Список async задач пользователя.

**Query params:**
- `limit` (default 20)
- `offset` (default 0)

**Response (200):**
```json
{
  "jobs": [
    {
      "id": "uuid",
      "job_folder": "uuid/",
      "file_name": "audio.wav",
      "created_at": "2026-01-01T00:00:00Z",
      "finished_at": null
    }
  ],
  "limit": 20,
  "offset": 0,
  "total": 100
}
```

---

## GET /api/async-jobs/{id}

Получить задачу.

**Response (200):**
```json
{
  "id": "uuid",
  "job_folder": "uuid/",
  "file_name": "audio.wav",
  "error_message": null,
  "created_at": "2026-01-01T00:00:00Z",
  "finished_at": "2026-01-01T00:05:00Z"
}
```

**Errors:**
- 404 — задача не найдена

---

## DELETE /api/async-jobs/{id}

Удалить задачу.

**Response (204):** No content

---

## GET /api/async-jobs/{id}/files

Список файлов задачи в MinIO.

**Response (200):**
```json
{
  "files": [
    {
      "key": "uuid/audio.wav",
      "size": 1024000
    },
    {
      "key": "uuid/result.json",
      "size": 512
    }
  ]
}
```

---

## GET /api/async-jobs/{id}/files/{file_key}

Скачать файл задачи.

**Response (200):** Binary file

---

## GET /api/async-jobs/{id}/result

Получить результат транскрибации (из MinIO result.json).

**Response (200):**
```json
{
  "job_id": "uuid",
  "results": [...]
}
```

---

## Sync (WebSocket)

Sync работает через WebSocket — записывает сессию в БД, клиент подключается по session_id.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/sync-sessions` | Создать сессию (получить session_id) |

### WebSocket

```
WS /api/sync?session_id={id}&token={jwt}
```

Клиент подключается к WebSocket и передаёт аудио. Результаты приходят в WebSocket.

### POST /api/sync-sessions

Создать сессию.

**Response (201):**
```json
{
  "id": "uuid",
  "user_id": "user123",
  "created_at": "2026-01-01T00:00:00Z"
}
```

Notes:

- `user_id` — строка (Keycloak subject / внешний ID от сервиса)
- `job_folder` — папка в MinIO (только для async)
- Для sync — результаты передаются напрямую через WebSocket/NATS, без MinIO
- Актуальный статус — из Redis / MinIO result.json (async)
- `finished_at` — заполняется API после завершения