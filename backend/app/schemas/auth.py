from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    username: str
    is_authenticated: bool = True
