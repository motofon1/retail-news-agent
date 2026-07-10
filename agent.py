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

HISTORY_FILE = "sent_news.json"

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

# ===== НОВАЯ ФУНКЦИЯ: забирает полный текст со страницы новости =====
def fetch_full_article(url, source):
    """Заходит на страницу новости и забирает основной текст"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ищем контейнер с текстом в зависимости от источника
        if source == "retail.ru":
            content = soup.find('div', class_='content') or soup.find('article') or soup.find('div', class_='news-text')
            if content:
                paragraphs = content.find_all('p')
                full_text = ' '.join([p.text.strip() for p in paragraphs if p.text.strip()])
                if full_text:
                    return full_text
        elif source == "shoppers.media":
            content = soup.find('div', class_='text') or soup.find('article') or soup.find('div', class_='article-body')
            if content:
                paragraphs = content.find_all('p')
                full_text = ' '.join([p.text.strip() for p in paragraphs if p.text.strip()])
                if full_text:
                    return full_text
        
        return None
    except Exception as e:
        print(f"⚠️ Ошибка загрузки статьи: {e}")
        return None

# ===== ОБНОВЛЁННАЯ ФУНКЦИЯ ПАРСИНГА (забирает полный текст) =====
def get_news():
    """Парсит новости с retail.ru и shoppers.media, забирая полный текст"""
    all_news = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # --- 1. Парсинг retail.ru ---
    try:
        url = "https://www.retail.ru/news/"
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')

        for article in soup.select('article')[:5]:
            title_elem = article.find('h2') or article.find('a')
            if not title_elem:
                continue
            
            title = title_elem.text.strip()
            link = "https://www.retail.ru" + title_elem.get('href', '')
            
            # Забираем полный текст новости
            full_text = fetch_full_article(link, "retail.ru")
            summary = full_text if full_text else title
            
            all_news.append({
                "title": title,
                "link": link,
                "summary": summary,
                "source": "retail.ru"
            })
    except Exception as e:
        print(f"⚠️ Ошибка retail.ru: {e}")

    # --- 2. Парсинг shoppers.media ---
    try:
        url = "https://shoppers.media/news"
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')

        for item in soup.select('div.item')[:5]:
            title_elem = item.find('a')
            if not title_elem:
                continue
            
            title = title_elem.text.strip()
            if not title or len(title) < 10:
                continue
            
            link = title_elem.get('href', '')
            if link and not link.startswith('http'):
                link = 'https://shoppers.media' + link
            
            # Забираем полный текст новости
            full_text = fetch_full_article(link, "shoppers.media")
            summary = full_text if full_text else title
            
            all_news.append({
                "title": title,
                "link": link,
                "summary": summary,
                "source": "shoppers.media"
            })
    except Exception as e:
        print(f"⚠️ Ошибка shoppers.media: {e}")

    return all_news[:10]

# ===== ОБНОВЛЁННАЯ ФУНКЦИЯ ГЕНЕРАЦИИ ПОСТА =====
def make_post(news_item):
    """Генерирует пост, точно копируя стиль из примеров и факты из новости"""
    
    # ===== ВАШИ ПРИМЕРЫ (вставьте свои посты) =====
    user_examples = """
    **Пример 1:**
    📌 Обязательная маркировка зубных щёток и салфеток стартует с 1 сентября 2026 года
    Регистрация в системе "Честный знак" для производителей, импортёров и продавцов станет обязательной с 1 сентября, маркировка — с 1 октября.
    Сведения об оптовых и розничных продажах нужно будет передавать с 1 октября 2027 года. Для бритв и лезвий она стартует с 1 февраля 2027 года.

    **Пример 2:**
    📌 Китайская платформа Poizon начала работу с российскими продавцами
    Первым партнёром стал бренд декоративной косметики Farres. Теперь локальные компании могут продавать свои товары внутри страны через платформу.
    В компании планируют продолжить подключение российских брендов из разных категорий.

    **Пример 3:**
    📌 Правительство утвердило новые правила розничной продажи товаров
    Документ заменяет действующие правила, срок которых истекает 1 января 2027 года. Нововведения касаются в первую очередь дистанционной торговли и агрегаторов маркетплейсов. В частности, продавцы, торгующие через маркетплейс, должны будут размещать информацию о себе на его сайте или в приложении. Маркетплейс обязан обеспечить возможность отправки претензии иностранному продавцу через свои цифровые каналы.
    Также закреплена возможность продавца проверять возраст покупателя с использованием многофункционального сервиса обмена информацией. Одновременно утверждены перечни товаров длительного пользования, не подлежащих бесплатной замене на период ремонта, и непродовольственных товаров, которые нельзя обменять.

    **Пример 4:**
    📌 Wildberries запустит сервис WB Track в Казахстане и Беларуси
    Об этом сообщила глава Wildberries & Russ Татьяна Ким. Сервис, который стартовал в пилотном режиме в марте 2025 года, а с января 2026 года стал доступен по всей сети российских пунктов выдачи, планируется масштабировать на зарубежные рынки в ближайшее время.
    Перед запуском компания изучит местное законодательство, чтобы обеспечить корректную работу сервиса. Расширение географии сервиса укрепит логистическую экосистему маркетплейса в странах присутствия.

    **Пример 5:**
    📌 Шестиступенчатый контроль качества X5 снизил обращения по мясной продукции до 0,1%
    Система качества охватывает всю цепочку "от поля до полки", включает до 200 аудиторских проверок поставщиков в год по 70 критериям.
    В 2025 году X5 утвердила стратегию пищевой безопасности до 2028 года.

    **Пример 6:**
    📌 Клиентов Ozon в малых городах в два раза больше, чем в Москве
    Компания доставила в города и сёла с населением до 50 тыс. человек треть от почти 2,5 млрд заказов в 2025 году. Почти половина из 84 тыс. ПВЗ работает именно в малых населённых пунктах.
    В Ozon отмечают, что потребность в товарах в регионах выше, чем в мегаполисах. Развитие складской инфраструктуры и сети пунктов выдачи позволяет местным жителям получать заказы рядом с домом.
    """
    # ===== КОНЕЦ ПРИМЕРОВ =====

    prompt = f"""
Ты — редактор Telegram-канала о ритейле. Твоя задача — написать пост по новости, **точно копируя структуру и стиль из примеров**.

**ВОТ МОЙ СТИЛЬ (ОБРАЗЕЦ):**
{user_examples}

**НОВОСТЬ ДЛЯ ПОСТА (используй ТОЛЬКО ЭТИ ФАКТЫ):**
Заголовок: {news_item['title']}
Полный текст новости:
{news_item['summary']}

**ТВОЙ ПОСТ ДОЛЖЕН:**
1. Начинаться с 📌 и заголовка.
2. Состоять из 2 абзацев, как в примерах.
3. **ТОЧНО КОПИРОВАТЬ** все цифры, даты, проценты.
4. **НЕ ДОБАВЛЯТЬ** ничего, чего нет в тексте новости.
5. Быть таким же по длине и тону, как примеры.

**ВЫДАЙ ТОЛЬКО ГОТОВЫЙ ПОСТ.**
"""
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=600
        )
        post = response.choices[0].message.content
        source = news_item.get('source', 'неизвестный источник')
        post += f"\n\nИсточник: {source}"
        return post
    except Exception as e:
        print(f"❌ Ошибка DeepSeek: {e}")
        return None

# ===== ФУНКЦИЯ ОТПРАВКИ В TELEGRAM =====
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

# ===== ОСНОВНАЯ ФУНКЦИЯ =====
def main():
    """Основная функция агента: парсит новости и отправляет только новые"""
    print(f"🚀 Запуск в {datetime.now()}")
    
    # 1. Загружаем историю отправленных новостей
    history = load_history()
    sent_titles = history.get("titles", [])
    
    # 2. Получаем свежие новости
    news = get_news()
    print(f"📰 Найдено новостей: {len(news)}")
    
    # 3. Обрабатываем каждую новость
    for item in news:
        # Проверяем, не отправляли ли уже эту новость
        if item['title'] in sent_titles:
            print(f"⏭️ Пропускаем (уже отправлено): {item['title'][:40]}...")
            continue
        
        print(f"📝 Обработка: {item['title'][:50]}...")
        post_text = make_post(item)
        if post_text and "ПРОПУСТИТЬ" not in post_text:
            send_to_telegram(post_text)
            # Добавляем заголовок в историю
            sent_titles.append(item['title'])
            save_history(sent_titles)
            time.sleep(2)  # пауза между постами
    
    print("✅ Завершено")

# ===== ТОЧКА ВХОДА =====
if __name__ == "__main__":
    main()
