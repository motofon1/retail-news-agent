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
    """Парсит новости с retail.ru"""
    all_news = []
    try:
        url = "https://www.retail.ru/news/"
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ищем новости (селектор может отличаться)
        for article in soup.select('article')[:5]:
            title_elem = article.find('h2') or article.find('a')
            if title_elem:
                all_news.append({
                    "title": title_elem.text.strip(),
                    "link": "https://www.retail.ru" + title_elem.get('href', ''),
                    "summary": title_elem.text.strip()
                })
    except Exception as e:
        print(f"⚠️ Ошибка парсинга: {e}")
    return all_news

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
