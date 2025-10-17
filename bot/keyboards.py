from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Главное меню"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📝 Предложить новость", callback_data="submit_news")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats")
    )
    
    if is_admin:
        builder.row(
            InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel")
        )
    
    return builder.as_markup()


def get_admin_panel_kb(pending_count: int = 0) -> InlineKeyboardMarkup:
    """Админ-панель"""
    builder = InlineKeyboardBuilder()
    
    pending_text = f"📬 Ожидающие ({pending_count})" if pending_count > 0 else "📭 Нет ожидающих"
    
    builder.row(
        InlineKeyboardButton(text=pending_text, callback_data="view_pending")
    )
    builder.row(
        InlineKeyboardButton(text="🔗 Сменить канал", callback_data="change_channel")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статистика бота", callback_data="bot_stats")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")
    )
    
    return builder.as_markup()


def get_forward_choice_kb() -> InlineKeyboardMarkup:
    """Выбор разрешения пересылки"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="✅ Разрешить публикацию от моего имени",
            callback_data="allow_forward_yes"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔒 Опубликовать анонимно",
            callback_data="allow_forward_no"
        )
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_submission")
    )
    
    return builder.as_markup()


def get_admin_decision_kb(submission_id: int, allow_forward: bool) -> InlineKeyboardMarkup:
    """Кнопки решения администратора"""
    builder = InlineKeyboardBuilder()
    
    if allow_forward:
        builder.row(
            InlineKeyboardButton(
                text="✅ Опубликовать с автором",
                callback_data=f"approve_with_author_{submission_id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text="✅ Опубликовать анонимно",
            callback_data=f"approve_anonymous_{submission_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=f"reject_{submission_id}"
        )
    )
    
    return builder.as_markup()


def get_cancel_kb() -> InlineKeyboardMarkup:
    """Кнопка отмены"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    return builder.as_markup()


def get_back_to_main_kb() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_main")
    )
    return builder.as_markup()
