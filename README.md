# channel-helper-telegram-bot

Бот-помощник для управления предложениями новостей в Telegram канал.

## Возможности

- 🔐 Безопасная настройка администратора через одноразовый код
- 📢 Подключение канала через ссылку/username/ID
- 📝 Отправка предложений с текстом, фото, видео
- 🔒 Выбор анонимности публикации
- ✅ Модерация заявок администратором
- 🔔 Уведомления пользователей о статусе
- 📊 Статистика для пользователей и админа

## Установка

1. Клонируйте репозиторий:

git clone https://github.com/yourusername/telegram-channel-helper-bot.git
cd telegram-channel-helper-bot

2. Создайте виртуальное окружение:

python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

3. Установите зависимости:

pip install -r requirements.txt

4. Создайте файл `.env` и добавьте токен бота:

cp .env.example .env

5. Отредактируйте `.env` и добавьте ваш токен:

BOT_TOKEN=your_bot_token_here

## Запуск

python bot/main.py

При первом запуске в консоли появится код администратора.

## Использование

1. Запустите бота командой `/start`
2. Введите код администратора из консоли
3. Подключите канал командой `/setup_channel`
4. Бот готов к работе!

## Требования

- Python 3.11+
- aiogram 3.15+
- aiosqlite 0.20+
