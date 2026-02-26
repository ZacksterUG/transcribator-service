# Stage 1: Сборка
FROM python:3.10-slim AS builder

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libopenblas-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/opt/pydeps --no-cache-dir -r requirements.txt


# Stage 2: Production
FROM python:3.10-slim AS production

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем зависимости в /opt/pydeps
COPY --from=builder /opt/pydeps /opt/pydeps

# Настраиваем окружение
ENV PATH="/opt/pydeps/bin:$PATH"
ENV PYTHONPATH="/opt/pydeps/lib/python3.10/site-packages:$PYTHONPATH"

# Создаем директории для кэша
RUN mkdir -p /tmp/numba_cache /tmp/librosa_cache

COPY . .

# Безопасный пользователь
RUN useradd -r -u 1000 transcriber && \
    chown -R transcriber:transcriber /app /tmp/numba_cache /tmp/librosa_cache
USER transcriber

ENV NUMBA_CACHE_DIR=/tmp/numba_cache
ENV LIBROSA_CACHE_DIR=/tmp/librosa_cache
ENV NUMBA_DISABLE_PERFORMANCE_WARNINGS=1

RUN pip install --prefix=/opt/pydeps --no-cache-dir s3fs==2026.1.0

CMD ["python", "main.py"]