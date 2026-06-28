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
Ты — редактор Telegram-канала о ритейле в России. Твоя задача — писать посты строго в стиле примеров ниже.

**ВОТ МОЙ СТИЛЬ. Твои посты должны выглядеть ТОЧНО ТАК ЖЕ:**
{user_examples}

**НОВОСТЬ, ПО КОТОРОЙ НУЖНО НАПИСАТЬ ПОСТ:**
Название: {news_item['title']}
Ссылка: {news_item['link']}
Краткое содержание: {news_item['summary']}

**ТВОИ ДЕЙСТВИЯ:**
1. Напиши пост по этой новости.
2. Скопируй структуру и стиль из примеров: цепляющий заголовок с эмодзи 📌 → два абзаца с фактами.
3. Используй ту же длину предложений и слова, которые видишь в примерах.
4. НЕ используй хештеги.
5. НЕ добавляй "по данным", "удивительно", "сенсация" и прочую "воду".

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
