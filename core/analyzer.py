# -*- coding: utf-8 -*-
"""Модуль распознавания речи (STT) и ИИ-аналитики с помощью Gemini API."""
import re
import time
from core.prompts import PROMPT_80_20

_whisper_model = None


def transcribe_local_whisper(audio_path: str, model_size: str = "base") -> str:
    """
    Транскрибирует локальный аудиофайл с помощью модели Whisper.
    Модель лениво загружается при первом вызове.
    
    :param audio_path: Путь к аудиофайлу
    :param model_size: Название модели Whisper (например, 'base')
    """
    global _whisper_model
    import whisper
    if _whisper_model is None:
        print(f"🧠 Загружаю локальную модель Whisper ({model_size})...")
        _whisper_model = whisper.load_model(model_size)
    result = _whisper_model.transcribe(audio_path)
    return result.get("text", "")


def generate_gemini_content_with_retry(client, model: str, contents: list, prompt: str = PROMPT_80_20) -> str:
    """
    Выполняет вызов Gemini API для генерации контента с автоматическим повтором при ошибках 429 и 503.
    
    :param client: Клиент genai.Client
    :param model: Имя модели (например, 'gemini-2.5-flash')
    :param contents: Список вложений (например, объекты File или текст)
    :param prompt: Текст системного промпта
    """
    for attempt in range(3):
        try:
            full_contents = contents + [prompt]
            response = client.models.generate_content(
                model=model,
                contents=full_contents
            )
            if not response.text:
                raise ValueError("Ответ от API пустой (возможно, сработал фильтр безопасности)")
            return response.text
        except Exception as e:
            error_msg = str(e)
            if ("503" in error_msg or "429" in error_msg) and attempt < 2:
                wait_time = 5 if "503" in error_msg else 30
                # Умный парсинг таймера ожидания из ошибки
                match = re.search(r'retry in (\d+\.?\d*)s', error_msg)
                if match:
                    wait_time = int(float(match.group(1))) + 5
                print(f"⏳ Ошибка API ({error_msg}). Повторная попытка через {wait_time} сек...")
                time.sleep(wait_time)
            else:
                raise e
    raise RuntimeError("Не удалось получить ответ от Gemini API после всех попыток.")


def analyze_cloud_audio(client, audio_path: str, model: str = "gemini-2.5-flash", progress_callback=None) -> str:
    """
    Загружает аудиофайл в облако Gemini, дожидается завершения обработки и вызывает ИИ-анализ.
    Гарантированно удаляет временный файл из облака по завершении.
    
    :param client: Клиент genai.Client
    :param audio_path: Локальный путь к MP3-файлу
    :param model: Имя модели для анализа
    :param progress_callback: Callable для обновления статуса на внешнем уровне
    """
    if client is None:
        raise ValueError("Клиент Gemini API не инициализирован.")
        
    uploaded_file = None
    try:
        if progress_callback:
            progress_callback("📤 Загружаю аудио в Google Cloud...")
            
        uploaded_file = client.files.upload(file=audio_path)
        
        elapsed = 0
        while uploaded_file.state.name == "PROCESSING":
            print(".", end="", flush=True)
            if progress_callback and elapsed % 4 == 0:
                progress_callback(f"📤 Облако обрабатывает файл... ({elapsed} сек)")
            time.sleep(2)
            elapsed += 2
            uploaded_file = client.files.get(name=uploaded_file.name)
            
        if uploaded_file.state.name == "FAILED":
            raise RuntimeError("Файл не прошел обработку (FAILED) в облаке Gemini.")
            
        if progress_callback:
            progress_callback("🤖 ИИ анализирует аудио...")
            
        return generate_gemini_content_with_retry(client, model, [uploaded_file])
    finally:
        if uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
                print("\n🧹 Временный файл удален из Google Cloud.")
            except Exception as e:
                print(f"⚠️ Не удалось удалить файл из Google Cloud: {e}")


def analyze_text_content(client, text: str, model: str = "gemini-2.5-flash") -> str:
    """
    Отправляет текстовый контент в Gemini API с системным промптом PROMPT_80_20.
    
    :param client: Клиент genai.Client
    :param text: Исходный текст для суммаризации
    :param model: Имя модели для анализа
    """
    prompt_with_input = f"{PROMPT_80_20}\n\nТекст:\n{text}"
    return generate_gemini_content_with_retry(
        client=client,
        model=model,
        contents=[prompt_with_input]
    )
