# -*- coding: utf-8 -*-
"""Модуль для работы с yt-dlp (получение метаданных, скачивание видео/аудио)."""
import os
import re
import sys
import time
import subprocess
from datetime import datetime
import yt_dlp

# Общие настройки yt-dlp для обхода блокировок
YDL_BASE_OPTS = {
    'quiet': True,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
    },
    'js_runtimes': {'quickjs': {}, 'node': {}, 'deno': {}},
    'remote_components': ['ejs:github'],
}

COOKIE_PATH = 'downloads/cookies.txt'


def _get_cookie_path():
    """Возвращает путь к файлу cookies.txt, если он существует и доступен."""
    if os.path.exists(COOKIE_PATH):
        try:
            if os.access(COOKIE_PATH, os.R_OK):
                return COOKIE_PATH
        except Exception:
            pass
    return None


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
    
    # Стратегия 1: Без куков (позволяет обойти блокировку SABR-эксперимента на аккаунте)
    opts_no_cookies = dict(YDL_BASE_OPTS)
    try:
        with yt_dlp.YoutubeDL(opts_no_cookies) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and info.get('title'):
                return sanitize_title(info['title'])
    except Exception as e:
        print(f"ℹ️ Не удалось получить инфо без куков ({e}), пробуем с cookies.txt...")

    # Стратегия 2: С файлом куки (для видео с ограничением по возрасту / закрытых)
    cookie_file = _get_cookie_path()
    if cookie_file:
        opts_cookies = dict(YDL_BASE_OPTS)
        opts_cookies['cookiefile'] = cookie_file
        try:
            with yt_dlp.YoutubeDL(opts_cookies) as ydl:
                info = ydl.extract_info(url, download=False)
                if info and info.get('title'):
                    return sanitize_title(info['title'])
        except Exception as e:
            print(f"❌ Ошибка при получении информации о видео с куками: {e}")

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
            percent = re.sub(r'\x1b[^m]*m', '', percent)
            now = time.time()
            if now - last_update_time[0] > 3:
                progress_callback(percent)
                last_update_time[0] = now

    base_name = output_path
    for ext in ('.mp3', '.mp4'):
        if base_name.endswith(ext):
            base_name = base_name[:-len(ext)]

    def _build_opts(use_cookies: bool = False, extractor_args: dict = None):
        opts = dict(YDL_BASE_OPTS)
        opts['outtmpl'] = base_name
        if progress_callback:
            opts['progress_hooks'] = [download_hook]
        if audio_only:
            opts['format'] = 'bestaudio/best'
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }]
        else:
            opts['format'] = 'best'
        if use_cookies and _get_cookie_path():
            opts['cookiefile'] = _get_cookie_path()
        if extractor_args:
            opts['extractor_args'] = extractor_args
        return opts

    # 1. Попытка скачивания без куков (для обхода SABR-эксперимента аккаунта)
    try:
        with yt_dlp.YoutubeDL(_build_opts(use_cookies=False)) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        print(f"⚠️ Скачивание без куков не удалось ({e}). Пробуем альтернативные варианты...")

    # 2. Попытка скачивания с куками
    if _get_cookie_path():
        try:
            with yt_dlp.YoutubeDL(_build_opts(use_cookies=True)) as ydl:
                ydl.download([url])
            return True
        except Exception as e:
            print(f"⚠️ Скачивание с куками не удалось ({e})...")

    # 3. Попытка скачивания через mweb / tv плеер
    for client in ('mweb,web', 'android,web'):
        try:
            print(f"🔄 Пробуем клиент {client}...")
            with yt_dlp.YoutubeDL(_build_opts(use_cookies=False, extractor_args={'youtube': {'player_client': [client]}})) as ydl:
                ydl.download([url])
            return True
        except Exception as e:
            print(f"⚠️ Попытка с клиентом {client} не удалась: {e}")

    return False

