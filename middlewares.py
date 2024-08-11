import contextvars
import logging
from typing import Optional

from aiogram import BaseMiddleware, types
from aiogram.types import Update
from models import User
from aiogram.utils.i18n import I18nMiddleware, I18n

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

locale_var = contextvars.ContextVar('locale', default='ru')

class CustomI18nMiddleware(I18nMiddleware):
    def __init__(
            self,
            i18n: I18n,
            i18n_key: Optional[str] = "i18n",
            middleware_key: str = "i18n_middleware",
    ) -> None:
        super().__init__(i18n=i18n, i18n_key=i18n_key, middleware_key=middleware_key)

    async def get_locale(self, event: types.TelegramObject, data: any) -> str:
        event_from_user: Optional[User] = data.get("event_from_user")
        user_id = event_from_user.id
        db_user = await User.get_or_none(user_id=user_id)
        if db_user and db_user.language_code in ('en', 'ru', 'uz', 'es'):
            return db_user.language_code
        language_code = event_from_user.language_code
        if language_code in ('en', 'ru', 'uz', 'es'):
            return language_code
        return 'ru'

    async def on_process_message(self, message: types.Message, data: dict):
        logger.info("Setting i18n context")
        i18n = self.i18n
        i18n.ctx_locale.set('ru')
        data['i18n'] = i18n

def get_current_locale() -> str:
    current_locale = locale_var.get()
    logger.info(f"Current locale: {current_locale}")
    return current_locale