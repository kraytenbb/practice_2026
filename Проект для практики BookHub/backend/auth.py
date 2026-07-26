from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from models import User


COOKIE_NAME = "bookhub_session"
SESSION_LIFETIME_SECONDS = 60 * 60 * 24 * 30


SECRET_KEY = os.getenv(
    "BOOKHUB_SECRET_KEY",
    "bookhub-local-development-secret-change-me"
).encode("utf-8")


@dataclass
class AuthResult:
    user: Optional[User]
    error: Optional[str] = None


def hash_password(password: str) -> str:

    salt = secrets.token_bytes(16)

    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        310_000
    )

    return (
        "pbkdf2_sha256$310000$"
        f"{base64.urlsafe_b64encode(salt).decode('ascii')}$"
        f"{base64.urlsafe_b64encode(derived_key).decode('ascii')}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, hash_text = (
            stored_hash.split("$", maxsplit=3)
        )

        if algorithm != "pbkdf2_sha256":
            return False

        iterations = int(iterations_text)
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected_hash = base64.urlsafe_b64decode(
            hash_text.encode("ascii")
        )

        actual_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations
        )

        return hmac.compare_digest(
            actual_hash,
            expected_hash
        )

    except (ValueError, TypeError):
        return False


def create_session_token(user_id: int) -> str:
    expires_at = int(time.time()) + SESSION_LIFETIME_SECONDS
    payload = f"{user_id}.{expires_at}"

    signature = hmac.new(
        SECRET_KEY,
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    raw_token = f"{payload}.{signature}".encode("utf-8")

    return base64.urlsafe_b64encode(
        raw_token
    ).decode("ascii")


def read_session_token(token: str) -> Optional[int]:
    try:
        decoded = base64.urlsafe_b64decode(
            token.encode("ascii")
        ).decode("utf-8")

        user_id_text, expires_at_text, signature = (
            decoded.split(".", maxsplit=2)
        )

        payload = f"{user_id_text}.{expires_at_text}"

        expected_signature = hmac.new(
            SECRET_KEY,
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(
            signature,
            expected_signature
        ):
            return None

        if int(expires_at_text) < int(time.time()):
            return None

        return int(user_id_text)

    except (
        ValueError,
        UnicodeDecodeError,
        base64.binascii.Error
    ):
        return None


def get_current_user(
    request: Request,
    db: Session
) -> Optional[User]:
    token = request.cookies.get(COOKIE_NAME)

    if not token:
        return None

    user_id = read_session_token(token)

    if user_id is None:
        return None

    return (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )


def validate_registration(
    db: Session,
    username: str,
    email: str,
    password: str,
    password_repeat: str
) -> Optional[str]:
    username = username.strip()
    email = email.strip().lower()

    if len(username) < 3:
        return "Имя пользователя должно содержать минимум 3 символа."

    if len(username) > 50:
        return "Имя пользователя слишком длинное."

    if "@" not in email or "." not in email.split("@")[-1]:
        return "Введите корректный адрес электронной почты."

    if len(password) < 6:
        return "Пароль должен содержать минимум 6 символов."

    if password != password_repeat:
        return "Пароли не совпадают."

    username_exists = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    if username_exists:
        return "Пользователь с таким именем уже существует."

    email_exists = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if email_exists:
        return "Пользователь с такой почтой уже существует."

    return None
