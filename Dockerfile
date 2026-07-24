# 1. Базовый дистрибутив Linux с Python 3.12
FROM python:3.12-slim

# 2. Создание системного непривилегированного пользователя для безопасности (Principle of Least Privilege)
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app appuser

# 3. Установка системных утилит (FFmpeg, Node.js, curl, unzip) и фиксация версии Deno (v2.2.3)
ENV DENO_VERSION=v2.2.3
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg nodejs npm curl unzip && rm -rf /var/lib/apt/lists/*
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "aarch64" ]; then DENO_ARCH="aarch64"; else DENO_ARCH="x86_64"; fi && \
    curl -fsSL "https://github.com/denoland/deno/releases/download/${DENO_VERSION}/deno-${DENO_ARCH}-unknown-linux-gnu.zip" -o deno.zip && \
    unzip deno.zip -d /usr/local/bin && \
    rm deno.zip && \
    chmod +x /usr/local/bin/deno

# 4. Настройка рабочей директории
WORKDIR /app

# 5. Копирование зависимостей и установка Python-пакетов
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Создание рабочих директорий и настройка прав доступа
RUN mkdir -p downloads results transcripts && \
    chown -R appuser:appgroup /app

# 7. Копирование исходного кода с правильными правами владения
COPY --chown=appuser:appgroup . .

# 8. Переключение на системного пользователя без root-привилегий
USER appuser

# 9. Команда по умолчанию
CMD ["python3", "-u", "duplicatmain.py"]


