import requests
import json
import time
import feedparser
from datetime import datetime
from openai import OpenAI
from bs4 import BeautifulSoup

# ===== НАСТРОЙКИ (через переменные окружения) =====
import os
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

HISTORY_FILE = "sent_news.json"  # файл будет сохраняться в хранилище

# ===== ИНИЦИАЛИЗАЦИЯ =====
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

def load_history():
    try:
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"titles": []}

def save_history(titles):
    with open(HISTORY_FILE, 'w') as f:
        json.dump({"titles": titles}, f)

def get_news():
    """Парсит новости из retail.ru и shoppers.media"""
    all_news = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # --- 1. Парсинг retail.ru (без изменений) ---
    try:
        url = "https://www.retail.ru/news/"
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        for article in soup.select('article')[:5]:
            title_elem = article.find('h2') or article.find('a')
            if title_elem:
                title = title_elem.text.strip()
                if title:
                    all_news.append({
                        "title": title,
                        "link": "https://www.retail.ru" + title_elem.get('href', ''),
                        "summary": title,
                        "source": "retail.ru"
                    })
    except Exception as e:
        print(f"⚠️ Ошибка парсинга retail.ru: {e}")

    # --- 2. Парсинг shoppers.media (исправленный) ---
    try:
        url = "https://shoppers.media/news"
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Ищем все элементы, которые выглядят как ссылки на новости.
        # На сайте shoppers.media новости часто находятся внутри <a> с классом, содержащим "news" или "item",
        # либо внутри <div class="...news-item...">.
        # Наиболее надёжный способ — найти все ссылки, у которых в атрибуте href есть "/news/" или "news/"
        for a in soup.find_all('a', href=True):
            link = a['href']
            # Проверяем, что ссылка ведёт на страницу новости
            if '/news/' in link or link.startswith('news/') or 'shoppers.media/news/' in link:
                title = a.text.strip()
                # Проверяем, что заголовок не пустой и не слишком короткий (отсеиваем "Читать далее" и т.п.)
                if title and len(title) > 10 and not title.startswith('Читать'):
                    # Преобразуем относительную ссылку в абсолютную
                    if not link.startswith('http'):
                        link = 'https://shoppers.media' + link
                    # Проверяем, не добавили ли мы уже эту новость (избегаем дублей внутри источника)
                    if not any(news['title'] == title for news in all_news):
                        all_news.append({
                            "title": title,
                            "link": link,
                            "summary": title,
                            "source": "shoppers.media"
                        })
                        # Останавливаемся, как только собрали 5 новостей
                        if len([news for news in all_news if news['source'] == 'shoppers.media']) >= 5:
                            break

    except Exception as e:
        print(f"⚠️ Ошибка парсинга shoppers.media: {e}")

    # --- 3. Возвращаем собранные новости (максимум 10) ---
    return all_news[:10]

def make_post(news_item):
    prompt = f"""
Ты — редактор Telegram-канала о ритейле в России. Напиши пост по этой новости:

Название: {news_item['title']}
Ссылка: {news_item['link']}
Краткое содержание: {news_item['summary']}

ТВОЙ ОТВЕТ — ТОЛЬКО ЭТА СТРУКТУРА (без пояснений):

📌 ЗАГОЛОВОК (до 10 слов) — [ЦИФРА] + [КОМПАНИЯ] + [ДЕЙСТВИЕ]

📄 ПЕРВЫЙ АБЗАЦ (ровно 2 предложения):
- Факт: что случилось
- Смысл: для кого это важно

📄 ВТОРОЙ АБЗАЦ (2 предложения):
- Контекст: почему это произошло
- Прогноз: что будет дальше (если есть)

СТИЛЬ: сухой, фактологический. Цифры — цифрами.

ХЕШТЕГИ: #ритейл # [название_компании_латиницей]
ИСТОЧНИК: retail.ru

ВАЖНО: если в новости нет компании ИЛИ цифры — напиши ровно одну строку: "ПРОПУСТИТЬ"
"""
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ Ошибка DeepSeek: {e}")
        return None

def send_to_telegram(text):
    """Отправляет пост в канал через HTTP"""
    if not text or "ПРОПУСТИТЬ" in text:
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ Отправлено: {text[:50]}...")
            return True
        else:
            print(f"❌ Ошибка: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def main():
    """Запуск агента (один раз)"""
    print(f"🚀 Запуск в {datetime.now()}")
    
    # 1. Загружаем историю
    history = load_history()
    sent_titles = history.get("titles", [])
    
    # 2. Получаем новости
    news = get_news()
    print(f"📰 Найдено новостей: {len(news)}")
    
    # 3. Обрабатываем каждую новость
    for item in news:
        if item['title'] in sent_titles:
            print(f"⏭️ Пропускаем (уже отправлено): {item['title'][:30]}...")
            continue
        
        print(f"📝 Обработка: {item['title']}")
        post_text = make_post(item)
        if post_text:
            send_to_telegram(post_text)
            sent_titles.append(item['title'])
            save_history(sent_titles)
            time.sleep(2)  # пауза между постами
    
    print("✅ Завершено")

if __name__ == "__main__":
    main()
