# -*- coding: utf-8 -*-
import os
import sys
import re
from datetime import datetime
from dotenv import load_dotenv

import core

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    print("❌ Для этого скрипта нужна библиотека youtube-transcript-api.")
    print("Установи её в консоли командой: pip install youtube-transcript-api")
    sys.exit(1)

# Загружаем переменные окружения (API ключ Gemini)
load_dotenv()


def get_video_id(url):
    """Извлекает ID видео из ссылки YouTube."""
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    if match:
        return match.group(1)
    return None


def process_subtitles_directly(url):
    """
    Анализирует видео по его субтитрам (без скачивания медиафайлов).
    """
    result_path = f"results/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_subs_summary.txt"
    
    video_id = get_video_id(url)
    if not video_id:
        print("❌ Не удалось извлечь ID видео из ссылки.")
        return

    print(f"📥 Скачиваю субтитры для видео: {video_id}")
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            transcript = transcript_list.find_transcript(['ru', 'en'])
        except Exception:
            # Если нет ru/en, берем первый попавшийся и переводим на русский
            transcript = list(transcript_list)[0]
            transcript = transcript.translate('ru')
            
        subs_data = transcript.fetch()
        transcript_text = " ".join([t['text'] for t in subs_data])
        print(f"✅ Субтитры успешно скачаны ({len(transcript_text)} символов).")
    except Exception as e:
        print(f"❌ Ошибка получения субтитров (возможно, они отключены для этого видео): {e}")
        return

    print("🤖 Gemini анализирует текст субтитров (режим 80/20)...")
    try:
        prompt_with_input = f"{core.PROMPT_80_20}\n\nТекст субтитров:\n{transcript_text}"
        summary_text = core.generate_gemini_content_with_retry(
            client=core.client,
            model="gemini-2.5-flash",
            contents=[prompt_with_input]
        )
        
        with open(result_path, "w", encoding="utf-8") as f:
            f.write(summary_text)
        print(f"✨ Готово! Отчет сохранен: {result_path}")
    except Exception as e:
        print(f"❌ Ошибка работы Gemini: {e}")


if __name__ == "__main__":
    print("="*50)
    print("📝 СКРИПТ Б: Анализ СУБТИТРОВ (Мгновенно, без аудио)")
    print("="*50)
    url = input("Введи ссылку на YouTube: ").strip()
    if url:
        process_subtitles_directly(url)
