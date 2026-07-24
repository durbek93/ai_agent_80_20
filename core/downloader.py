# -*- coding: utf-8 -*-
"""Модуль для работы с yt-dlp (получение метаданных, скачивание видео/аудио)."""
import os
import re
import sys
import time
import subprocess
from datetime import datetime
import yt_dlp

# Общие настройки yt-dlp для обхода блокировок и парсинга n-challenge
YDL_BASE_OPTS = {
    'quiet': True,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
    },
    'remote_components': ['ejs:github'],
}

# Безопасная проверка прав доступа к cookies.txt
cookie_path = 'downloads/cookies.txt'
if os.path.exists(cookie_path):
    try:
        if os.access(cookie_path, os.R_OK | os.W_OK):
            YDL_BASE_OPTS['cookiefile'] = cookie_path
    except Exception:
        pass


def check_and_update_ytdlp(days_interval: int = 5):
    """Проверяет, прошло ли n дней с последнего обновления yt-dlp, и при необходимости обновляет."""
    try:
        os.makedirs('cache', exist_ok=True)
    except Exception:
        pass

    stamp_file = 'cache/.ytdlp_last_update'
    now = time.time()
    
    if os.path.exists(stamp_file):
        try:
            with open(stamp_file, 'r') as f:
                last_update = float(f.read().strip())
            if now - last_update < days_interval * 86400:
                return
        except Exception:
            pass

    try:
        print("🔄 Проверка автообновления yt-dlp (каждые 5 дней)...")
        res = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "--quiet", "--user", "yt-dlp", "yt-dlp-ejs"],
            check=False,
            capture_output=True
        )
        if res.returncode == 0:
            with open(stamp_file, 'w') as f:
                f.write(str(now))
            print("✅ yt-dlp актуален.")
        else:
            print("ℹ️ Пропуск автообновления yt-dlp (стабильная версия используется).")
    except Exception as e:
        print(f"⚠️ Пропуск автообновления yt-dlp: {e}")




def sanitize_title(raw_title: str) -> str:
    """Очищает название видео от спецсимволов и ограничивает длину во избежание OSError."""
    clean = re.sub(r'[^\w\sа-яА-ЯёЁ-]', '', raw_title).strip()
    clean = re.sub(r'\s+', '_', clean)
    if not clean:
        clean = datetime.now().strftime("%Y-%m-%d")
    return clean[:100]


def get_video_info(url: str) -> str:
    """Извлекает и возвращает очищенное название видео."""
    check_and_update_ytdlp(days_interval=5)
    try:
        with yt_dlp.YoutubeDL(YDL_BASE_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            return sanitize_title(info.get('title', 'video'))
    except Exception as e:
        print(f"❌ Ошибка при получении информации о видео: {e}")
        return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def download_media(url: str, output_path: str, audio_only: bool = True, progress_callback=None) -> bool:
    """
    Скачивает видео или аудио по ссылке с возможностью отслеживания прогресса.
    
    :param url: Ссылка на видео YouTube
    :param output_path: Локальный путь сохранения (с расширением .mp3/.mp4)
    :param audio_only: Если True, скачивает и конвертирует в mp3. Иначе скачивает видео mp4.
    :param progress_callback: Callable, принимающий строку процента скачивания (например, '45.2%')
    """
    last_update_time = [time.time()]

    def download_hook(d):
        if d['status'] == 'downloading' and progress_callback:
            percent = d.get('_percent_str', '0%').strip()
            # Убираем цветные ANSI-коды
            percent = re.sub(r'\x1b[^m]*m', '', percent)
            now = time.time()
            if now - last_update_time[0] > 3:
                progress_callback(percent)
                last_update_time[0] = now

    ydl_opts = dict(YDL_BASE_OPTS)
    
    # yt-dlp ожидает шаблон имени без финального расширения в postprocessors
    base_name = output_path
    for ext in ('.mp3', '.mp4'):
        if base_name.endswith(ext):
            base_name = base_name[:-len(ext)]
            
    ydl_opts['outtmpl'] = base_name
    
    if progress_callback:
        ydl_opts['progress_hooks'] = [download_hook]
        
    if audio_only:
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }]
    else:
        ydl_opts['format'] = 'best'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        print(f"❌ Ошибка скачивания через yt-dlp: {e}")
        return False
