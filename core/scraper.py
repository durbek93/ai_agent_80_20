# -*- coding: utf-8 -*-
"""Модуль для извлечения текстового содержимого (статей, новостей) из веб-страниц."""
import re
import urllib.parse
from datetime import datetime
import requests
import trafilatura
from bs4 import BeautifulSoup

# Заголовки для обхода блокировок
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
}


def is_video_url(url: str) -> bool:
    """
    Проверяет, является ли ссылка видеороликом.
    """
    video_domains = {
        'youtube.com', 'youtu.be',
        'instagram.com',
        'tiktok.com',
        'facebook.com', 'fb.watch',
        'twitter.com', 'x.com',
        'vimeo.com',
        'rutube.ru',
    }
    try:
        parsed_url = urllib.parse.urlparse(url if url.startswith(('http://', 'https://')) else f'http://{url}')
        domain = parsed_url.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]

        if 'vk.com' in domain or 'vkontakte.ru' in domain:
            return '/video' in parsed_url.path.lower()

        for v_domain in video_domains:
            if domain == v_domain or domain.endswith('.' + v_domain):
                return True
    except Exception:
        pass
    return False



def get_page_title(url: str, html_content: str = None) -> str:
    """
    Извлекает заголовок страницы.
    """
    try:
        if not html_content:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            html_content = response.text

        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Сначала ищем og:title
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return og_title['content'].strip()

        # Иначе стандартный tag title
        if soup.title and soup.title.string:
            return soup.title.string.strip()
            
        # Иначе h1
        h1 = soup.find('h1')
        if h1:
            return h1.get_text().strip()
            
    except Exception as e:
        print(f"⚠️ Не удалось извлечь заголовок страницы: {e}")
        
    # Возвращаем доменное имя как фолбек
    try:
        parsed_url = urllib.parse.urlparse(url)
        return parsed_url.netloc
    except Exception:
        return "article"


def extract_article_text(url: str) -> tuple[str, str]:
    """
    Скачивает и извлекает чистый текст статьи из веб-страницы.
    Использует trafilatura как основной парсер и BeautifulSoup как резервный.
    
    Возвращает кортеж (заголовок, текст_статьи).
    """
    html_content = None
    try:
        # Пытаемся скачать страницу через trafilatura
        html_content = trafilatura.fetch_url(url)
    except Exception as e:
        print(f"⚠️ Ошибка загрузки trafilatura: {e}")

    # Если trafilatura не смогла скачать, пробуем через requests
    if not html_content:
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            html_content = response.text
        except Exception as e:
            raise ValueError(f"Не удалось загрузить веб-страницу: {e}")

    title = get_page_title(url, html_content)
    
    # Пытаемся извлечь текст с помощью trafilatura
    text = None
    try:
        text = trafilatura.extract(
            html_content,
            include_comments=False,
            include_tables=True,
            include_links=False,
            no_fallback=False
        )
    except Exception as e:
        print(f"⚠️ Ошибка извлечения через trafilatura: {e}")

    # Фолбек на BeautifulSoup, если trafilatura ничего не извлекла
    if not text:
        print("🔄 trafilatura не вернула контент, используем BeautifulSoup фолбек...")
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Удаляем ненужные теги
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            tag.decompose()
            
        # Пытаемся найти основной контент статьи
        main_content = (
            soup.find('article') or 
            soup.find('main') or 
            soup.find(class_=re.compile(r'post|article|content|body', re.I)) or 
            soup.find(id=re.compile(r'post|article|content|body', re.I))
        )
        
        if main_content:
            raw_text = main_content.get_text('\n')
        else:
            raw_text = soup.get_text('\n')
            
        # Очищаем пустые строки и лишние пробелы
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        text = '\n'.join(lines)

    if not text or len(text.strip()) < 100:
        raise ValueError("Не удалось извлечь содержательный текст из страницы (текст слишком короткий или защищен от скрапинга).")

    return title, text.strip()
