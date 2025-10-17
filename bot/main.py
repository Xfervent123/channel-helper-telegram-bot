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
    get_main_menu_kb,
    get_admin_panel_kb,
    get_forward_choice_kb,
    get_admin_decision_kb,
    get_cancel_kb,
    get_back_to_main_kb
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

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


async def copy_message_to_channel(
    message: Message,
    channel_id: int,
    from_user_id: int = None
):
    """Копирование сообщения в канал"""
    try:
        if from_user_id:
            # Пересылка от имени пользователя
            await bot.forward_message(
                chat_id=channel_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
        else:
            # Копирование без автора
            await bot.copy_message(
                chat_id=channel_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки в канал: {e}")
        return False


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
    
    welcome_text = f"👋 Добро пожаловать, {first_name}!\n\n"
    
    if admin:
        channel_id = await db.get_channel_id()
        if channel_id:
            welcome_text += "✅ Вы администратор бота.\n"
            welcome_text += "📢 Канал подключен.\n\n"
        else:
            welcome_text += "✅ Вы администратор бота.\n"
            welcome_text += "⚠️ Канал ещё не подключен.\n\n"
        welcome_text += "Выберите действие:"
    else:
        stats = await db.get_user_stats(user_id)
        welcome_text += (
            f"📊 Ваша статистика:\n"
            f"• Всего предложений: {stats['total']}\n"
            f"• Одобрено: {stats['approved']}\n"
            f"• Ожидает: {stats['pending']}\n\n"
            f"Выберите действие:"
        )
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_menu_kb(admin)
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Команда для администратора"""
    if not await is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора.")
        return
    
    pending_count = await db.get_pending_submissions_count()
    
    await message.answer(
        "⚙️ <b>Панель администратора</b>\n\n"
        f"📬 Ожидающих заявок: {pending_count}",
        reply_markup=get_admin_panel_kb(pending_count),
        parse_mode="HTML"
    )


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
            reply_markup=get_main_menu_kb(True)
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
        "1. Инвайт-ссылку на канал (https://t.me/...)\n"
        "2. Username канала (@channel)\n"
        "3. ID канала (например: -1001234567890)\n\n"
        "⚠️ Убедитесь, что бот добавлен в канал как администратор с правом публикации!",
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
                "❌ Неверный формат. Отправьте корректную ссылку, username или ID канала.",
                reply_markup=get_cancel_kb()
            )
            return
        
        # Проверяем доступ к каналу
        try:
            chat = await bot.get_chat(channel_id)
            
            # Проверяем, что это канал
            if chat.type != 'channel':
                await message.answer(
                    "❌ Это не канал. Отправьте ссылку на канал.",
                    reply_markup=get_cancel_kb()
                )
                return
            
            # Проверяем права бота
            bot_member = await bot.get_chat_member(chat.id, bot.id)
            if bot_member.status not in ['administrator', 'creator']:
                await message.answer(
                    "❌ Бот не является администратором канала.\n"
                    "Добавьте бота в канал как администратора с правом публикации сообщений!",
                    reply_markup=get_cancel_kb()
                )
                return
            
            # Сохраняем канал
            await db.set_channel_id(chat.id)
            
            await message.answer(
                f"✅ Канал успешно подключен!\n\n"
                f"📢 Название: {chat.title}\n"
                f"🆔 ID: {chat.id}\n\n"
                f"Теперь пользователи могут отправлять предложения!",
                reply_markup=get_main_menu_kb(True)
            )
            await state.clear()
            logger.info(f"Канал подключен: {chat.title} (ID: {chat.id})")
            
        except TelegramBadRequest as e:
            await message.answer(
                f"❌ Ошибка доступа к каналу.\n"
                f"Убедитесь, что:\n"
                f"1. Бот добавлен в канал\n"
                f"2. Бот является администратором\n"
                f"3. У бота есть право публикации\n\n"
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
            reply_markup=get_back_to_main_kb()
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
    # Сохраняем данные сообщения
    await state.update_data(
        message_id=message.message_id,
        content_type=message.content_type,
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
    
    # Сохраняем предложение в базу
    submission_id = await db.add_submission(
        user_id=callback.from_user.id,
        message_id=message_id,
        content_type=content_type,
        content=json.dumps({'chat_id': callback.from_user.id}),
        allow_forward=allow_forward
    )
    
    # Отправляем уведомление пользователю
    await callback.message.edit_text(
        "✅ Ваше предложение отправлено на модерацию!\n\n"
        "Вы получите уведомление, когда администратор примет решение.",
        reply_markup=get_back_to_main_kb()
    )
    
    # Отправляем администратору
    admin_id = await db.get_admin_id()
    if admin_id:
        user_info = await get_user_info(callback.from_user.id)
        user_name = f"{user_info['first_name']}"
        if user_info.get('username'):
            user_name += f" (@{user_info['username']})"
        
        forward_status = "✅ Разрешена публикация с автором" if allow_forward else "🔒 Только анонимно"
        
        # Пересылаем сообщение администратору
        try:
            await bot.copy_message(
                chat_id=admin_id,
                from_chat_id=callback.from_user.id,
                message_id=message_id,
                caption=f"📬 <b>Новое предложение #{submission_id}</b>\n\n"
                        f"👤 От: {user_name}\n"
                        f"🔐 {forward_status}\n\n"
                        f"{callback.message.caption or ''}",
                parse_mode="HTML",
                reply_markup=get_admin_decision_kb(submission_id, allow_forward)
            )
            
            # Если сообщение без caption, отправляем отдельно клавиатуру
            if not callback.message.caption and content_type == 'text':
                await bot.send_message(
                    chat_id=admin_id,
                    text=f"📬 <b>Новое предложение #{submission_id}</b>\n\n"
                         f"👤 От: {user_name}\n"
                         f"🔐 {forward_status}",
                    parse_mode="HTML",
                    reply_markup=get_admin_decision_kb(submission_id, allow_forward)
                )
        except Exception as e:
            logger.error(f"Ошибка отправки администратору: {e}")
    
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
    publish_type = parts[1]  # with-author или anonymous
    submission_id = int(parts[-1])
    
    # Получаем предложение
    submission = await db.get_submission(submission_id)
    if not submission:
        await callback.message.edit_text("❌ Предложение не найдено.")
        return
    
    if submission['status'] != 'pending':
        await callback.message.edit_text(f"❌ Предложение уже обработано (статус: {submission['status']}).")
        return
    
    # Получаем ID канала
    channel_id = await db.get_channel_id()
    if not channel_id:
        await callback.answer("❌ Канал не подключен!", show_alert=True)
        return
    
    # Публикуем в канал
    try:
        content_data = json.loads(submission['content'])
        user_chat_id = content_data['chat_id']
        
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
                text=f"✅ Ваше предложение #{submission_id} одобрено и опубликовано с {decision_text}!",
                reply_markup=get_back_to_main_kb()
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователя: {e}")
        
        # Обновляем сообщение администратора
        await callback.message.edit_caption(
            caption=f"{callback.message.caption}\n\n✅ <b>ОДОБРЕНО</b> ({decision_text})",
            parse_mode="HTML"
        )
        
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
        await callback.message.edit_text(f"❌ Предложение уже обработано (статус: {submission['status']}).")
        return
    
    # Обновляем статус
    await db.update_submission_status(submission_id, 'rejected', 'Отклонено администратором')
    
    # Уведомляем пользователя
    try:
        await bot.send_message(
            chat_id=submission['user_id'],
            text=f"❌ Ваше предложение #{submission_id} было отклонено.",
            reply_markup=get_back_to_main_kb()
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления пользователя: {e}")
    
    # Обновляем сообщение администратора
    try:
        await callback.message.edit_caption(
            caption=f"{callback.message.caption}\n\n❌ <b>ОТКЛОНЕНО</b>",
            parse_mode="HTML"
        )
    except:
        await callback.message.edit_text(
            text=f"{callback.message.text}\n\n❌ <b>ОТКЛОНЕНО</b>",
            parse_mode="HTML"
        )
    
    logger.info(f"Предложение #{submission_id} отклонено администратором")


# ============= НАВИГАЦИЯ ПО МЕНЮ =============

@router.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await callback.answer()
    await state.clear()
    
    admin = await is_admin(callback.from_user.id)
    stats = await db.get_user_stats(callback.from_user.id)
    
    if admin:
        channel_id = await db.get_channel_id()
        text = "⚙️ <b>Главное меню</b>\n\n"
        text += "✅ Вы администратор бота.\n"
        if channel_id:
            text += "📢 Канал подключен.\n"
        else:
            text += "⚠️ Канал не подключен.\n"
    else:
        text = (
            f"📊 <b>Ваша статистика:</b>\n\n"
            f"• Всего предложений: {stats['total']}\n"
            f"• Одобрено: {stats['approved']}\n"
            f"• Отклонено: {stats['rejected']}\n"
            f"• Ожидает: {stats['pending']}\n"
        )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_main_menu_kb(admin),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_panel")
async def show_admin_panel(callback: CallbackQuery):
    """Показ админ-панели"""
    await callback.answer()
    
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав!", show_alert=True)
        return
    
    pending_count = await db.get_pending_submissions_count()
    
    await callback.message.edit_text(
        "⚙️ <b>Панель администратора</b>\n\n"
        f"📬 Ожидающих заявок: {pending_count}",
        reply_markup=get_admin_panel_kb(pending_count),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "change_channel")
async def change_channel(callback: CallbackQuery, state: FSMContext):
    """Смена канала"""
    await callback.answer()
    
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔗 Отправьте:\n"
        "1. Инвайт-ссылку на канал\n"
        "2. Username канала (@channel)\n"
        "3. ID канала\n\n"
        "⚠️ Убедитесь, что бот добавлен в канал как администратор!",
        reply_markup=get_cancel_kb()
    )
    await state.set_state(ChannelSetup.waiting_for_invite)


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
        reply_markup=get_back_to_main_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.in_({"cancel", "cancel_submission"}))
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    """Отмена действия"""
    await callback.answer()
    await state.clear()
    
    admin = await is_admin(callback.from_user.id)
    
    await callback.message.edit_text(
        "❌ Действие отменено.",
        reply_markup=get_main_menu_kb(admin)
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
        print(f"🔐 КОД АДМИНИСТРАТОРА: {code}")
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
