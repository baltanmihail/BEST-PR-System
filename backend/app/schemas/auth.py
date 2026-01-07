"""
Схемы для авторизации и регистрации
"""
from pydantic import BaseModel
from typing import Optional


class TelegramAuthData(BaseModel):
    """Данные авторизации от Telegram Web App"""
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    auth_date: int
    hash: str


class PersonalDataConsent(BaseModel):
    """Согласие на обработку персональных данных"""
    consent: bool
    consent_date: Optional[str] = None


class UserAgreementAccept(BaseModel):
    """Принятие пользовательского соглашения"""
    accepted: bool
    version: Optional[str] = None  # Версия соглашения


class RegistrationData(BaseModel):
    """Данные для регистрации (после авторизации через Telegram)"""
    telegram_auth: TelegramAuthData
    personal_data_consent: PersonalDataConsent
    user_agreement: UserAgreementAccept
