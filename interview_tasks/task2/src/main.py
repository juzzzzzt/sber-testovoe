import sys
from rag_retriever import get_rag_context
from llm_client import generate_presentation_content
from pptx_builder import create_pptx


def main():
    """Главная функция: оркестрация пайплайна"""
    # Получаем имя клиента из аргументов командной строки
    client_name = sys.argv[1] if len(sys.argv) > 1 else "РЖД"

    print(f"🎯 Генерация презентации для клиента: {client_name}")
    print("=" * 60)

    # Шаг 1: Сбор контекста через RAG
    rag_context = get_rag_context(client_name)

    # Шаг 2: Генерация контента через GigaChat
    print(" Генерация контента с учетом внутренних заметок...")
    presentation_data = generate_presentation_content(rag_context, client_name)

    # Шаг 3: Создание презентации
    print("🎨 Отрисовка .pptx файла...")
    filepath = create_pptx(presentation_data, client_name)

    print("=" * 60)
    print(f"✅ Готово! Презентация сохранена: {filepath}")


if __name__ == "__main__":
    main()