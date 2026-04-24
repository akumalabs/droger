from pydantic import BaseModel, EmailStr, Field


class RegisterReq(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str | None = None


class LoginReq(BaseModel):
    email: EmailStr
    password: str


class VerifyEmailReq(BaseModel):
    token: str


class ForgotPasswordReq(BaseModel):
    email: EmailStr


class ResetPasswordReq(BaseModel):
    token: str
    password: str = Field(min_length=6, max_length=128)
