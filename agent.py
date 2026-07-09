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

def get_news():
    """Парсит новости с retail.ru и shoppers.media с полным текстом"""
    all_news = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # --- 1. Парсинг retail.ru (с описанием) ---
    try:
        url = "https://www.retail.ru/news/"
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')

        for article in soup.select('article')[:5]:
            title_elem = article.find('h2') or article.find('a')
            if not title_elem:
                continue
            
            title = title_elem.text.strip()
            # Ищем описание: первый абзац или блок с классом announce
            desc_elem = article.find('p') or article.find('div', class_='announce')
            if desc_elem:
                summary = desc_elem.text.strip()
            else:
                # Если описания нет, берём заголовок
                summary = title
            
            all_news.append({
                "title": title,
                "link": "https://www.retail.ru" + title_elem.get('href', ''),
                "summary": summary,
                "source": "retail.ru"
            })
    except Exception as e:
        print(f"⚠️ Ошибка retail.ru: {e}")

    # --- 2. Парсинг shoppers.media (с описанием) ---
    try:
        url = "https://shoppers.media/news"
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')

        # На shoppers.media новости часто в блоках div.item
        for item in soup.select('div.item')[:5]:
            # Ищем заголовок (обычно в <a> внутри блока)
            title_elem = item.find('a')
            if not title_elem:
                continue
            
            title = title_elem.text.strip()
            if not title or len(title) < 10:
                continue
            
            # Ищем описание: следующий абзац или текст после заголовка
            # На shoppers.media описание может быть в соседнем <p> или в следующем элементе
            desc_elem = item.find('p') or item.find('div', class_='desc')
            if desc_elem:
                summary = desc_elem.text.strip()
            else:
                # Если отдельного описания нет, берём заголовок
                summary = title
            
            # Формируем полную ссылку
            link = title_elem.get('href', '')
            if link and not link.startswith('http'):
                link = 'https://shoppers.media' + link
            
            all_news.append({
                "title": title,
                "link": link,
                "summary": summary,
                "source": "shoppers.media"
            })
    except Exception as e:
        print(f"⚠️ Ошибка shoppers.media: {e}")

    # Возвращаем уникальные новости (максимум 10)
    return all_news[:10]

def make_post(news_item):
    """Генерирует пост в стиле пользователя, с точными фактами"""
    
    # ===== ВАШИ ПРИМЕРЫ ПОСТОВ (вставьте свои) =====
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
Ты — редактор Telegram-канала о ритейле. Твоя задача — написать пост, **точно копируя все факты** из новости и сохраняя стиль примеров.

**ВОТ МОЙ СТИЛЬ (ОБРАЗЕЦ):**
{user_examples}

**НОВОСТЬ ДЛЯ ПОСТА (используй ТОЛЬКО ЭТУ ИНФОРМАЦИЮ):**
Заголовок: {news_item['title']}
Текст новости: {news_item['summary']}

**ТВОЙ ПОСТ ДОЛЖЕН:**
1. Начинаться с заголовка (с эмодзи 📌).
2. Состоять из 2 абзацев (как в примерах).
3. **ТОЧНО КОПИРОВАТЬ** все цифры, даты, проценты из текста новости. НЕ меняй их.
4. **НЕ ДОБАВЛЯТЬ** никаких собственных комментариев, оценок или данных, которых нет в тексте.
5. Быть сухим и фактологическим, как в примерах.

**ВЫДАЙ ТОЛЬКО ГОТОВЫЙ ПОСТ, БЕЗ ЛИШНИХ СЛОВ.**
"""
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500
        )
        post = response.choices[0].message.content
        
        # Добавляем источник в конце
        source = news_item.get('source', 'неизвестный источник')
        post += f"\n\nИсточник: {source}"
        return post
        
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

# ===== ОСНОВНОЙ ЗАПУСК =====

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

if __name__ == "__main__":
    main()
