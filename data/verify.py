import io
import cv2
# import face_recognition
import mediapipe as mp
import numpy as np
import random
from aiogram import types, Router, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from main import bot, i18n
from models import User

router = Router()

class VerificationStates(StatesGroup):
    waiting_for_gesture_photo = State()

@router.message(Command('verify_with_gesture'))
async def request_gesture_photo(message: types.Message, state: FSMContext):
    gestures = [
        i18n.gettext('покажите два пальца'),
        i18n.gettext('поднимите правую руку'),
        i18n.gettext('сделайте знак ОК'),
        i18n.gettext('покажите ладонь')
    ]
    selected_gesture = random.choice(gestures)
    await state.update_data(selected_gesture=selected_gesture)
    await message.reply(i18n.gettext(f"Для верификации, пожалуйста, {selected_gesture} и отправьте фото."))
    await state.set_state(VerificationStates.waiting_for_gesture_photo)

@router.message(F.photo, F.state(VerificationStates.waiting_for_gesture_photo))
async def handle_photo(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        selected_gesture = data.get('selected_gesture')

        if not selected_gesture:
            await message.reply(i18n.gettext('Сначала запросите верификацию с жестом.'))
            return

        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        photo_bytes = await bot.download_file(file_info.file_path)

        is_gesture_correct, image_with_landmarks = await verify_gesture(io.BytesIO(photo_bytes), selected_gesture)

        if not is_gesture_correct:
            await message.reply(i18n.gettext('Пожалуйста, покажите правильный жест.'))
            return

        face_encoding = await get_face_encoding(io.BytesIO(photo_bytes))
        if face_encoding is None:
            await message.reply(i18n.gettext('Не удалось распознать лицо. Пожалуйста, попробуйте снова.'))
            return

        user = await User.get_or_none(username=message.from_user.username)
        if user:
            reference_face_encoding = np.array(user.reference_face_encoding)
            match = face_recognition.compare_faces([reference_face_encoding], face_encoding)
            if match[0]:
                await message.reply(i18n.gettext('Вы успешно верифицированы!'), parse_mode=ParseMode.HTML)
            else:
                await message.reply(i18n.gettext('Лицо не совпадает с эталонным. Верификация не пройдена.'))
        else:
            await User.create(username=message.from_user.username, reference_face_encoding=face_encoding.tolist(),
                              is_verified=True)
            await message.reply(i18n.gettext('Вы верифицированы и ваша эталонная фотография сохранена!'),
                                parse_mode=ParseMode.HTML)

        await state.clear()
    except Exception as e:
        await message.reply(i18n.gettext('Произошла ошибка при обработке фото. Пожалуйста, попробуйте снова.'))
        print(f"Error: {e}")

async def verify_gesture(photo_bytes, expected_gesture):
    try:
        mp_hands = mp.solutions.hands
        hands = mp_hands.Hands(static_image_mode=True)

        image = cv2.imdecode(np.frombuffer(photo_bytes.read(), np.uint8), cv2.IMREAD_COLOR)
        results = hands.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

        if not results.multi_hand_landmarks:
            return False, None

        for hand_landmarks in results.multi_hand_landmarks:
            landmarks = hand_landmarks.landmark
            if expected_gesture == i18n.gettext('покажите два пальца') and is_two_fingers_up(landmarks):
                return True, image
            elif expected_gesture == i18n.gettext('поднимите правую руку') and is_right_hand_up(landmarks):
                return True, image
            elif expected_gesture == i18n.gettext('сделайте знак OK') and is_ok(landmarks):
                return True, image
            elif expected_gesture == i18n.gettext('покажите ладонь') and is_hand_open(landmarks):
                return True, image

        return False, None
    except Exception as e:
        print(f"Error: {e}")
        return False, None

async def get_face_encoding(photo_bytes):
    try:
        image = face_recognition.load_image_file(photo_bytes)
        face_encodings = face_recognition.face_encodings(image)

        if face_encodings:
            return face_encodings[0]
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def is_two_fingers_up(landmarks):
    is_index_up = landmarks[8].y < landmarks[6].y
    is_middle_up = landmarks[12].y < landmarks[10].y
    is_ring_down = landmarks[16].y > landmarks[14].y
    is_pinky_down = landmarks[20].y > landmarks[18].y

    return is_index_up and is_middle_up and is_ring_down and is_pinky_down

def is_right_hand_up(landmarks):
    wrist_y = landmarks[0].y
    return wrist_y < 0.5

def is_ok(landmarks):
    thumb_tip = landmarks[4]
    index_tip = landmarks[8]

    distance = ((thumb_tip.x - index_tip.x) ** 2 + (thumb_tip.y - index_tip.y) ** 2) ** 0.5
    return distance < 0.05

def is_hand_open(landmarks):
    is_thumb_up = landmarks[4].y < landmarks[3].y
    is_index_up = landmarks[8].y < landmarks[7].y
    is_middle_up = landmarks[12].y < landmarks[11].y
    is_ring_up = landmarks[16].y < landmarks[15].y
    is_pinky_up = landmarks[20].y < landmarks[19].y

    return is_thumb_up and is_index_up and is_middle_up and is_ring_up and is_pinky_up
