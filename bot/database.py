import aiosqlite
import random
import string
from typing import Optional

DB_NAME = 'bot_database.db'

# Глобальное соединение с базой данных
_conn = None


async def connect(db_name: str = DB_NAME):
    """Подключение к базе данных"""
    global _conn
    _conn = await aiosqlite.connect(db_name)
    _conn.row_factory = aiosqlite.Row
    await create_tables()


async def close():
    """Закрытие соединения"""
    global _conn
    if _conn:
        await _conn.close()


async def create_tables():
    """Создание таблиц"""
    global _conn
    async with _conn.cursor() as cursor:
        # Таблица настроек
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # Таблица пользователей
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                is_banned INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица предложений
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message_id INTEGER,
                content_type TEXT,
                content TEXT,
                allow_forward INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                admin_decision TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        await _conn.commit()


async def generate_admin_code() -> str:
    """Генерация кода администратора"""
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    await set_setting('admin_code', code)
    return code


async def set_setting(key: str, value: str):
    """Установка настройки"""
    global _conn
    async with _conn.cursor() as cursor:
        await cursor.execute(
            'INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
            (key, value)
        )
        await _conn.commit()


async def get_setting(key: str) -> Optional[str]:
    """Получение настройки"""
    global _conn
    async with _conn.cursor() as cursor:
        await cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        result = await cursor.fetchone()
        return result['value'] if result else None


async def get_admin_id() -> Optional[int]:
    """Получение ID администратора"""
    admin_id = await get_setting('admin_id')
    return int(admin_id) if admin_id else None


async def set_admin(user_id: int):
    """Установка администратора"""
    await set_setting('admin_id', str(user_id))
    await set_setting('admin_code', '')  # Удаляем код


async def get_channel_id() -> Optional[int]:
    """Получение ID канала"""
    channel_id = await get_setting('channel_id')
    return int(channel_id) if channel_id else None


async def set_channel_id(channel_id: int):
    """Установка ID канала"""
    await set_setting('channel_id', str(channel_id))


async def add_user(user_id: int, username: str = None, first_name: str = None):
    """Добавление пользователя"""
    global _conn
    async with _conn.cursor() as cursor:
        await cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
        ''', (user_id, username, first_name))
        await _conn.commit()


async def is_user_banned(user_id: int) -> bool:
    """Проверка, забанен ли пользователь"""
    global _conn
    async with _conn.cursor() as cursor:
        await cursor.execute(
            'SELECT is_banned FROM users WHERE user_id = ?',
            (user_id,)
        )
        result = await cursor.fetchone()
        return bool(result['is_banned']) if result else False


async def add_submission(
    user_id: int,
    message_id: int,
    content_type: str,
    content: str,
    allow_forward: bool
) -> int:
    """Добавление предложения"""
    global _conn
    async with _conn.cursor() as cursor:
        await cursor.execute('''
            INSERT INTO submissions (user_id, message_id, content_type, content, allow_forward)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, message_id, content_type, content, allow_forward))
        await _conn.commit()
        return cursor.lastrowid


async def get_submission(submission_id: int):
    """Получение предложения по ID"""
    global _conn
    async with _conn.cursor() as cursor:
        await cursor.execute(
            'SELECT * FROM submissions WHERE id = ?',
            (submission_id,)
        )
        return await cursor.fetchone()


async def update_submission_status(
    submission_id: int,
    status: str,
    admin_decision: str = None
):
    """Обновление статуса предложения"""
    global _conn
    async with _conn.cursor() as cursor:
        await cursor.execute('''
            UPDATE submissions
            SET status = ?, admin_decision = ?
            WHERE id = ?
        ''', (status, admin_decision, submission_id))
        await _conn.commit()


async def get_pending_submissions_count() -> int:
    """Получение количества ожидающих предложений"""
    global _conn
    async with _conn.cursor() as cursor:
        await cursor.execute(
            'SELECT COUNT(*) as count FROM submissions WHERE status = "pending"'
        )
        result = await cursor.fetchone()
        return result['count']


async def get_user_stats(user_id: int) -> dict:
    """Получение статистики пользователя"""
    global _conn
    async with _conn.cursor() as cursor:
        await cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
            FROM submissions
            WHERE user_id = ?
        ''', (user_id,))
        result = await cursor.fetchone()
        return {
            'total': result['total'] or 0,
            'approved': result['approved'] or 0,
            'rejected': result['rejected'] or 0,
            'pending': result['pending'] or 0
        }


async def get_conn():
    """Получение соединения с базой данных"""
    global _conn
    return _conn
