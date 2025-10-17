import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')

# Проверка наличия токена
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден! Создайте .env файл с BOT_TOKEN")
