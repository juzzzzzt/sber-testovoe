import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройки GigaChat
GIGA_CREDENTIALS = os.getenv("GIGA_CREDENTIALS")

# Настройки OpenSearch
OS_HOST = os.getenv("OS_HOST", "localhost")
OS_PORT = int(os.getenv("OS_PORT", 9200))

# Пути к данным
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

# Убедимся, что папка output существует
os.makedirs(OUTPUT_DIR, exist_ok=True)