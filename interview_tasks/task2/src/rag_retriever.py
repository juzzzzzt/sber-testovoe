from opensearchpy import OpenSearch
from sentence_transformers import SentenceTransformer
from config import OS_HOST, OS_PORT

# Загружаем модель
embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')


def get_opensearch_client():
    return OpenSearch(
        hosts=[{'host': OS_HOST, 'port': OS_PORT}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
    )


def get_client_profile(client_name):
    """ТОЧНЫЙ поиск профиля клиента по имени (не семантический!)"""
    client = get_opensearch_client()

    # Ищем точное совпадение имени клиента
    res = client.search(
        index="clients",
        body={
            "size": 1,
            "query": {
                "term": {"name": client_name.strip()}
            }
        }
    )

    if res['hits']['hits']:
        return res['hits']['hits'][0]['_source']['profile']

    # Если точного совпадения нет — пробуем нечёткий поиск
    res = client.search(
        index="clients",
        body={
            "size": 1,
            "query": {
                "match": {"name": client_name.strip()}
            }
        }
    )

    if res['hits']['hits']:
        return res['hits']['hits'][0]['_source']['profile']

    return f"Информация о клиенте '{client_name}' не найдена"


def get_internal_note(client_name):
    """ТОЧНЫЙ поиск заметки по client_name + семантический поиск по тексту"""
    client = get_opensearch_client()

    # Сначала ищем по точному client_name
    res = client.search(
        index="notes",
        body={
            "size": 1,
            "query": {
                "term": {"client_name": client_name.strip()}
            }
        }
    )

    if res['hits']['hits']:
        return res['hits']['hits'][0]['_source']['note_text']

    # Если не нашли — пробуем нечёткий поиск
    res = client.search(
        index="notes",
        body={
            "size": 1,
            "query": {
                "match": {"client_name": client_name.strip()}
            }
        }
    )

    if res['hits']['hits']:
        return res['hits']['hits'][0]['_source']['note_text']

    return f"Внутренняя заметка для '{client_name}' не найдена"


def get_all_products():
    """Получение всех продуктов"""
    client = get_opensearch_client()
    res = client.search(
        index="products",
        body={"query": {"match_all": {}}, "size": 20}
    )

    products = {}
    for hit in res['hits']['hits']:
        products[hit['_source']['name']] = hit['_source']['description']

    return products


def get_client_news(client_name, size=3):
    """Гибридный поиск новостей: сначала точный, потом семантический"""
    client = get_opensearch_client()

    # 1. Сначала ищем через match по тексту новости (title + text)
    res = client.search(
        index="news",
        body={
            "size": size,
            "query": {
                "multi_match": {
                    "query": client_name.strip(),
                    "fields": ["title", "text", "client_name"],
                    "fuzziness": "AUTO"  # Нечёткий поиск
                }
            },
            "sort": [
                {"date": {"order": "desc"}}  # Сначала свежие
            ]
        }
    )

    if res['hits']['hits']:
        print(f"   📰 Найдено {len(res['hits']['hits'])} новостей через текстовый поиск")
        return [hit['_source'] for hit in res['hits']['hits'][:size]]

    # 2. Fallback: семантический поиск
    print(f"   ⚠️  Текстовый поиск не дал результатов, используем семантический...")
    query_text = f"новости о компании {client_name}"
    query_vector = embedding_model.encode(query_text).tolist()

    res = client.search(
        index="news",
        body={
            "size": size * 2,
            "query": {
                "knn": {
                    "content_vector": {
                        "vector": query_vector,
                        "k": size * 2
                    }
                }
            }
        }
    )

    # Фильтруем: берём только те, где реально упоминается клиент
    filtered_news = []
    for hit in res['hits']['hits']:
        source = hit['_source']
        full_text = f"{source.get('title', '')} {source.get('text', '')}".lower()
        if client_name.strip().lower() in full_text:
            filtered_news.append(source)
            if len(filtered_news) >= size:
                break

    # Если семантический тоже не дал — берём топ из knn
    if not filtered_news:
        filtered_news = [hit['_source'] for hit in res['hits']['hits'][:size]]

    return filtered_news


def get_rag_context(client_name):
    """Главная функция: сбор контекста"""
    print(f"🔍 Сбор контекста для клиента: {client_name}...")

    profile = get_client_profile(client_name)
    note = get_internal_note(client_name)
    products = get_all_products()
    news = get_client_news(client_name)

    print(f"   📄 Профиль: {profile[:80]}...")
    print(f"    Заметка: {note[:80]}...")
    print(f"   📰 Новостей найдено: {len(news)}")

    return {
        "profile": profile,
        "note": note,
        "products": products,
        "news": news
    }