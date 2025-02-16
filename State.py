from aiogram.fsm.state import StatesGroup, State


class Gen(StatesGroup):
    photo = State()
    descript = State()
    message_sent = State()