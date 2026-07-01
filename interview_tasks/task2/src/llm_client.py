import json
import re
from gigachat import GigaChat
from config import GIGA_CREDENTIALS


def get_giga_client():
    return GigaChat(
        credentials=GIGA_CREDENTIALS,
        verify_ssl_certs=False
    )


def extract_json_from_response(text):
    """Извлечение JSON из ответа"""
    match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        return match.group(1).strip()

    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        return text[start:end + 1].strip()

    return text.strip()


def try_fix_json(json_text):
    """Исправление обрезанного JSON"""
    json_text = re.sub(r',(\s*[\]}])', r'\1', json_text)

    open_braces = json_text.count('{') - json_text.count('}')
    open_brackets = json_text.count('[') - json_text.count(']')
    open_quotes = json_text.count('"') % 2

    if open_quotes:
        json_text += '"'
    for _ in range(open_brackets):
        json_text += ']'
    for _ in range(open_braces):
        json_text += '}'

    return json_text


def safe_json_parse(text, max_retries=2):
    """Безопасный парсинг JSON"""
    for attempt in range(max_retries):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            text = try_fix_json(text)
    return None


def format_news_for_prompt(news_list, max_items=2):
    """Форматирование новостей для промпта"""
    if not news_list:
        return "Новостей нет"

    formatted = []
    for news in news_list[:max_items]:
        title = news.get('title', '')
        text = news.get('text', '')[:150]  # Обрезаем текст
        formatted.append(f"- {title}: {text}")

    return "\n".join(formatted)


def generate_presentation_content(context, client_name):
    """Генерация презентации в 3 этапа"""
    giga = get_giga_client()

    # === ЭТАП 1: Профиль ===
    prompt_profile = f"""Сделай JSON для слайда о профиле компании "{client_name}".

ПРОФИЛЬ КЛИЕНТА:
{context['profile'][:500]}

Верни JSON (только JSON, без текста):
{{"profile_slide":{{"title":"Профиль бизнеса и ключевые риски","bullets":["пункт1","пункт2","пункт3"]}}}}
"""

    print("Этап 1: Генерация профиля...")
    response = giga.chat(prompt_profile)
    text1 = response.choices[0].message.content.strip()
    json1 = extract_json_from_response(text1)
    data1 = safe_json_parse(json1)

    if not data1 or "profile_slide" not in data1:
        print("Не удалось распарсить этап 1, используем шаблон")
        data1 = {
            "profile_slide": {
                "title": "Профиль бизнеса",
                "bullets": [context['profile'][:300]]
            }
        }

    # === ЭТАП 2: Новости (ОТДЕЛЬНЫЙ ЗАПРОС!) ===
    news_formatted = format_news_for_prompt(context['news'], max_items=3)

    prompt_news = f"""Сделай JSON для слайда новостей о компании "{client_name}".

НОВОСТИ:
{news_formatted}

Верни JSON (только JSON, без текста):
{{"news_slide":{{"title":"Актуальная повестка","news_items":[{{"title":"заголовок","summary":"краткое описание (1-2 предложения)"}}]}}}}
"""

    print("Этап 2: Генерация новостей...")
    response = giga.chat(prompt_news)
    text2 = response.choices[0].message.content.strip()
    json2 = extract_json_from_response(text2)
    data2 = safe_json_parse(json2)

    if not data2 or "news_slide" not in data2:
        print("Не удалось распарсить этап 2, используем шаблон")
        data2 = {
            "news_slide": {
                "title": "Актуальная повестка",
                "news_items": [
                    {"title": n.get('title', ''), "summary": n.get('text', '')[:100]}
                    for n in context['news'][:2]
                ]
            }
        }

    # === ЭТАП 3: Подбор продуктов ===
    note_text = context['note']

    # Извлекаем названия продуктов из заметки
    product_names = ["IRS", "XCCY", "FX Forward", "Option Collar", "DCD",
                     "Commodity Hedge", "Repo", "Structured Note", "Deposit", "Prepaid Forward"]

    mentioned_products = []
    for pname in product_names:
        if pname.lower() in note_text.lower():
            idx = note_text.lower().find(pname.lower())
            context_window = note_text[max(0, idx - 50):idx + len(pname) + 50].lower()
            if "не " not in context_window and "не является" not in context_window and "вторичн" not in context_window:
                mentioned_products.append(pname)

    relevant_products = {k: v for k, v in context['products'].items() if k in mentioned_products}

    if not relevant_products:
        relevant_products = context['products']

    products_text = "\n".join([f"- {k}: {v[:100]}" for k, v in relevant_products.items()])

    prompt_products = f"""Ты — корпоративный банкир. Выбери 2-3 продукта для клиента "{client_name}".

ЗАМЕТКА ЭКСПЕРТА (СЛЕДУЙ СТРОГО): {note_text[:400]}

ДОСТУПНЫЕ ПРОДУКТЫ:
{products_text}

ПРАВИЛА:
1. Выбери ТОЛЬКО продукты, которые РЕКОМЕНДОВАНЫ в заметке.
2. НЕ включай продукты, про которые сказано "не приоритетен", "вторична", "осторожно".
3. Для каждого продукта напиши обоснование (1 предложение).

Верни JSON (только JSON):
{{"products_slide":{{"title":"Рекомендуемые решения","products":[{{"name":"...","reason":"..."}}]}}}}
"""

    print(" Этап 3: Подбор продуктов...")
    response = giga.chat(prompt_products)
    text3 = response.choices[0].message.content.strip()
    json3 = extract_json_from_response(text3)
    data3 = safe_json_parse(json3)

    if not data3 or "products_slide" not in data3:
        print("Не удалось распарсить этап 3, используем шаблон")
        data3 = {
            "products_slide": {
                "title": "Рекомендуемые решения",
                "products": [{"name": "Deposit", "reason": "Размещение ликвидности"}]
            }
        }

    # === Собираем финальный результат ===
    result = {
        "title_slide": {
            "title": f"Стратегическое партнёрство с {client_name}",
            "subtitle": "Индивидуальные финансовые решения"
        },
        "profile_slide": data1.get("profile_slide", {"title": "Профиль", "bullets": ["Информация о клиенте"]}),
        "news_slide": data2.get("news_slide", {"title": "Новости", "news_items": []}),
        "products_slide": data3.get("products_slide", {"title": "Продукты", "products": []})
    }

    print("Презентация собрана из 3 этапов")
    return result