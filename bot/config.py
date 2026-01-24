import os
from pathlib import Path
from dotenv import load_dotenv

# Загрузка .env из папки bot (рядом с config.py)
load_dotenv(Path(__file__).resolve().parent / ".env")

BOT_TOKEN = os.getenv('BOT_TOKEN')

# Проверка наличия токена
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден! Создайте .env файл с BOT_TOKEN")
