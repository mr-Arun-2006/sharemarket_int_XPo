from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class VerifyRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=40, max_length=256)


class TwoFactorCodeRequest(BaseModel):
    challenge_id: str = Field(min_length=16, max_length=128)
    code: str = Field(min_length=6, max_length=6)


class TwoFactorVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class LoginResponse(BaseModel):
    status: str
    access_token: str | None = None
    # Refresh tokens are now kept in an HttpOnly cookie.
    refresh_token: str | None = None
    challenge_id: str | None = None
    requires_2fa: bool = False
    token_type: str = "bearer"


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
