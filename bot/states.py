from aiogram.fsm.state import State, StatesGroup


class AdminSetup(StatesGroup):
    """Состояния настройки администратора"""
    waiting_for_code = State()


class ChannelSetup(StatesGroup):
    """Состояния настройки канала"""
    waiting_for_invite = State()


class SubmissionStates(StatesGroup):
    """Состояния отправки предложения"""
    waiting_for_content = State()
    waiting_for_forward_choice = State()
