# -*- coding: utf-8 -*-
"""Модуль для озвучки текста (Text-To-Speech) через edge-tts или Gemini API."""
import os
import tempfile
from google.genai import types as genai_types


def clean_text_for_tts(text: str) -> str:
    """Удаляет спецсимволы (звездочки, решетки), которые мешают озвучке."""
    return text.replace('*', '').replace('#', '')


def run_edge_tts(text: str, output_path: str, voice: str = "ru-RU-DmitryNeural") -> bool:
    """
    Озвучивает текст через утилиту edge-tts.
    
    :param text: Исходный текст
    :param output_path: Путь для сохранения .mp3
    :param voice: Имя голоса в edge-tts
    """
    try:
        clean_text = clean_text_for_tts(text)
        
        # Записываем во временный файл во избежание Command Injection через CLI-параметры
        fd, temp_path = tempfile.mkstemp(suffix=".txt")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(clean_text)
                
            exit_code = os.system(f'edge-tts --voice {voice} -f "{temp_path}" --write-media "{output_path}"')
            if exit_code == 0 and os.path.exists(output_path):
                return True
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    except Exception as e:
        print(f"⚠️ Ошибка при генерации edge-tts: {e}")
    return False


def run_gemini_tts(client, text: str, output_path: str) -> bool:
    """
    Озвучивает текст средствами Gemini Cloud TTS и конвертирует RAW PCM в MP3 через ffmpeg.
    
    :param client: Инициализированный клиент genai.Client
    :param text: Текст для озвучки
    :param output_path: Путь для сохранения .mp3
    """
    if client is None:
        print("⚠️ Клиент Gemini API не инициализирован.")
        return False
        
    try:
        clean_text = clean_text_for_tts(text)
        prompt_tts = f"Read the following text out loud, do not generate any text responses, just audio:\n\n{clean_text}"
        
        tts_response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=prompt_tts,
            config=genai_types.GenerateContentConfig(
                response_modalities=["AUDIO"],
            )
        )
        
        if getattr(tts_response, 'candidates', None) and len(tts_response.candidates) > 0:
            for part in tts_response.candidates[0].content.parts:
                if part.inline_data:
                    # RAW PCM (24kHz, 16-bit, Mono) -> MP3
                    fd, temp_raw_path = tempfile.mkstemp(suffix=".raw")
                    try:
                        with os.fdopen(fd, 'wb') as f:
                            f.write(part.inline_data.data)
                        
                        exit_code = os.system(
                            f'ffmpeg -y -f s16le -ar 24000 -ac 1 -i "{temp_raw_path}" -b:a 128k "{output_path}" -loglevel error'
                        )
                        if exit_code == 0 and os.path.exists(output_path):
                            return True
                    finally:
                        if os.path.exists(temp_raw_path):
                            os.remove(temp_raw_path)
                            
    except Exception as e:
        print(f"⚠️ Ошибка при генерации Gemini Cloud TTS: {e}")
    return False
