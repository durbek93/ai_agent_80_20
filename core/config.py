# -*- coding: utf-8 -*-
"""Инициализация конфигурации, папок проекта и клиента Gemini API."""
import os
from google import genai
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Автоматическое создание необходимых директорий
DIRS = ['downloads', 'results', 'transcripts']
for directory in DIRS:
    os.makedirs(directory, exist_ok=True)

# Инициализация Gemini API клиента
client = None
try:
    client = genai.Client()
    print("✅ Gemini API подключен.")
except Exception as e:
    print(f"❌ Ошибка инициализации Gemini API: {e}")
