# -*- coding: utf-8 -*-
import os
import time
from datetime import datetime
from dotenv import load_dotenv

import core

# Загружаем переменные окружения (API ключ Gemini)
load_dotenv()


def process_url(url):
    """
    Пакетная обработка ссылок в консоли (видео или статьи):
    - Видео: скачивание -> Whisper STT -> Gemini API -> Edge-TTS.
    - Статьи: скрапинг текста -> Gemini API -> Edge-TTS.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    result_path = f"results/{timestamp}_summary.txt"
    audio_path = f"results/{timestamp}_audio.mp3"

    is_video = core.is_video_url(url)

    if is_video:
        print(f"📹 ОБНАРУЖЕНО ВИДЕО: {url}")
        video_path = f"downloads/{timestamp}.mp4"
        transcript_path = f"transcripts/{timestamp}_transcript.txt"

        # --- ЭТАП 1: СКАЧИВАНИЕ ---
        print(f"📥 Скачиваю: {url}")
        download_success = core.download_media(
            url=url,
            output_path=video_path,
            audio_only=False
        )
        if not download_success:
            return None, None

        # --- ЭТАП 2: РАСПОЗНАВАНИЕ ---
        print("🎧 Слушаю аудио и перевожу в текст (Whisper STT)...")
        try:
            transcript_text = core.transcribe_local_whisper(
                audio_path=video_path,
                model_size="base"
            )
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(transcript_text)
            print(f"📝 Текст сохранен: {transcript_path}")
        except Exception as e:
            print(f"❌ Ошибка распознавания речи: {e}")
            if os.path.exists(video_path):
                os.remove(video_path)
            return None, None

        # --- ЭТАП 3: СУММАРИЗАЦИЯ GEMINI ---
        print("🤖 Gemini анализирует текст (режим 80/20)...")
        try:
            prompt_with_input = f"{core.PROMPT_80_20}\n\nТекст:\n{transcript_text}"
            summary_text = core.generate_gemini_content_with_retry(
                client=core.client,
                model="gemini-2.5-flash",
                contents=[prompt_with_input]
            )
            with open(result_path, "w", encoding="utf-8") as f:
                f.write(summary_text)
            print(f"✨ Готово! Отчет 80/20 сохранен: {result_path}")
        except Exception as e:
            print(f"❌ Ошибка работы Gemini: {e}")
            if os.path.exists(video_path):
                os.remove(video_path)
            if os.path.exists(transcript_path):
                os.remove(transcript_path)
            return None, None

        # --- ЭТАП 4: ОЗВУЧКА ---
        print("🎙️ Подготавливаю текст для диктора...")
        tts_success = core.run_edge_tts(
            text=summary_text,
            output_path=audio_path,
            voice="ru-RU-DmitryNeural"
        )
        if tts_success:
            print(f"🔊 Аудио сохранено: {audio_path}")
        else:
            print("❌ Ошибка при создании аудио.")

        # --- ЭТАП 5: ОЧИСТКА МУСОРА ---
        print("🧹 Убираю за собой временные файлы...")
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
            if os.path.exists(transcript_path):
                os.remove(transcript_path)
            print("✨ Чистота наведена!")
        except Exception as e:
            print(f"⚠️ Ошибка при удалении файлов: {e}")

    else:
        print(f"📰 ОБНАРУЖЕНА СТАТЬЯ: {url}")
        
        # --- ЭТАП 1: СКРАПИНГ ТЕКСТА ---
        print("🔍 Извлекаю текст статьи...")
        try:
            title, article_text = core.extract_article_text(url)
            print(f"🎬 Заголовок статьи: {title}")
            print(f"📝 Длина извлеченного текста: {len(article_text)} символов.")
        except Exception as e:
            print(f"❌ Ошибка при извлечении статьи: {e}")
            return None, None

        # --- ЭТАП 2: СУММАРИЗАЦИЯ GEMINI ---
        print("🤖 Gemini анализирует текст статьи (режим 80/20)...")
        try:
            summary_text = core.analyze_text_content(
                client=core.client,
                text=article_text,
                model="gemini-2.5-flash"
            )
            with open(result_path, "w", encoding="utf-8") as f:
                f.write(summary_text)
            print(f"✨ Готово! Отчет 80/20 сохранен: {result_path}")
        except Exception as e:
            print(f"❌ Ошибка работы Gemini: {e}")
            return None, None

        # --- ЭТАП 3: ОЗВУЧКА ---
        print("🎙️ Подготавливаю текст для диктора...")
        tts_success = core.run_edge_tts(
            text=summary_text,
            output_path=audio_path,
            voice="ru-RU-DmitryNeural"
        )
        if tts_success:
            print(f"🔊 Аудио сохранено: {audio_path}")
        else:
            print("❌ Ошибка при создании аудио.")

    # Задержка для обхода лимитов
    print("⏳ Охлаждаю системы 15 секунд...")
    time.sleep(15)

    return result_path, (audio_path if tts_success else None)


def main():
    print("="*50)
    print("🚀 ИИ-АГЕНТ: Пакетная обработка ссылок (видео / статьи)")
    print("="*50)
    print("Введи ссылки на видео или статьи (по одной на строку).")
    print("Когда введешь все ссылки, просто нажми Enter на пустой строке.\n")

    urls = []
    while True:
        url = input("Ссылка (или Enter для старта): ").strip()
        if not url:
            break
        urls.append(url)

    if not urls:
        print("Ссылки не добавлены. Отмена.")
        return

    print(f"\n🔥 Начинаю обработку {len(urls)} ссылок...")
    for i, url in enumerate(urls, 1):
        print(f"\n--- Запускаю цикл {i} из {len(urls)} ---")
        process_url(url)

    print("\n🎉 Вся партия успешно обработана!")


if __name__ == "__main__":
    main()
