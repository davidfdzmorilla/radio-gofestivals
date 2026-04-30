from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    username: str | None
    display_name: str | None
    bio: str | None
    avatar_url: str | None
    is_public: bool
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserOut
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: uuid.UUID
    new_password: str = Field(min_length=8, max_length=200)


class FavoriteStreamRef(BaseModel):
    id: uuid.UUID
    url: str
    codec: str | None
    bitrate: int | None
    format: str | None


class FavoriteOut(BaseModel):
    station_id: uuid.UUID
    slug: str
    name: str
    country_code: str | None
    city: str | None
    curated: bool
    quality_score: int
    status: str
    primary_stream: FavoriteStreamRef | None
    created_at: datetime


class FavoritesListResponse(BaseModel):
    items: list[FavoriteOut]
    total: int


class MigrateFavoritesRequest(BaseModel):
    station_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


class MigrateFavoritesResponse(BaseModel):
    added: int
    already_existed: int
    invalid: int


class LikeResponse(BaseModel):
    user_voted: bool
    votes_local: int
