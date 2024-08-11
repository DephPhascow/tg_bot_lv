import logging
import random
import string
from aiogram import types, F, Router
from aiogram.filters import Command
from geopy import Nominatim
from keyboards.reply_kb import main_menu_kb
from models import User, LeomatchMain, LeomatchRegistration
from keyboards import reply_kb
from main import i18n
from shortcuts import add_leo, get_leo, show_profile, update_leo
from aiogram.fsm.context import FSMContext
from aiogram.utils.i18n import lazy_gettext as __
from aiogram.utils.i18n import gettext as _

geolocator = Nominatim(user_agent="НУЖНЫЙ УЗЕР АГЕНТ")

router = Router()

async def return_main(message: types.Message, state: FSMContext):
    await message.answer(i18n.gettext("Вы успешно отменили регистрацию! Возвращаемся в главное меню."), reply_markup=main_menu_kb())
    await state.clear()

async def now_send_photo(message: types.Message, state: FSMContext):
    leo = await User.get_or_none(user_id=message.from_user.id)
    kwargs = {}
    if leo:
        kwargs['reply_markup'] = reply_kb.save_current()
    await message.answer(i18n.gettext("Теперь пришли фото или запиши видео 👍 (до 15 сек), его будут видеть другие пользователи"), **kwargs)
    await state.set_state(LeomatchRegistration.SEND_PHOTO)

async def save_media(message: types.Message, state: FSMContext, url: str, media_type: str):
    await state.update_data(photo=url, media_type=media_type)
    data = await state.get_data()
    age = data['age']
    full_name = data['full_name']
    about_me = data['about_me']
    city = data['city']
    await show_profile(message, message.from_user.id, full_name, age, city, about_me, url, media_type)
    await message.answer(i18n.gettext("Всё верно?"), reply_markup=reply_kb.final_registration())
    await state.set_state(LeomatchRegistration.FINAL)

@router.message(F.text == i18n.gettext("Давай, начнем!"))
async def bot_start(message: types.Message, state: FSMContext):
    await message.answer(i18n.gettext("Настоятельно рекомендуем указать username или в настройках разрешение на пересылку сообщения иначе Вам не смогут написать те, кого вы лайкните"))
    await begin_registration(message, state)

@router.message(F.text == i18n.gettext("Отменить"), F.state(LeomatchRegistration.AGE))
async def cancel_registration(message: types.Message, state: FSMContext):
    await message.answer(i18n.gettext("Отменена регистрация!"))
    await return_main(message, state)

@router.message(F.text, F.state(LeomatchRegistration.AGE))
async def set_age(message: types.Message, state: FSMContext):
    try:
        age = int(message.text)
        await state.update_data(age=age)
        await message.answer(i18n.gettext("Теперь выберите минимальный возраст"))
        await state.set_state(LeomatchRegistration.MIN_AGE)
    except ValueError:
        await message.answer(i18n.gettext("Пожалуйста, введите возраст цифрами"))

@router.message(F.text, F.state(LeomatchRegistration.MIN_AGE))
async def set_min_age(message: types.Message, state: FSMContext):
    try:
        min_age = int(message.text)
        await state.update_data(min_age=min_age)
        await message.answer(i18n.gettext("Теперь выберите максимальный возраст"))
        await state.set_state(LeomatchRegistration.MAX_AGE)
    except ValueError:
        await message.answer(i18n.gettext("Пожалуйста, введите возраст цифрами"))

@router.message(F.text, F.state(LeomatchRegistration.MAX_AGE))
async def set_max_age(message: types.Message, state: FSMContext):
    try:
        max_age = int(message.text)
        data = await state.get_data()
        min_age = data['min_age']
        await state.update_data(max_age=max_age)
        await message.reply(f'{i18n.gettext("Вы задали возрастной диапазон от")} {min_age} {i18n.gettext("до")} {max_age}')
        await message.answer(i18n.gettext("Теперь определимся с полом!"), reply_markup=reply_kb.chooice_sex())
        await state.set_state(LeomatchRegistration.SEX)
    except ValueError:
        await message.answer(i18n.gettext("Пожалуйста, введите возраст цифрами"))

@router.message(F.text == i18n.gettext("Я парень"), F.state(LeomatchRegistration.SEX))
async def set_sex_male(message: types.Message, state: FSMContext):
    await set_sex("MALE", message, state)

@router.message(F.text == i18n.gettext("Я девушка"), F.state(LeomatchRegistration.SEX))
async def set_sex_female(message: types.Message, state: FSMContext):
    await set_sex("FEMALE", message, state)

@router.message(F.text, F.state(LeomatchRegistration.SEX))
async def ask_sex(message: types.Message):
    await message.answer(i18n.gettext("Пожалуйста, укажите Ваш пол, нажав на кнопку"))

@router.message(F.text == i18n.gettext("Парня"), F.state(LeomatchRegistration.WHICH_SEARCH))
async def set_search_male(message: types.Message, state: FSMContext):
    await set_which_search("MALE", message, state)

@router.message(F.text == i18n.gettext("Девушку"), F.state(LeomatchRegistration.WHICH_SEARCH))
async def set_search_female(message: types.Message, state: FSMContext):
    await set_which_search("FEMALE", message, state)

@router.message(F.text == i18n.gettext("Мне всё равно"), F.state(LeomatchRegistration.WHICH_SEARCH))
async def set_search_any(message: types.Message, state: FSMContext):
    await set_which_search("ANY", message, state)


@router.message(F.text, F.state(LeomatchRegistration.SEX))
async def set_sex(message: types.Message, state: FSMContext):
    sex = message.text
    if sex not in ["Мужчина", "Женщина"]:
        await message.answer(i18n.gettext("Пожалуйста, выберите правильный пол."))
        return
    await state.update_data(sex=sex)
    await message.answer(i18n.gettext("Кого Вы ищите?"), reply_markup=reply_kb.which_search())
    await state.set_state(LeomatchRegistration.WHICH_SEARCH)

@router.message(F.text, F.state(LeomatchRegistration.WHICH_SEARCH))
async def set_which_search(message: types.Message, state: FSMContext):
    which_search = message.text
    if which_search not in ["Парня", "Девушку", "Мне всё равно"]:
        await message.answer(i18n.gettext("Пожалуйста, выберите правильный вариант поиска."))
        return
    await state.update_data(which_search=which_search)
    await message.answer(i18n.gettext("Из какого ты города?"), reply_markup=reply_kb.remove())
    await state.set_state(LeomatchRegistration.CITY)

@router.message(F.text, F.state(LeomatchRegistration.CITY))
async def set_city(message: types.Message, state: FSMContext):
    city = message.text
    await state.update_data(city=city)
    button = types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text=message.from_user.full_name)]], resize_keyboard=True, one_time_keyboard=True)
    await message.answer(i18n.gettext("Как мне тебя называть?"), reply_markup=button)
    await state.set_state(LeomatchRegistration.FULL_NAME)

def generate_referral_code(length=10):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

@router.message(F.text == i18n.gettext("Получить реферальный код"))
async def get_referral_handler(message: types.Message):
    user_id = message.from_user.id
    user = await User.get_or_none(user_id=user_id)
    if user:
        referral_code = user.referral_code
        await message.answer(i18n.gettext(f"Ваш реферальный код: {referral_code}. Поделитесь им, чтобы получать дополнительные просмотры профилей."))
    else:
        await message.answer(i18n.gettext("Пожалуйста, сначала зарегистрируйтесь, чтобы получить реферальный код."))

@router.message(F.text, F.state(LeomatchRegistration.FULL_NAME))
async def set_full_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    referral_code = generate_referral_code()
    if len(name) > 15:
        await message.answer(i18n.gettext("Пожалуйста, введите имя не более 15 символов"))
        return
    await state.update_data(full_name=name)
    user_id = message.from_user.id
    user = await User.get_or_none(user_id=user_id)
    if not user:
        user = await User.create(user_id=user_id, full_name=name, referral_code=referral_code)
    await message.reply(f"{i18n.gettext('Ваш профиль был успешно создан!')} {i18n.gettext('Вы можете просматривать других пользователей, когда они будут вас лайкать!')}")
    await now_send_photo(message, state)

@router.message(F.photo, F.state(LeomatchRegistration.SEND_PHOTO))
async def handle_photo(message: types.Message, state: FSMContext):
    file_url = await message.photo[-1].get_url()
    await save_media(message, state, file_url, "photo")

@router.message(F.video, F.state(LeomatchRegistration.SEND_PHOTO))
async def handle_video(message: types.Message, state: FSMContext):
    file_url = await message.video.get_url()
    await save_media(message, state, file_url, "video")

@router.message(F.text, F.state(LeomatchRegistration.FINAL))
async def finalize_registration(message: types.Message, state: FSMContext):
    if message.text == i18n.gettext("Да"):
        data = await state.get_data()
        user_id = message.from_user.id
        leo = await User.get_or_none(user_id=user_id)
        if not leo:
            await message.answer(i18n.gettext("Произошла ошибка при регистрации. Пожалуйста, попробуйте снова."))
            return
        await User.update_or_create(
            user_id=user_id,
            defaults={
                'full_name': data['full_name'],
                'age': data['age'],
                'min_age': data['min_age'],
                'max_age': data['max_age'],
                'sex': data['sex'],
                'which_search': data['which_search'],
                'about_me': data['about_me'],
                'city': data['city'],
                'photo': data['photo'],
                'media_type': data['media_type'],
            }
        )
        await message.answer(i18n.gettext("Ваша регистрация завершена! Теперь вы можете искать и просматривать профили других пользователей."), reply_markup=main_menu_kb())
        await state.clear()
    elif message.text == i18n.gettext("Нет"):
        await message.answer(i18n.gettext("Регистрация отменена."), reply_markup=main_menu_kb())
        await state.clear()
    else:
        await message.answer(i18n.gettext("Пожалуйста, ответьте 'Да' или 'Нет'."))



@router.message(F.text, F.state(LeomatchRegistration.AGE))
async def begin_registration(message: types.Message, state: FSMContext):
    age = message.text
    if not age.isdigit():
        await message.answer(i18n.gettext("Пожалуйста, введите возраст цифрами."))
        return
    await state.update_data(age=int(age))
    await message.answer(i18n.gettext("Теперь укажите город, в котором вы находитесь."), reply_markup=reply_kb.remove())
    await state.set_state(LeomatchRegistration.CITY)

@router.message(Command(commands=['start', 'help']))
async def send_welcome(message: types.Message, state: FSMContext):
    try:
        user = await User.get_or_none(user_id=message.from_user.id)
        if user:
            if not user.is_verified:
                await message.reply(_("Рекомендуем пройти верификацию, чтобы другие пользователи доверяли вам больше."))
            if not user.is_registered:
                await message.reply(_("Вы не завершили регистрацию. Давайте начнем с вашего возраста."), reply_markup=main_menu_kb())
                await state.set_state(LeomatchRegistration.AGE)
            else:
                await message.reply(_("Добро пожаловать обратно!"), reply_markup=main_menu_kb())
        else:
            await message.reply(_("Вы не зарегистрированы. Давайте начнем с вашего возраста."), reply_markup=main_menu_kb())
            await state.set_state(LeomatchRegistration.AGE)
    except Exception as e:
        await message.reply(f"Error in send_welcome handler: {e}")