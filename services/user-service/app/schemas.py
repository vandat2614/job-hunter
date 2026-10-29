from pydantic import BaseModel, EmailStr, Field


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)  # bcrypt limit is 72 bytes


class SubscriptionIn(BaseModel):
    skills: list[str] = []
    location: str | None = None
    min_salary: int | None = Field(None, ge=0)
    currency: str | None = None
    telegram_chat_id: str | None = None
    active: bool = True
