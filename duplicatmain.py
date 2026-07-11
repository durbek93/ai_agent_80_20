# -*- coding: utf-8 -*-
import os
import re
import time
import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from dotenv import load_dotenv

import core

# Настройка логов
logging.basicConfig(level=logging.INFO)

# Загружаем ключи
load_dotenv()


def analyze_audio(url, loop=None, status_msg=None):
    """
    Запускает конвейер: скачивание -> анализ через Gemini API (cloud audio) -> Gemini TTS.
    """
    def update_status(text):
        print(text)
        if loop and status_msg:
            async def _edit():
                try:
                    await status_msg.edit_text(text)
                except Exception as e:
                    print(f"⚠️ Ошибка редактирования TG: {e}")
            asyncio.run_coroutine_threadsafe(_edit(), loop)

    update_status("🔍 [1/5] Получаю информацию о видео...")
    clean_title = core.get_video_info(url)

    file_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    audio_path = f"downloads/{file_id}.mp3"
    result_path = f"results/{file_id}_summary.txt"
    tts_audio_path = f"results/{file_id}_voice.mp3"

    try:
        # ЭТАП 1: Скачивание аудио
        update_status(f"📥 [2/5] Скачиваю аудио:\n«{clean_title}»...")
        download_success = core.download_media(
            url=url,
            output_path=audio_path,
            audio_only=True,
            progress_callback=lambda p: update_status(f"📥 [2/5] Скачиваю аудио: {p}\n«{clean_title}»...")
        )
        if not download_success:
            return None, None, None

        # ЭТАП 2 и 3: Загрузка в облако и анализ ИИ (модель gemini-2.5-pro)
        summary_text = core.analyze_cloud_audio(
            client=core.client,
            audio_path=audio_path,
            model="gemini-2.5-pro",
            progress_callback=lambda status: update_status(status.replace("📥 [2/5]", "").replace("🤖 [4/5]", ""))
        )
        
        # Сохраняем текстовый результат
        with open(result_path, "w", encoding="utf-8") as f:
            f.write(summary_text)

        # ЭТАП 4: Озвучка выжимки через Gemini TTS
        update_status("🎙️ [5/5] Создаю аудио-выжимку через Gemini 2.5 Flash TTS...")
        tts_success = core.run_gemini_tts(
            client=core.client,
            text=summary_text,
            output_path=tts_audio_path
        )
        
        actual_tts_audio_path = tts_audio_path if tts_success else None
        return result_path, actual_tts_audio_path, clean_title

    except Exception as e:
        print(f"❌ Ошибка конвейера ИИ: {e}")
        return None, None, None
        
    finally:
        # ЭТАП 5: Удаление локального тяжелого аудио
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception:
                pass


def analyze_text_article(url, loop=None, status_msg=None):
    """
    Запускает конвейер для статей: скачивание текста -> анализ через Gemini API -> Gemini TTS.
    """
    def update_status(text):
        print(text)
        if loop and status_msg:
            async def _edit():
                try:
                    await status_msg.edit_text(text)
                except Exception as e:
                    print(f"⚠️ Ошибка редактирования TG: {e}")
            asyncio.run_coroutine_threadsafe(_edit(), loop)

    update_status("🔍 [1/4] Скачиваю и извлекаю текст статьи...")
    try:
        title, article_text = core.extract_article_text(url)
        clean_title = core.sanitize_title(title)
    except Exception as e:
        print(f"❌ Ошибка при извлечении текста статьи: {e}")
        return None, None, None

    file_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = f"results/{file_id}_summary.txt"
    tts_audio_path = f"results/{file_id}_voice.mp3"

    try:
        update_status("🤖 [2/4] Gemini анализирует статью (режим 80/20)...")
        summary_text = core.analyze_text_content(
            client=core.client,
            text=article_text,
            model="gemini-2.5-pro"
        )
        
        with open(result_path, "w", encoding="utf-8") as f:
            f.write(summary_text)

        update_status("🎙️ [3/4] Создаю аудио-выжимку через Gemini 2.5 Flash TTS...")
        tts_success = core.run_gemini_tts(
            client=core.client,
            text=summary_text,
            output_path=tts_audio_path
        )
        
        actual_tts_audio_path = tts_audio_path if tts_success else None
        return result_path, actual_tts_audio_path, clean_title

    except Exception as e:
        print(f"❌ Ошибка конвейера ИИ для статьи: {e}")
        return None, None, None


# --- ТЕЛЕГРАМ БОТ ---

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🚀 Привет! Пришли ссылку на видео (YouTube, Shorts, Reels, TikTok и др.) "
        "или статью/новость с любого сайта, и я сделаю аудио-выжимку 80/20."
    )


@dp.message(F.text.regexp(r'https?://[^\s]+'))
async def handle_link(message: types.Message):
    status = await message.answer("⏳ Запуск конвейера...")
    
    # ИЩЕМ ЧИСТУЮ ССЫЛКУ В ТЕКСТЕ СООБЩЕНИЯ
    url_match = re.search(r'(https?://[^\s]+)', message.text)
    if not url_match:
        await status.edit_text("❌ Не смог найти правильную ссылку в сообщении.")
        return
        
    clean_url = url_match.group(1)
    
    loop = asyncio.get_running_loop()
    
    if core.is_video_url(clean_url):
        res_txt, res_audio, clean_title = await asyncio.to_thread(analyze_audio, clean_url, loop, status)
    else:
        res_txt, res_audio, clean_title = await asyncio.to_thread(analyze_text_article, clean_url, loop, status)
    
    if res_txt and os.path.exists(res_txt):
        await status.edit_text("✅ Готово! Лови суть:")
        
        if res_audio and os.path.exists(res_audio):
            await message.answer_audio(
                FSInputFile(res_audio, filename=f"{clean_title}_voice.mp3"),
                caption="🎧 Голосовая выжимка"
            )
        
        await message.answer_document(
            FSInputFile(res_txt, filename=f"{clean_title}_summary.txt"),
            caption="📝 Текстовый отчет 80/20"
        )
    else:
        await status.edit_text("❌ Что-то пошло не так. Проверь логи сервера.")


async def main():
    print("🤖 Бот на базе Gemini Cloud Audio запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
