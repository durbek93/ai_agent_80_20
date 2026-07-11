# -*- coding: utf-8 -*-
import os
from datetime import datetime
from dotenv import load_dotenv

import core

# Загружаем переменные окружения (API ключ Gemini)
load_dotenv()


def process_audio_directly(url):
    """
    Прямой анализ аудио через облачный API Gemini (без Whisper) в консоли.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    audio_path = f"downloads/{timestamp}.mp3"
    result_path = f"results/{timestamp}_audio_summary.txt"

    print(f"📥 Скачиваю только АУДИО: {url}")
    download_success = core.download_media(
        url=url,
        output_path=audio_path,
        audio_only=True
    )
    if not download_success:
        return

    try:
        # Анализ в облаке Gemini с использованием модели gemini-2.5-flash
        summary_text = core.analyze_cloud_audio(
            client=core.client,
            audio_path=audio_path,
            model="gemini-2.5-flash"
        )
        
        with open(result_path, "w", encoding="utf-8") as f:
            f.write(summary_text)
        print(f"✨ Готово! Отчет сохранен: {result_path}")
        
    except Exception as e:
        print(f"❌ Ошибка работы Gemini: {e}")
    finally:
        # Удаляем локальный тяжелый файл
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception:
                pass


if __name__ == "__main__":
    print("="*50)
    print("🎵 СКРИПТ А: Прямой анализ АУДИО через Gemini (без Whisper)")
    print("="*50)
    url = input("Введи ссылку на YouTube: ").strip()
    if url:
        process_audio_directly(url)
