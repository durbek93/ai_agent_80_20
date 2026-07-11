# -*- coding: utf-8 -*-
"""ИИ-Агент Аналитик 80/20. Ядро системы."""

from core.config import client
from core.prompts import PROMPT_80_20
from core.downloader import get_video_info, download_media, sanitize_title
from core.tts import run_edge_tts, run_gemini_tts
from core.scraper import is_video_url, extract_article_text
from core.analyzer import (
    transcribe_local_whisper,
    generate_gemini_content_with_retry,
    analyze_cloud_audio,
    analyze_text_content,
)

