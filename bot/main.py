import asyncio
import logging
import sys
import json
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, Chat
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest

from config import BOT_TOKEN
from database import db
from states import AdminSetup, ChannelSetup, SubmissionStates
from keyboards import (
    get_user_quick_commands_kb,
    get_admin_quick_commands_kb,
    get_forward_choice_kb,
    get_admin_decision_kb,
    get_cancel_kb,
    get_pending_submissions_kb,
    get_empty_inline_kb,
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Полностью отключаем логирование ошибок polling для aiogram
logging.getLogger('aiogram.dispatcher').setLevel(logging.CRITICAL)
logging.getLogger('aiogram.event').setLevel(logging.CRITICAL)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()


# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============

async def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    admin_id = await db.get_admin_id()
    return admin_id == user_id


async def get_user_info(user_id: int) -> dict:
    """Получение информации о пользователе"""
    try:
        chat = await bot.get_chat(user_id)
        return {
            'id': chat.id,
            'username': chat.username,
            'first_name': chat.first_name,
            'full_name': chat.full_name
        }
    except Exception as e:
        logger.error(f"Ошибка получения информации о пользователе {user_id}: {e}")
        return None


# ============= ОБРАБОТЧИКИ КОМАНД =============

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команды /start"""
    await state.clear()
    
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Добавляем пользователя в базу
    await db.add_user(user_id, username, first_name)
    
    # Проверяем, есть ли администратор
    admin_id = await db.get_admin_id()
    
    if not admin_id:
        # Генерируем код администратора
        admin_code = await db.get_setting('admin_code')
        if not admin_code:
            admin_code = await db.generate_admin_code()
            print(f"\n{'='*50}")
            print(f"🔐 КОД АДМИНИСТРАТОРА: {admin_code}")
            print(f"{'='*50}\n")
        
        await message.answer(
            "👋 Добро пожаловать!\n\n"
            "Администратор ещё не установлен.\n"
            "Введите код администратора из консоли:",
            reply_markup=get_cancel_kb()
        )
        await state.set_state(AdminSetup.waiting_for_code)
        return
    
    # Проверяем бан
    if await db.is_user_banned(user_id):
        await message.answer("❌ Вы заблокированы и не можете использовать бота.")
        return
    
    admin = await is_admin(user_id)
    channel_id = await db.get_channel_id()
    
    # Если канал не подключен - показываем предупреждение
    if not channel_id:
        if admin:
            await message.answer(
                "⚠️ <b>Канал не подключен!</b>\n\n"
                "Для начала работы бота необходимо подключить канал.\n"
                "Используйте команду /setup_channel",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "⚠️ <b>Бот ещё не настроен</b>\n\n"
                "Администратор должен подключить канал.\n"
                "Пожалуйста, подождите.",
                parse_mode="HTML"
            )
        return
    
    welcome_text = f"👋 Добро пожаловать, {first_name}!\n\n"
    
    if admin:
        pending_count = await db.get_pending_submissions_count()
        welcome_text += (
            "⚙️ <b>Панель администратора</b>\n\n"
            f"📬 Ожидающих заявок: {pending_count}\n"
            f"📢 Канал подключен\n\n"
            "Выберите действие:"
        )
        await message.answer(
            welcome_text,
            reply_markup=get_admin_quick_commands_kb(),
            parse_mode="HTML"
        )
    else:
        stats = await db.get_user_stats(user_id)
        welcome_text += (
            f"📊 <b>Ваша статистика:</b>\n"
            f"• Всего предложений: {stats['total']}\n"
            f"• Одобрено: {stats['approved']}\n"
            f"• Ожидает: {stats['pending']}\n\n"
            f"Выберите действие:"
        )
        await message.answer(
            welcome_text,
            reply_markup=get_user_quick_commands_kb(),
            parse_mode="HTML"
        )


# ============= ОБРАБОТКА БЫСТРЫХ КОМАНД =============

@router.message(F.text == "📋 Главное меню")
async def quick_main_menu(message: Message, state: FSMContext):
    """Быстрая команда: Главное меню"""
    await state.clear()
    
    admin = await is_admin(message.from_user.id)
    channel_id = await db.get_channel_id()
    
    # Если канал не подключен
    if not channel_id:
        if admin:
            await message.answer(
                "⚠️ <b>Канал не подключен!</b>\n\n"
                "Для начала работы бота необходимо подключить канал.\n"
                "Используйте команду /setup_channel",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "⚠️ <b>Бот ещё не настроен</b>\n\n"
                "Администратор должен подключить канал.\n"
                "Пожалуйста, подождите.",
                parse_mode="HTML"
            )
        return
    
    if admin:
        pending_count = await db.get_pending_submissions_count()
        text = (
            "⚙️ <b>Панель администратора</b>\n\n"
            f"📬 Ожидающих заявок: {pending_count}\n"
            f"📢 Канал подключен"
        )
        await message.answer(
            text,
            reply_markup=get_admin_quick_commands_kb(),
            parse_mode="HTML"
        )
    else:
        stats = await db.get_user_stats(message.from_user.id)
        text = (
            f"📊 <b>Ваша статистика:</b>\n\n"
            f"• Всего предложений: {stats['total']}\n"
            f"• Одобрено: {stats['approved']}\n"
            f"• Отклонено: {stats['rejected']}\n"
            f"• Ожидает: {stats['pending']}\n"
        )
        await message.answer(
            text,
            reply_markup=get_user_quick_commands_kb(),
            parse_mode="HTML"
        )


@router.message(F.text == "📝 Предложить новость")
async def quick_submit_news(message: Message, state: FSMContext):
    """Быстрая команда: Предложить новость"""
    # Проверяем, что канал подключен
    channel_id = await db.get_channel_id()
    if not channel_id:
        await message.answer(
            "❌ Канал не подключен. Обратитесь к администратору.",
            reply_markup=get_user_quick_commands_kb()
        )
        return
    
    # Проверяем бан
    if await db.is_user_banned(message.from_user.id):
        await message.answer(
            "❌ Вы заблокированы и не можете отправлять предложения.",
            reply_markup=get_user_quick_commands_kb()
        )
        return
    
    await message.answer(
        "📝 <b>Отправка предложения</b>\n\n"
        "Отправьте ваше сообщение:\n"
        "• Текст\n"
        "• Фото с подписью\n"
        "• Видео с подписью\n"
        "• Документ\n\n"
        "После отправки вы сможете выбрать, разрешить ли публикацию от вашего имени.",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML"
    )
    await state.set_state(SubmissionStates.waiting_for_content)


@router.message(F.text == "📊 Моя статистика")
async def quick_my_stats(message: Message):
    """Быстрая команда: Моя статистика"""
    stats = await db.get_user_stats(message.from_user.id)
    
    text = (
        f"📊 <b>Ваша статистика</b>\n\n"
        f"• Всего предложений: {stats['total']}\n"
        f"• ✅ Одобрено: {stats['approved']}\n"
        f"• ❌ Отклонено: {stats['rejected']}\n"
        f"• ⏳ Ожидает модерации: {stats['pending']}\n"
    )
    
    if stats['total'] > 0:
        approval_rate = (stats['approved'] / stats['total']) * 100
        text += f"\n📈 Процент одобрения: {approval_rate:.1f}%"
    
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_user_quick_commands_kb()
    )


async def _handle_my_pending(message: Message):
    """Показать пользователю его предложения на рассмотрении."""
    if await db.is_user_banned(message.from_user.id):
        await message.answer("❌ Вы заблокированы.", reply_markup=get_user_quick_commands_kb())
        return
    channel_id = await db.get_channel_id()
    if not channel_id:
        await message.answer(
            "❌ Канал не подключен.",
            reply_markup=get_user_quick_commands_kb()
        )
        return
    submissions = await db.get_user_pending_submissions(message.from_user.id)
    if not submissions:
        await message.answer(
            "📭 Нет предложений на рассмотрении.",
            reply_markup=get_user_quick_commands_kb()
        )
        return
    text = f"⏳ Ваших предложений на рассмотрении: {len(submissions)}\n\nВыберите для просмотра:"
    await message.answer(
        text,
        reply_markup=get_pending_submissions_kb(submissions)
    )


@router.message(F.text == "⏳ На рассмотрении")
async def quick_my_pending(message: Message, state: FSMContext):
    """Быстрая команда: Мои предложения на рассмотрении"""
    await state.clear()
    await _handle_my_pending(message)


@router.message(F.text == "📬 Ожидающие")
async def quick_pending(message: Message):
    """Быстрая команда: Ожидающие"""
    if not await is_admin(message.from_user.id):
        return

    # Получаем все ожидающие предложения
    submissions = await db.get_pending_submissions()

    if not submissions:
        await message.answer(
            "📭 Нет ожидающих предложений",
            reply_markup=get_admin_quick_commands_kb()
        )
    else:
        text = f"📬 Ожидающих предложений: {len(submissions)}\n\n" \
               "Выберите предложение для просмотра:"

        await message.answer(
            text,
            reply_markup=get_pending_submissions_kb(submissions)
        )


@router.message(F.text == "📊 Статистика")
async def quick_bot_stats(message: Message):
    """Быстрая команда: Статистика бота"""
    if not await is_admin(message.from_user.id):
        return
    
    # Получаем статистику
    async with db.conn.cursor() as cursor:
        # Всего пользователей
        await cursor.execute('SELECT COUNT(*) as count FROM users')
        users_count = (await cursor.fetchone())['count']
        
        # Всего предложений
        await cursor.execute('SELECT COUNT(*) as count FROM submissions')
        total_submissions = (await cursor.fetchone())['count']
        
        # Одобренных
        await cursor.execute('SELECT COUNT(*) as count FROM submissions WHERE status = "approved"')
        approved = (await cursor.fetchone())['count']
        
        # Отклоненных
        await cursor.execute('SELECT COUNT(*) as count FROM submissions WHERE status = "rejected"')
        rejected = (await cursor.fetchone())['count']
        
        # Ожидающих
        await cursor.execute('SELECT COUNT(*) as count FROM submissions WHERE status = "pending"')
        pending = (await cursor.fetchone())['count']
    
    text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: {users_count}\n"
        f"📝 Всего предложений: {total_submissions}\n\n"
        f"✅ Одобрено: {approved}\n"
        f"❌ Отклонено: {rejected}\n"
        f"⏳ Ожидает: {pending}\n"
    )
    
    if total_submissions > 0:
        approval_rate = (approved / total_submissions) * 100
        text += f"\n📈 Процент одобрения: {approval_rate:.1f}%"
    
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_admin_quick_commands_kb()
    )


@router.message(F.text == "🔗 Сменить канал")
async def quick_change_channel(message: Message, state: FSMContext):
    """Быстрая команда: Сменить канал"""
    if not await is_admin(message.from_user.id):
        return
    
    await message.answer(
        "🔗 Отправьте:\n"
        "1. Инвайт-ссылку на канал или группу\n"
        "2. Username (@channel или @group)\n"
        "3. ID канала/группы\n\n"
        "⚠️ Бот должен быть админом!",
        reply_markup=get_cancel_kb()
    )
    await state.set_state(ChannelSetup.waiting_for_invite)


# ============= ОБРАБОТКА НАСТРОЙКИ АДМИНИСТРАТОРА =============

@router.message(AdminSetup.waiting_for_code)
async def process_admin_code(message: Message, state: FSMContext):
    """Обработка ввода кода администратора"""
    code = message.text.strip().upper()
    correct_code = await db.get_setting('admin_code')
    
    if code == correct_code:
        await db.set_admin(message.from_user.id)
        await message.answer(
            "✅ Вы успешно стали администратором!\n\n"
            "Теперь подключите канал, отправив инвайт-ссылку или добавив бота в канал администратором.\n\n"
            "Используйте /setup_channel для настройки канала.",
        )
        await state.clear()
        logger.info(f"Новый администратор: {message.from_user.id} (@{message.from_user.username})")
    else:
        await message.answer(
            "❌ Неверный код. Попробуйте ещё раз:",
            reply_markup=get_cancel_kb()
        )


# ============= ОБРАБОТКА НАСТРОЙКИ КАНАЛА =============

@router.message(Command("setup_channel"))
async def cmd_setup_channel(message: Message, state: FSMContext):
    """Команда настройки канала"""
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Только администратор может настраивать канал.")
        return
    
    await message.answer(
            "🔗 Отправьте:\n"
            "1. Инвайт-ссылку на канал или группу (https://t.me/...)\n"
            "2. Username (@channel или @group)\n"
            "3. ID (например: -1001234567890)\n\n"
            "⚠️ Бот должен быть админом с правом публикации!",
        reply_markup=get_cancel_kb()
    )
    await state.set_state(ChannelSetup.waiting_for_invite)


@router.message(ChannelSetup.waiting_for_invite)
async def process_channel_invite(message: Message, state: FSMContext):
    """Обработка инвайт-ссылки канала"""
    text = message.text.strip()
    
    # Пробуем разные варианты
    channel_id = None
    
    try:
        # Вариант 1: ID канала
        if text.startswith('-'):
            channel_id = int(text)
        # Вариант 2: Username
        elif text.startswith('@'):
            channel_id = text
        # Вариант 3: Ссылка
        elif 't.me/' in text:
            username = text.split('t.me/')[-1].split('?')[0]
            channel_id = f"@{username}" if not username.startswith('@') else username
        else:
            await message.answer(
                "❌ Неверный формат. Отправьте ссылку, username или ID канала/группы.",
                reply_markup=get_cancel_kb()
            )
            return
        
        # Проверяем доступ к каналу/группе
        try:
            chat = await bot.get_chat(channel_id)
            
            # Поддерживаем каналы и супергруппы
            if chat.type not in ('channel', 'supergroup'):
                await message.answer(
                    "❌ Поддерживаются только каналы и супергруппы.",
                    reply_markup=get_cancel_kb()
                )
                return
            
            # Проверяем права бота
            bot_member = await bot.get_chat_member(chat.id, bot.id)
            if bot_member.status not in ['administrator', 'creator']:
                await message.answer(
                    "❌ Бот не администратор.\n"
                    "Добавьте бота в канал/группу как администратора с правом публикации!",
                    reply_markup=get_cancel_kb()
                )
                return
            
            # Сохраняем канал/группу
            await db.set_channel_id(chat.id)
            
            dest_type = "группа" if chat.type == 'supergroup' else "канал"
            connected = "подключена" if chat.type == 'supergroup' else "подключен"
            
            await message.answer(
                f"✅ {dest_type.capitalize()} успешно {connected}!\n\n"
                f"📢 Название: {chat.title}\n"
                f"🆔 ID: {chat.id}\n\n"
                f"Теперь пользователи могут отправлять предложения!",
                reply_markup=get_admin_quick_commands_kb(),
                parse_mode="HTML"
            )
            await state.clear()
            logger.info(f"Канал подключен: {chat.title} (ID: {chat.id})")
            
        except TelegramBadRequest as e:
            await message.answer(
                f"❌ Ошибка доступа к каналу/группе.\n"
                f"Убедитесь, что:\n"
                f"1. Бот добавлен в чат\n"
                f"2. Бот — администратор\n"
                f"3. Есть право публикации сообщений\n\n"
                f"Ошибка: {e}",
                reply_markup=get_cancel_kb()
            )
    
    except ValueError:
        await message.answer(
            "❌ Неверный формат ID канала.",
            reply_markup=get_cancel_kb()
        )
    except Exception as e:
        logger.error(f"Ошибка подключения канала: {e}")
        await message.answer(
            f"❌ Произошла ошибка: {e}",
            reply_markup=get_cancel_kb()
        )


# ============= ОБРАБОТКА ПРЕДЛОЖЕНИЙ ОТ ПОЛЬЗОВАТЕЛЕЙ =============

@router.callback_query(F.data == "submit_news")
async def start_submission(callback: CallbackQuery, state: FSMContext):
    """Начало отправки предложения"""
    await callback.answer()
    
    # Проверяем бан
    if await db.is_user_banned(callback.from_user.id):
        await callback.message.edit_text("❌ Вы заблокированы и не можете отправлять предложения.")
        return
    
    # Проверяем, подключен ли канал
    channel_id = await db.get_channel_id()
    if not channel_id:
        await callback.message.edit_text(
            "❌ Канал ещё не подключен. Обратитесь к администратору.",
            reply_markup=get_empty_inline_kb()
        )
        return
    
    await callback.message.edit_text(
        "📝 <b>Отправка предложения</b>\n\n"
        "Отправьте ваше сообщение:\n"
        "• Текст\n"
        "• Фото с подписью\n"
        "• Видео с подписью\n"
        "• Документ\n\n"
        "После отправки вы сможете выбрать, разрешить ли публикацию от вашего имени.",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML"
    )
    await state.set_state(SubmissionStates.waiting_for_content)


@router.message(SubmissionStates.waiting_for_content)
async def process_submission_content(message: Message, state: FSMContext):
    """Обработка контента предложения"""
    # Кнопки быстрых команд работают даже в процессе отправки — выходим из состояния
    if message.content_type == "text" and message.text and message.text.strip() == "⏳ На рассмотрении":
        await state.clear()
        await _handle_my_pending(message)
        return

    # Сохраняем данные сообщения
    content_data = ""
    if message.content_type == "text":
        content_data = message.text
    elif message.content_type in ["photo", "video", "document", "animation"]:
        content_data = message.caption or ""

    await state.update_data(
        message_id=message.message_id,
        content_type=message.content_type,
        content=content_data,
        chat_id=message.chat.id
    )
    
    await message.answer(
        "✅ Сообщение получено!\n\n"
        "Выберите вариант публикации:",
        reply_markup=get_forward_choice_kb()
    )
    await state.set_state(SubmissionStates.waiting_for_forward_choice)


@router.callback_query(SubmissionStates.waiting_for_forward_choice, F.data.startswith("allow_forward_"))
async def process_forward_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора пересылки"""
    await callback.answer()
    
    choice = callback.data.split("_")[-1]
    allow_forward = choice == "yes"
    
    # Получаем данные из состояния
    data = await state.get_data()
    message_id = data.get('message_id')
    content_type = data.get('content_type')
    content = data.get('content', '')

    # Сохраняем предложение в базу
    submission_id = await db.add_submission(
        user_id=callback.from_user.id,
        message_id=message_id,
        content_type=content_type,
        content=content,
        allow_forward=allow_forward
    )
    
    # Отправляем уведомление пользователю
    await callback.message.edit_text(
        "✅ Ваше предложение отправлено на модерацию!\n\n"
        "Вы получите уведомление, когда администратор примет решение.",
        reply_markup=get_empty_inline_kb()
    )
    
    # Отправляем администратору
    admin_id = await db.get_admin_id()
    if admin_id:
        user_info = await get_user_info(callback.from_user.id)
        user_name = f"{user_info['first_name']}"
        if user_info.get('username'):
            user_name += f" (@{user_info['username']})"
        
        forward_status = "✅ Разрешена публикация с автором" if allow_forward else "🔒 Только анонимно"
        
        # Формируем текст заголовка
        header_text = (
            f"┌─ 📬 <b>Новое предложение</b>\n"
            f"│\n"
            f"│ 👤 От: {user_name}\n"
            f"│ 🔐 {forward_status}\n"
            f"└─────────────────────\n\n"
        )
        
        # Отправляем одно сообщение с предложением внутри
        try:
            # Получаем оригинальное сообщение
            original_msg = await bot.forward_message(
                chat_id=admin_id,
                from_chat_id=callback.from_user.id,
                message_id=message_id
            )
            
            # Удаляем пересланное сообщение
            await bot.delete_message(admin_id, original_msg.message_id)
            
            # Копируем с новым caption
            if content_type in ['photo', 'video', 'document', 'animation']:
                # Для медиа добавляем caption
                original_caption = callback.message.caption or ""
                new_caption = header_text + original_caption
                
                await bot.copy_message(
                    chat_id=admin_id,
                    from_chat_id=callback.from_user.id,
                    message_id=message_id,
                    caption=new_caption,
                    parse_mode="HTML",
                    reply_markup=get_admin_decision_kb(submission_id, allow_forward)
                )
            else:
                # Для текста отправляем заголовок + текст из базы данных
                submission = await db.get_submission(submission_id)
                content_text = submission['content'] if submission and submission['content'] else "Текст не найден"
                await bot.send_message(
                    chat_id=admin_id,
                    text=header_text + "📄 <b>Текст предложения:</b>\n\n" + content_text,
                    parse_mode="HTML",
                    reply_markup=get_admin_decision_kb(submission_id, allow_forward)
                )
            
        except Exception as e:
            logger.error(f"Ошибка отправки администратору: {e}")
            # Запасной вариант - отправляем как раньше
            try:
                await bot.copy_message(
                    chat_id=admin_id,
                    from_chat_id=callback.from_user.id,
                    message_id=message_id,
                    caption=header_text if content_type != 'text' else None,
                    parse_mode="HTML",
                    reply_markup=get_admin_decision_kb(submission_id, allow_forward)
                )
                
                if content_type == 'text':
                    await bot.send_message(
                        chat_id=admin_id,
                        text=header_text,
                        parse_mode="HTML",
                        reply_markup=get_admin_decision_kb(submission_id, allow_forward)
                    )
            except Exception as e2:
                logger.error(f"Ошибка запасного варианта: {e2}")
    
    await state.clear()


# ============= ОБРАБОТКА РЕШЕНИЙ АДМИНИСТРАТОРА =============

@router.callback_query(F.data.startswith("approve_"))
async def approve_submission(callback: CallbackQuery):
    """Одобрение предложения"""
    await callback.answer()
    
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав!", show_alert=True)
        return
    
    # Парсим данные
    parts = callback.data.split("_")
    publish_type = parts[1]  # with или anonymous
    submission_id = int(parts[-1])
    
    # Получаем предложение
    submission = await db.get_submission(submission_id)
    if not submission:
        await callback.message.edit_text("❌ Предложение не найдено.")
        return
    
    if submission['status'] != 'pending':
        await callback.answer(f"❌ Предложение уже обработано!", show_alert=True)
        return
    
    # Получаем ID канала
    channel_id = await db.get_channel_id()
    if not channel_id:
        await callback.answer("❌ Канал не подключен!", show_alert=True)
        return
    
    # Публикуем в канал
    try:
        user_chat_id = submission['user_id']
        
        if publish_type == 'with' and submission['allow_forward']:
            # Публикация с автором (пересылка)
            await bot.forward_message(
                chat_id=channel_id,
                from_chat_id=user_chat_id,
                message_id=submission['message_id']
            )
            decision_text = "публикацией с указанием авторства"
        else:
            # Анонимная публикация (копирование)
            await bot.copy_message(
                chat_id=channel_id,
                from_chat_id=user_chat_id,
                message_id=submission['message_id']
            )
            decision_text = "анонимной публикацией"
        
        # Обновляем статус
        await db.update_submission_status(submission_id, 'approved', decision_text)
        
        # Уведомляем пользователя
        try:
            await bot.send_message(
                chat_id=submission['user_id'],
                text=f"✅ Ваше предложение одобрено и опубликовано с {decision_text}!"
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователя: {e}")
        
        # Обновляем сообщение администратора
        try:
            if callback.message.caption:
                await callback.message.edit_caption(
                    caption=f"{callback.message.caption}\n\n✅ <b>ОДОБРЕНО</b> ({decision_text})",
                    parse_mode="HTML"
                )
            else:
                await callback.message.edit_text(
                    text=f"{callback.message.text}\n\n✅ <b>ОДОБРЕНО</b> ({decision_text})",
                    parse_mode="HTML"
                )
        except:
            pass
        
        logger.info(f"Предложение #{submission_id} одобрено администратором")
        
    except Exception as e:
        logger.error(f"Ошибка публикации в канал: {e}")
        await callback.answer(f"❌ Ошибка публикации: {e}", show_alert=True)


@router.callback_query(F.data.startswith("reject_"))
async def reject_submission(callback: CallbackQuery):
    """Отклонение предложения"""
    await callback.answer()
    
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав!", show_alert=True)
        return
    
    submission_id = int(callback.data.split("_")[1])
    
    # Получаем предложение
    submission = await db.get_submission(submission_id)
    if not submission:
        await callback.message.edit_text("❌ Предложение не найдено.")
        return
    
    if submission['status'] != 'pending':
        await callback.answer(f"❌ Предложение уже обработано!", show_alert=True)
        return
    
    # Обновляем статус
    await db.update_submission_status(submission_id, 'rejected', 'Отклонено администратором')
    
    # Уведомляем пользователя
    try:
        await bot.send_message(
            chat_id=submission['user_id'],
            text="❌ Ваше предложение было отклонено."
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления пользователя: {e}")
    
    # Обновляем сообщение администратора
    try:
        if callback.message.caption:
            await callback.message.edit_caption(
                caption=f"{callback.message.caption}\n\n❌ <b>ОТКЛОНЕНО</b>",
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                text=f"{callback.message.text}\n\n❌ <b>ОТКЛОНЕНО</b>",
                parse_mode="HTML"
            )
    except:
        pass
    
    logger.info(f"Предложение #{submission_id} отклонено администратором")


# ============= НАВИГАЦИЯ ПО МЕНЮ =============

@router.callback_query(F.data == "my_stats")
async def show_my_stats(callback: CallbackQuery):
    """Показ статистики пользователя"""
    await callback.answer()
    
    stats = await db.get_user_stats(callback.from_user.id)
    
    text = (
        f"📊 <b>Ваша статистика</b>\n\n"
        f"• Всего предложений: {stats['total']}\n"
        f"• ✅ Одобрено: {stats['approved']}\n"
        f"• ❌ Отклонено: {stats['rejected']}\n"
        f"• ⏳ Ожидает модерации: {stats['pending']}\n"
    )
    
    if stats['total'] > 0:
        approval_rate = (stats['approved'] / stats['total']) * 100
        text += f"\n📈 Процент одобрения: {approval_rate:.1f}%"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_empty_inline_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "bot_stats")
async def show_bot_stats(callback: CallbackQuery):
    """Показ статистики бота"""
    await callback.answer()
    
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав!", show_alert=True)
        return
    
    # Получаем статистику
    async with db.conn.cursor() as cursor:
        # Всего пользователей
        await cursor.execute('SELECT COUNT(*) as count FROM users')
        users_count = (await cursor.fetchone())['count']
        
        # Всего предложений
        await cursor.execute('SELECT COUNT(*) as count FROM submissions')
        total_submissions = (await cursor.fetchone())['count']
        
        # Одобренных
        await cursor.execute('SELECT COUNT(*) as count FROM submissions WHERE status = "approved"')
        approved = (await cursor.fetchone())['count']
        
        # Отклоненных
        await cursor.execute('SELECT COUNT(*) as count FROM submissions WHERE status = "rejected"')
        rejected = (await cursor.fetchone())['count']
        
        # Ожидающих
        await cursor.execute('SELECT COUNT(*) as count FROM submissions WHERE status = "pending"')
        pending = (await cursor.fetchone())['count']
    
    text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: {users_count}\n"
        f"📝 Всего предложений: {total_submissions}\n\n"
        f"✅ Одобрено: {approved}\n"
        f"❌ Отклонено: {rejected}\n"
        f"⏳ Ожидает: {pending}\n"
    )
    
    if total_submissions > 0:
        approval_rate = (approved / total_submissions) * 100
        text += f"\n📈 Процент одобрения: {approval_rate:.1f}%"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_empty_inline_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "view_pending")
async def view_pending(callback: CallbackQuery):
    """Просмотр списка ожидающих предложений"""
    await callback.answer()

    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав!", show_alert=True)
        return

    # Получаем все ожидающие предложения
    submissions = await db.get_pending_submissions()

    if not submissions:
        await callback.message.edit_text(
            "📭 Нет ожидающих предложений",
            reply_markup=get_empty_inline_kb()
        )
    else:
        text = f"📬 Ожидающих предложений: {len(submissions)}\n\n" \
               "Выберите предложение для просмотра:"

        await callback.message.edit_text(
            text,
            reply_markup=get_pending_submissions_kb(submissions)
        )


@router.callback_query(F.data.startswith("view_submission_"))
async def view_submission(callback: CallbackQuery):
    """Просмотр конкретного предложения (админ — с решениями, пользователь — только свои ожидающие)"""
    await callback.answer()

    submission_id = int(callback.data.split("_")[-1])
    submission = await db.get_submission(submission_id)
    if not submission:
        await callback.message.edit_text(
            "❌ Предложение не найдено",
            reply_markup=get_empty_inline_kb()
        )
        return

    is_adm = await is_admin(callback.from_user.id)

    if is_adm:
        # Админ: показываем с кнопками одобрения/отклонения
        user_info = await get_user_info(submission['user_id'])
        user_name = f"{user_info['first_name']}"
        if user_info.get('username'):
            user_name += f" (@{user_info['username']})"
        forward_status = "✅ Разрешена публикация с автором" if submission['allow_forward'] else "🔒 Только анонимно"
        header_text = (
            f"┌─ 📬 <b>Предложение #{submission_id}</b>\n"
            f"│\n"
            f"│ 👤 От: {user_name}\n"
            f"│ 🔐 {forward_status}\n"
            f"│ 📅 {submission['created_at'][:19]}\n"
            f"└─────────────────────\n\n"
        )
        decision_kb = get_admin_decision_kb(submission_id, submission['allow_forward'])
    else:
        # Пользователь: только свои ожидающие, без кнопок решения
        if submission['user_id'] != callback.from_user.id:
            await callback.answer("❌ Нет доступа к этому предложению.", show_alert=True)
            return
        if submission['status'] != 'pending':
            await callback.answer("Это предложение уже рассмотрено.", show_alert=True)
            return
        header_text = (
            f"┌─ ⏳ <b>Предложение</b>\n"
            f"│ Ожидает рассмотрения\n"
            f"│ 📅 {submission['created_at'][:19]}\n"
            f"└─────────────────────\n\n"
        )
        decision_kb = get_empty_inline_kb()

    try:
        if submission['content_type'] in ['photo', 'video', 'document', 'animation']:
            cap = (submission['content'] or "").strip()
            new_caption = header_text + (cap if cap else "")
            await bot.copy_message(
                chat_id=callback.from_user.id,
                from_chat_id=submission['user_id'],
                message_id=submission['message_id'],
                caption=new_caption,
                parse_mode="HTML",
                reply_markup=decision_kb
            )
        else:
            content_text = submission['content'] if submission['content'] else "Текст не найден"
            await bot.send_message(
                chat_id=callback.from_user.id,
                text=header_text + "📄 <b>Текст предложения:</b>\n\n" + content_text,
                parse_mode="HTML",
                reply_markup=decision_kb
            )
    except Exception as e:
        logger.error(f"Ошибка отправки предложения: {e}")
        try:
            await bot.copy_message(
                chat_id=callback.from_user.id,
                from_chat_id=submission['user_id'],
                message_id=submission['message_id'],
                caption=header_text if submission['content_type'] != 'text' else None,
                parse_mode="HTML",
                reply_markup=decision_kb
            )
        except Exception as e2:
            logger.error(f"Ошибка запасного варианта: {e2}")
            await callback.message.edit_text(
                f"❌ Ошибка загрузки предложения: {str(e)}",
                reply_markup=get_empty_inline_kb()
            )


@router.callback_query(F.data == "change_channel")
async def change_channel(callback: CallbackQuery, state: FSMContext):
    """Смена канала/группы"""
    await callback.answer()
    
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔗 Отправьте:\n"
        "1. Инвайт-ссылку на канал или группу\n"
        "2. Username (@channel или @group)\n"
        "3. ID канала/группы\n\n"
        "⚠️ Бот должен быть админом!",
        reply_markup=get_cancel_kb()
    )
    await state.set_state(ChannelSetup.waiting_for_invite)


@router.callback_query(F.data.in_({"cancel", "cancel_submission"}))
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    """Отмена действия"""
    await callback.answer()
    await state.clear()
    
    channel_id = await db.get_channel_id()
    
    if not channel_id:
        await callback.message.edit_text(
            "❌ Действие отменено.",
            reply_markup=get_empty_inline_kb()
        )
        return
    
    await callback.message.edit_text(
        "❌ Действие отменено.",
        reply_markup=get_empty_inline_kb()
    )


# ============= ЗАПУСК БОТА =============

async def on_startup():
    """Действия при запуске бота"""
    await db.connect()
    logger.info("База данных подключена")
    
    # Проверяем наличие администратора
    admin_id = await db.get_admin_id()
    if not admin_id:
        code = await db.get_setting('admin_code')
        if not code:
            code = await db.generate_admin_code()
        print(f"\n{'='*50}")
        print(f"КОД АДМИНИСТРАТОРА: {code}")
        print(f"{'='*50}\n")
    else:
        logger.info(f"Администратор установлен: {admin_id}")
        channel_id = await db.get_channel_id()
        if channel_id:
            logger.info(f"Канал подключен: {channel_id}")


async def on_shutdown():
    """Действия при остановке бота"""
    await db.close()
    logger.info("База данных отключена")


async def main():
    """Главная функция"""
    dp.include_router(router)
    
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
