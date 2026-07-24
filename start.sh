#!/bin/bash

echo "🚀 Запускаем ИИ-Агента на Oracle Cloud (ARM)..."

# 0. Подготовка директорий и доступ на хост-системе для appuser в контейнере
mkdir -p downloads results transcripts cache
chmod 777 downloads results transcripts cache 2>/dev/null || true
if [ -f downloads/cookies.txt ]; then
  chmod 666 downloads/cookies.txt 2>/dev/null || true
fi

if [ -f .env ]; then
  chmod 600 .env
fi

# 1. Удаляем старый контейнер, если он завис или существует
docker stop my_ai_bot || true
docker rm my_ai_bot || true

# 2. Запуск новой версии с cgroups-ограничениями ресурсов (Memory, CPU, PIDs)
docker run -d \
  --name my_ai_bot \
  --restart unless-stopped \
  --memory="2g" \
  --cpus="2.0" \
  --pids-limit=100 \
  --env-file .env \
  -v "$(pwd)/downloads:/app/downloads" \
  -v "$(pwd)/results:/app/results" \
  -v "$(pwd)/transcripts:/app/transcripts" \
  ai_agent python3 -u duplicatmain.py

 
