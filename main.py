# -*- coding: utf-8 -*-
import os
import re
import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from dotenv import load_dotenv

import core

logging.basicConfig(level=logging.INFO)

# Загружаем переменные окружения (API ключ Gemini)
load_dotenv()


def process_video(url, loop=None, status_msg=None):
    """
    Запускает конвейер: скачивание видео -> распознавание Whisper -> анализ Gemini -> Edge-TTS.
    """
    def update_status(text):
        print(text)
        if loop and status_msg:
            try:
                asyncio.run_coroutine_threadsafe(status_msg.edit_text(text), loop)
            except Exception:
                pass

    update_status("🔍 [1/5] Получаю информацию о видео...")
    clean_title = core.get_video_info(url)
    
    video_path = f"downloads/{clean_title}.mp4"
    transcript_path = f"transcripts/{clean_title}_transcript.txt"
    result_path = f"results/{clean_title}_summary.txt"
    audio_path = f"results/{clean_title}_audio.mp3"

    # --- ЭТАП 1: СКАЧИВАНИЕ ---
    update_status(f"📥 [2/5] Скачиваю видео:\n«{clean_title}»...")
    download_success = core.download_media(
        url=url,
        output_path=video_path,
        audio_only=False,
        progress_callback=lambda p: update_status(f"📥 [2/5] Скачиваю видео: {p}\n«{clean_title}»...")
    )
    if not download_success:
        return None, None

    # --- ЭТАП 2: РАСПОЗНАВАНИЕ ---
    update_status("🎧 [3/5] Whisper распознает речь...")
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
        return None, None

    # --- ЭТАП 3: СУММАРИЗАЦИЯ GEMINI ---
    update_status("🤖 [4/5] Gemini анализирует текст...")
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
        return None, None

    # --- ЭТАП 4: ОЗВУЧКА ---
    update_status("🎙️ [5/5] Создаю аудио-выжимку...")
    tts_success = core.run_edge_tts(
        text=summary_text,
        output_path=audio_path,
        voice="ru-RU-DmitryNeural"
    )
    if not tts_success:
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

    return result_path, (audio_path if tts_success else None)


# --- ТЕЛЕГРАМ БОТ ---

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
raw_allowed = os.getenv("ALLOWED_TELEGRAM_USERS", "").strip()
ALLOWED_USERS = set(int(uid.strip()) for uid in raw_allowed.split(",") if uid.strip().isdigit()) if raw_allowed else set()

def is_user_allowed(user_id: int) -> bool:
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS

def validate_env():
    gemini_key = os.getenv("GEMINI_API_KEY")
    missing = []
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "your_telegram_bot_token_here":
        missing.append("TELEGRAM_TOKEN")
    if not gemini_key or gemini_key == "your_gemini_api_key_here":
        missing.append("GEMINI_API_KEY")
    if missing:
        raise ValueError(f"❌ Ошибка конфигурации: Переменные {', '.join(missing)} не заданы в .env!")

if TELEGRAM_TOKEN:
    bot = Bot(token=TELEGRAM_TOKEN)
else:
    bot = None

dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not is_user_allowed(message.from_user.id):
        await message.answer("⛔ Доступ ограничен. Ваш Telegram ID не находится в списке разрешенных.")
        return
    await message.answer(
        "👋 Привет! Я твой личный ИИ-Аналитик.\n"
        "Отправь мне ссылку на YouTube, и я пришлю тебе аудио-выжимку 80/20 и текстовый отчет."
    )


@dp.message(F.text.contains("youtu"))
async def process_youtube_link(message: types.Message):
    if not is_user_allowed(message.from_user.id):
        await message.answer("⛔ Доступ ограничен. Ваш Telegram ID не находится в списке разрешенных.")
        return

    url = message.text
    status_msg = await message.answer("⏳ Запуск конвейера...")
    
    try:
        loop = asyncio.get_running_loop()
        result_path, audio_path = await asyncio.to_thread(process_video, url, loop, status_msg)
        
        if result_path and audio_path:
            await status_msg.edit_text("✅ Анализ завершен! Отправляю файлы...")
            
            audio_file = FSInputFile(audio_path)
            await message.answer_audio(audio_file)
            
            text_file = FSInputFile(result_path)
            await message.answer_document(text_file)
        else:
            await status_msg.edit_text("❌ Произошла ошибка. Проверь консоль Ubuntu.")
            
    except Exception as e:
        await status_msg.edit_text(f"❌ Системная ошибка: {e}")


async def main():
    validate_env()
    if ALLOWED_USERS:
        logging.info(f"🔒 Авторизация включена для {len(ALLOWED_USERS)} пользователей.")
    else:
        logging.warning("⚠️ Внимание: ALLOWED_TELEGRAM_USERS не задан в .env. Бот доступен всем!")
    print("🤖 Бот запущен и слушает Telegram!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())