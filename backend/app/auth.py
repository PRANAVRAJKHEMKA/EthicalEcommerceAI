"""FairCart AI — Authentication & Session Verification Services (Milestone 6B)

Provides Argon2id password verification, server-validated session management,
failed login rate limiting, and FastAPI security dependencies.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import secrets
import time
from fastapi import Depends, HTTPException, Request, Response, status
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from backend.app.config import settings
from backend.app.db.repository import CatalogRepository, UserEntity

ph = PasswordHasher()

# Sliding-window rate limiter for failed login attempts (max 5 failures per 60s per IP/username)
FAILED_LOGIN_ATTEMPTS: dict[str, list[float]] = defaultdict(list)

def record_failed_login(identifier: str) -> None:
    """Records a failed login attempt timestamp."""
    FAILED_LOGIN_ATTEMPTS[identifier].append(time.time())

def check_login_rate_limit(identifier: str, max_failures: int = 5, window_seconds: int = 60) -> None:
    """Enforces rate limiting on repeated failed authentication attempts."""
    now = time.time()
    history = FAILED_LOGIN_ATTEMPTS[identifier]
    # Prune expired timestamps
    active = [t for t in history if now - t < window_seconds]
    FAILED_LOGIN_ATTEMPTS[identifier] = active
    if len(active) >= max_failures:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Please wait {window_seconds} seconds before trying again.",
        )

def clear_login_failures(identifier: str) -> None:
    """Clears failed login attempts upon successful authentication."""
    if identifier in FAILED_LOGIN_ATTEMPTS:
        del FAILED_LOGIN_ATTEMPTS[identifier]

def hash_password(password: str) -> str:
    """Hashes a password with Argon2id."""
    return ph.hash(password)

def verify_password(password_hash: str, password: str) -> bool:
    """Verifies a candidate password against an Argon2id hash."""
    try:
        return ph.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False

def extract_session_token(request: Request) -> str | None:
    """Extracts session token from Authorization header, X-Session-Token header, or HttpOnly cookie."""
    # 1. Bearer Token in Authorization header
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            return token

    # 2. X-Session-Token custom header
    session_header = request.headers.get("x-session-token", "").strip()
    if session_header:
        return session_header

    # 3. HttpOnly cookie
    cookie_token = request.cookies.get("faircart_session", "").strip()
    if cookie_token:
        return cookie_token

    return None

def get_current_user_optional(request: Request) -> dict | None:
    """Dependency that returns the authenticated user dictionary if a valid session exists, or None."""
    token = extract_session_token(request)
    if not token:
        return None

    repo = CatalogRepository()
    session = repo.get_session(token)
    return session

def get_current_user_required(
    current_user: dict | None = Depends(get_current_user_optional),
) -> dict:
    """Dependency that enforces active authentication, raising HTTP 401 if unauthenticated."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access this resource.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user

def create_user_session(user_id: str, days: int = 7) -> tuple[str, str]:
    """Generates a cryptographically random session token and persists it to SQLite."""
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    repo = CatalogRepository()
    repo.create_session(token, user_id, expires_at)
    return token, expires_at

def attach_session_cookie(response: Response, session_token: str, max_age_days: int = 7) -> None:
    """Attaches a secure HttpOnly session cookie to an HTTP response."""
    # Note: secure=False in local development, secure=True in production HTTPS
    is_prod = settings.ENVIRONMENT.lower() == "production"
    response.set_cookie(
        key="faircart_session",
        value=session_token,
        max_age=max_age_days * 86400,
        httponly=True,
        samesite="lax",
        secure=is_prod,
        path="/",
    )

def clear_session_cookie(response: Response) -> None:
    """Clears the session cookie."""
    response.delete_cookie(
        key="faircart_session",
        httponly=True,
        samesite="lax",
        path="/",
    )
