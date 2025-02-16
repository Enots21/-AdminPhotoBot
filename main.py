import asyncio
import locale
import datetime
import json
import logging
import os

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, \
    KeyboardButton, InlineKeyboardButton, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import TOKEN, ADMIN_ID  # Не забудьте указать свои токен и ID администратора

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
router = Router()

# Путь к файлу JSON
USERS_FILE = "users.json"


# Устанавливаем локаль на русский язык
locale.setlocale(locale.LC_TIME, 'ru_RU')

# Получаем текущую дату и время
now = datetime.datetime.now()

# Форматируем дату в строку "день месяц год"
formatted_date = now.strftime("%d %B %Y")


# Загрузка пользователей из JSON
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as file:
            return json.load(file)
    return {}


# Сохранение пользователей в JSON
def save_users(users):
    try:
        with open(USERS_FILE, "w") as file:
            json.dump(users, file, indent=4)
    except IOError as e:
        print(f"Ошибка при записи файла: {e}")


class Form(StatesGroup):
    waiting_for_photos = State()
    waiting_for_text = State()
    waiting_for_broadcast_text = State()  # Новое состояние для рассылки


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    users = load_users()

    # Добавляем пользователя в JSON, если его еще нет
    if str(user_id) not in users:
        users[str(user_id)] = {
            "username": message.from_user.username,
            "full_name": message.from_user.full_name,
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_users(users)

    await message.answer("Привет! Отправь мне фотографию или ссылку на фотографию.")
    await state.set_state(Form.waiting_for_photos)
    await message.answer("Выберите действие:", reply_markup=show_main_keyboard(message))


def show_main_keyboard(message: types.Message):
    # Основные кнопки для всех пользователей
    keyboard = [
        [KeyboardButton(text='Начало работы')],
        [KeyboardButton(text='Помощь')]
    ]

    # Если пользователь админ, добавляем дополнительные кнопки
    if message.from_user.id == int(ADMIN_ID):
        keyboard.append([KeyboardButton(text='Рассылка')])
        keyboard.append([KeyboardButton(text='Информация о боте')])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )


@router.message(F.text == 'Начало работы')
async def send_photo(message: types.Message, state: FSMContext):
    await message.answer("Отправь мне фотографию")
    await state.set_state(Form.waiting_for_photos)
    await state.update_data(photos=[])  # Инициализируем пустой список для фото


@router.message(Form.waiting_for_photos)
async def process_photos(message: types.Message, state: FSMContext):
    if message.photo:
        # Получаем текущие данные из состояния
        data = await state.get_data()
        photos = data.get("photos", [])  # Список фотографий пользователя
        message_sent = data.get("message_sent", False)
        media_group_id = message.media_group_id  # ID медиагруппы


        # Если это одиночное фото (без медиагруппы)
        if not media_group_id:
            if message.photo:
                photo = message.photo[-1]  # Берем самое большое доступное фото
                file_id = photo.file_id
                photos.append(file_id)  # Добавляем file_id в список
                # Если фотографий больше 3 и сообщение еще не отправлено
            if len(photos) > 0 and not message_sent:
                await message.answer('Ожидайте пожалуйста загрузки фотографий')
                message_sent = True  # Устанавливаем флаг, что сообщение отправлено

                # Обновляем данные в состоянии
                await state.update_data(photos=photos, message_sent=message_sent)
                nu = InlineKeyboardBuilder()  # Инициализируем клавиатуру
                nu.row(InlineKeyboardButton(text='Отправить фото без текста', callback_data='yess_photo'))
                nu.row(InlineKeyboardButton(text='Написать текст', callback_data='nex_text'))
                await message.answer("Фото добавлено! Отправьте еще или нажмите Отправить фото или Написать текст.",
                                     reply_markup=nu.as_markup())
            return

        # Если это медиагруппа
        if media_group_id:
            # Получаем или создаем список для текущей медиагруппы
            media_groups = data.get("media_groups", {})
            if media_group_id not in media_groups:
                media_groups[media_group_id] = []

            # Добавляем фото в медиагруппу
            if message.photo:
                photo = message.photo[-1]  # Берем самое большое доступное фото
                file_id = photo.file_id
                media_groups[media_group_id].append(file_id)
                photos.append(file_id)  # Добавляем file_id в общий список

            # Обновляем данные в состоянии
            await state.update_data(photos=photos, media_groups=media_groups)

        # Ждем 2 секунды, чтобы все фото из группы успели прийти
        await asyncio.sleep(1)


        # Проверяем, завершена ли медиагруппа
        if media_group_id in media_groups:
            media_group = media_groups.pop(media_group_id)
        nu = InlineKeyboardBuilder()  # Инициализируем клавиатуру
        nu.row(InlineKeyboardButton(text='Отправить фото без текста', callback_data='yess_photo'))
        nu.row(InlineKeyboardButton(text='Написать текст', callback_data='nex_text'))
        await message.answer(f'Загружено фотографий: {len(media_group)}', reply_markup=nu.as_markup())
    else:  # Если это не медиагруппа
        await message.answer("Отправьте фотографию или ссылку на фотографию.")


@router.callback_query(F.data == 'yess_photo')
async def yes_photo(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()  # Подтверждаем callback
    await callback.message.delete()  # Удаляем сообщение с кнопками

    # Получаем данные из состояния
    data = await state.get_data()
    photos = data.get("photos", [])
    text = data.get("text", "")

    # Если есть фото для отправки
    if photos:
        # Создаем список медиа для отправки
        media_list = [InputMediaPhoto(media=file_id) for file_id in photos]

        # Добавляем подпись к первому фото, если есть текст
        if text and media_list:
            media_list[0].caption = f"{formatted_date}\n\n{callback.from_user.full_name}\n{text}"
        else:
            media_list[0].caption = f"{formatted_date}\n\n{callback.from_user.full_name}"
        # Отправляем медиагруппу админу
        await bot.send_media_group(ADMIN_ID, media=media_list)
        await callback.message.answer(f"{formatted_date}\n\nВаш альбом фотографий успешно отправлен админу!")

    # Очищаем состояние
    await state.clear()

@router.callback_query(F.data == 'nex_text')
async def next_text(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer("Введите текст для отправки:")
    await state.set_state(Form.waiting_for_text)

@router.message(Form.waiting_for_text)
async def process_text(message: types.Message, state: FSMContext):
    # Сохраняем текст в состоянии
    text = message.text
    await state.update_data(text=text)

    # Получаем данные из состояния
    data = await state.get_data()
    photos = data.get("photos", [])

    # Создаем инлайн-клавиатуру
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text='Отправить фото без текста', callback_data='yess_photo'))
    builder.row(InlineKeyboardButton(text='Изменить текст', callback_data='nex_text'))
    await message.answer(
        f"Текст сохранен: {text}\nЗагружено фотографий: {len(photos)}",
        reply_markup=builder.as_markup()
    )


# Обработка кнопки "Рассылка"
@router.message(F.text == 'Рассылка')
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != int(ADMIN_ID):
        await message.answer("Эта функция доступна только администратору.")
    else:
        await message.answer("Введите текст для рассылки:")
        await state.set_state(Form.waiting_for_broadcast_text)


# Обработка текста для рассылки
@router.message(Form.waiting_for_broadcast_text)
async def process_broadcast_text(message: types.Message, state: FSMContext):
    broadcast_text = message.text

    # Загружаем пользователей
    users = load_users()
    sent_count = 0  # Счетчик успешно отправленных сообщений

    for user_id in users:
        try:
            if user_id == ADMIN_ID:
                continue  # Пропускаем администратора
            await bot.send_message(user_id, f"Рассылка от администратора:\n\n{broadcast_text}")
            sent_count += 1  # Увеличиваем счетчик только для успешных отправок
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

    await message.answer(
        f"Рассылка завершена. Сообщение отправлено {sent_count} пользователям.")  # Используем sent_count
    await state.clear()  # Очищаем состояние


@router.message(F.text == 'Помощь')
async def help(message: types.Message):
    await message.answer('Тут когда-то ходила эта функция, но она не работает.')

# Обработка кнопки "Информация о боте"
@router.message(F.text == 'Информация о боте')
async def bot_info(message: types.Message):
    if message.from_user.id != int(ADMIN_ID):
        await message.answer("Эта функция доступна только администратору.")
    else:
        # Загружаем пользователей
        users = load_users()
        total_users = len(users)

        # Формируем информацию о боте
        info_text = (
            f"📊 **Информация о боте:**\n"
            f"👤 Всего пользователей: {total_users}\n"
            f"🆔 ID администратора: {ADMIN_ID}\n"
            f"🤖 Версия бота: 1.0\n"
            f"📅 Дата запуска: 2025-02-04"
        )

        await message.answer(info_text)


async def main():
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())