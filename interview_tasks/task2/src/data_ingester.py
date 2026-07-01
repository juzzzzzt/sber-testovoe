import json
import os
from opensearchpy import OpenSearch
from config import OS_HOST, OS_PORT, DATA_DIR
from sentence_transformers import SentenceTransformer

# Загружаем модель для эмбеддингов (один раз при старте)
embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')


def get_opensearch_client():
    """Создание клиента OpenSearch"""
    return OpenSearch(
        hosts=[{'host': OS_HOST, 'port': OS_PORT}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
    )


def create_indices(client):
    """Создание индексов в OpenSearch с поддержкой векторного поиска"""
    indices_config = {
        "clients": {
            "settings": {
                "index.knn": True
            },
            "mappings": {
                "properties": {
                    "name": {"type": "keyword"},
                    "profile": {"type": "text"},
                    "profile_vector": {
                        "type": "knn_vector",
                        "dimension": 384,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "lucene"  # <-- ЗДЕСЬ
                        }
                    }
                }
            }
        },
        "products": {
            "settings": {
                "index.knn": True
            },
            "mappings": {
                "properties": {
                    "name": {"type": "keyword"},
                    "description": {"type": "text"},
                    "description_vector": {
                        "type": "knn_vector",
                        "dimension": 384,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "lucene"  # <-- ЗДЕСЬ
                        }
                    }
                }
            }
        },
        "notes": {
            "settings": {
                "index.knn": True
            },
            "mappings": {
                "properties": {
                    "client_name": {"type": "keyword"},
                    "note_text": {"type": "text"},
                    "note_vector": {
                        "type": "knn_vector",
                        "dimension": 384,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "lucene"  # <-- ЗДЕСЬ
                        }
                    }
                }
            }
        },
        "news": {
            "settings": {
                "index.knn": True
            },
            "mappings": {
                "properties": {
                    "client_name": {"type": "keyword"},
                    "title": {"type": "text"},
                    "text": {"type": "text"},
                    "date": {"type": "date"},
                    "content_vector": {
                        "type": "knn_vector",
                        "dimension": 384,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "lucene"  # <-- ЗДЕСЬ
                        }
                    }
                }
            }
        }
    }

    for index_name, body in indices_config.items():
        if not client.indices.exists(index=index_name):
            client.indices.create(index=index_name, body=body)
            print(f"✅ Индекс {index_name} создан с поддержкой векторного поиска")
        else:
            print(f"ℹ️  Индекс {index_name} уже существует")


def load_clients(client):
    """Загрузка данных о клиентах с эмбеддингами"""
    with open(os.path.join(DATA_DIR, "clients.json"), "r", encoding="utf-8") as f:
        clients_data = json.load(f)

    for name, profile in clients_data.items():
        # Генерируем эмбеддинг профиля
        profile_vector = embedding_model.encode(profile).tolist()

        client.index(index="clients", body={
            "name": name.strip(),
            "profile": profile,
            "profile_vector": profile_vector
        })
    print(f"Загружено {len(clients_data)} клиентов с эмбеддингами")


def load_products(client):
    """Загрузка данных о продуктах с эмбеддингами"""
    with open(os.path.join(DATA_DIR, "products.json"), "r", encoding="utf-8") as f:
        products_data = json.load(f)

    for name, desc in products_data.items():
        # Генерируем эмбеддинг описания
        desc_vector = embedding_model.encode(desc).tolist()

        client.index(index="products", body={
            "name": name.strip(),
            "description": desc,
            "description_vector": desc_vector
        })
    print(f"Загружено {len(products_data)} продуктов с эмбеддингами")


def load_notes(client):
    """Загрузка внутренних заметок с эмбеддингами"""
    with open(os.path.join(DATA_DIR, "internal_notes.json"), "r", encoding="utf-8") as f:
        notes_data = json.load(f)

    # Загружаем клиентов для привязки заметок
    with open(os.path.join(DATA_DIR, "clients.json"), "r", encoding="utf-8") as f:
        clients_data = json.load(f)

    count = 0
    for note_text in notes_data:
        matched_client = None
        for c_name in clients_data.keys():
            if c_name.strip() in note_text:
                matched_client = c_name.strip()
                break

        if matched_client:
            # Генерируем эмбеддинг заметки
            note_vector = embedding_model.encode(note_text).tolist()

            client.index(index="notes", body={
                "client_name": matched_client,
                "note_text": note_text,
                "note_vector": note_vector
            })
            count += 1

    print(f"Загружено {count} заметок с эмбеддингами")


def load_news_from_csv(client):
    """Загрузка новостей из CSV файла"""
    import csv
    from datetime import datetime

    csv_path = os.path.join(DATA_DIR, "..", "data", "news.csv")

    if not os.path.exists(csv_path):
        print(f"⚠️  Файл news.csv не найден по пути: {csv_path}")
        load_mock_news(client)
        return

    print(f"📄 Загрузка новостей из: {csv_path}")

    count = 0
    skipped = 0

    with open(os.path.join(DATA_DIR, "clients.json"), "r", encoding="utf-8") as cf:
        clients_data = json.load(cf)

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            print(f"📋 Колонки в CSV: {reader.fieldnames}")

            for row in reader:
                title = row.get("title", row.get("заголовок", row.get("headline", "")))
                text = row.get("text", row.get("content", row.get("описание", "")))
                date_str = row.get("date", row.get("дата", row.get("published_at", "")))
                source = row.get("source", row.get("источник", ""))

                if not title.strip() and not text.strip():
                    skipped += 1
                    continue

                parsed_date = None
                if date_str and date_str.strip():
                    for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y"]:
                        try:
                            parsed_date = datetime.strptime(date_str.strip(), fmt)
                            break
                        except ValueError:
                            continue

                if parsed_date is None:
                    parsed_date = datetime.now()

                full_content = f"{title}. {text}"

                # Ищем упоминания компаний (нестрогое)
                matched_client = None
                for client_name in clients_data.keys():
                    clean_name = client_name.strip()
                    # Проверяем вхождение в разных формах
                    if (clean_name.lower() in full_content.lower() or
                            clean_name.split()[0].lower() in full_content.lower()):  # Первое слово
                        matched_client = clean_name
                        break

                if matched_client:
                    doc = {
                        "client_name": matched_client,
                        "title": title,
                        "text": text,
                        "date": parsed_date.strftime("%Y-%m-%d"),
                        "source": source
                    }

                    try:
                        from data_ingester import embedding_model
                        doc["content_vector"] = embedding_model.encode(full_content).tolist()
                    except:
                        pass

                    client.index(index="news", body=doc)
                    count += 1

        print(f"✅ Загружено {count} новостей из CSV (пропущено: {skipped})")

    except Exception as e:
        print(f"❌ Ошибка при чтении CSV: {e}")
        print("Используем моковые данные")
        load_mock_news(client)


def ingest_all_data():
    """Главная функция загрузки всех данных"""
    print("Начинаем загрузку данных в OpenSearch...")

    client = get_opensearch_client()

    # Создаем индексы
    create_indices(client)

    # Загружаем данные
    load_clients(client)
    load_products(client)
    load_notes(client)
    load_news_from_csv(client)

    print("Все данные успешно загружены в OpenSearch!")


if __name__ == "__main__":
    ingest_all_data()