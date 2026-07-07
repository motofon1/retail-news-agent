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

   # --- 2. Парсинг shoppers.media (исправленный, без дублей) ---
    try:
        url = "https://shoppers.media/news"
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Используем множество для хранения уникальных ссылок
        seen_links = set()
        news_from_shoppers = []

        # Ищем все ссылки, которые ведут на новости
        for a in soup.find_all('a', href=True):
            link = a['href']
            # Проверяем, что ссылка ведёт на страницу новости
            if '/news/' in link or link.startswith('news/') or 'shoppers.media/news/' in link:
                # Преобразуем относительную ссылку в абсолютную
                if not link.startswith('http'):
                    full_link = 'https://shoppers.media' + link
                else:
                    full_link = link

                # Проверяем, не обрабатывали ли мы уже эту ссылку
                if full_link in seen_links:
                    continue  # Пропускаем дублирующуюся ссылку
                seen_links.add(full_link)

                title = a.text.strip()
                # Проверяем, что заголовок не пустой и не слишком короткий
                if title and len(title) > 10 and not title.startswith('Читать'):
                    news_from_shoppers.append({
                        "title": title,
                        "link": full_link,
                        "summary": title,
                        "source": "shoppers.media"
                    })

        # Добавляем в общий список, но проверяем глобальные дубли по заголовку
        for news in news_from_shoppers:
            if not any(existing['title'] == news['title'] for existing in all_news):
                all_news.append(news)

    except Exception as e:
        print(f"⚠️ Ошибка парсинга shoppers.media: {e}")

    # --- 3. Возвращаем собранные новости (максимум 10) ---
    return all_news[:10]

def make_post(news_item):
    """Генерирует пост в точном стиле пользователя на основе примеров"""
    
    # ===== ВАШИ ПРИМЕРЫ ПОСТОВ (ВСТАВЬТЕ СВОИ) =====
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
Ты — редактор Telegram-канала о ритейле. Твоя задача — написать пост по новости, **сохранив все цифры, даты и проценты точно такими, как в оригинале**.

**ВОТ МОЙ СТИЛЬ (примеры):**
{user_examples}

**НОВОСТЬ, ПО КОТОРОЙ НУЖНО НАПИСАТЬ ПОСТ:**
Название: {news_item['title']}
Ссылка: {news_item['link']}
Текст новости: {news_item['summary']}

**ТВОИ ДЕЙСТВИЯ:**
1. Внимательно прочитай текст новости.
2. Напиши пост в том же стиле, что и примеры.
3. **КРИТИЧЕСКИ ВАЖНО:** Все числа, проценты, даты (например, "46 000", "2025 г.", "на 93%") должны быть **точно скопированы** из новости. НЕ меняй их, НЕ округляй, НЕ пересчитывай.
4. Если в новости есть сравнения (например, "в 2024 г. — 22 000"), обязательно упомяни их.
5. НЕ используй хештеги.
6. НЕ добавляй свои комментарии или обобщения, которых нет в тексте.

**ВЫДАЙ ТОЛЬКО ГОТОВЫЙ ПОСТ, БЕЗ ЛИШНИХ СЛОВ.**
"""
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,  # Низкая температура для точного следования стилю
            max_tokens=400
        )
        post = response.choices[0].message.content
        
        # Добавляем источник в конец
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
