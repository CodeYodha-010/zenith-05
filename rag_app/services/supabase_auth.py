"""Supabase JWT authentication for Django API views.

The frontend authenticates with Supabase Auth and sends its access token as a
Bearer token. This module verifies the token against Supabase's public JWKS
endpoint; it never requires a Supabase service-role key or database password.
"""
from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Callable

import jwt
from django.conf import settings
from django.http import JsonResponse

logger = logging.getLogger(__name__)

_jwks_client: jwt.PyJWKClient | None = None


class SupabasePrincipal:
    """Small request.user-compatible principal backed by Supabase claims."""

    is_authenticated = True
    is_anonymous = False

    def __init__(self, claims: dict[str, Any]):
        self.claims = claims
        self.id = claims.get("sub", "")
        self.email = claims.get("email", "")
        self.username = self.email or self.id
        metadata = claims.get("app_metadata") or {}
        self.is_staff = bool(metadata.get("is_staff", False))


def _unauthorized(message: str = "Authentication required. Please sign in."):
    return JsonResponse({"success": False, "error": message}, status=401)


def _forbidden(message: str = "Staff permission required."):
    return JsonResponse({"success": False, "error": message}, status=403)


def _get_jwks_client() -> jwt.PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        if not settings.SUPABASE_URL:
            raise RuntimeError("SUPABASE_URL is not configured")
        jwks_url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        _jwks_client = jwt.PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


def verify_supabase_token(request) -> SupabasePrincipal | None:
    """Return a verified principal, or None for missing/invalid tokens."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None

    token = header[7:].strip()
    if not token or not settings.SUPABASE_URL:
        return None

    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.SUPABASE_JWT_AUDIENCE,
            issuer=f"{settings.SUPABASE_URL}/auth/v1",
            options={"require": ["exp", "iat", "sub"]},
        )
    except (jwt.PyJWTError, ValueError, RuntimeError) as exc:
        logger.warning("Supabase token rejected: %s", exc)
        return None

    if claims.get("role") != "authenticated":
        return None

    principal = SupabasePrincipal(claims)
    request.supabase_user = claims
    # AuthenticationMiddleware normally installs AnonymousUser here. Replace
    # it for the duration of this request so existing throttle/decorators work.
    request.user = principal
    return principal


def require_supabase_user(view: Callable):
    """Protect sync or async views with a verified Supabase bearer token."""
    if getattr(view, "_supabase_protected", False):
        return view

    import inspect

    if inspect.iscoroutinefunction(view):
        @wraps(view)
        async def async_wrapper(request, *args, **kwargs):
            if verify_supabase_token(request) is None:
                return _unauthorized()
            return await view(request, *args, **kwargs)
        async_wrapper._supabase_protected = True
        return async_wrapper
    else:
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if verify_supabase_token(request) is None:
                return _unauthorized()
            return view(request, *args, **kwargs)
        wrapper._supabase_protected = True
        return wrapper


def require_supabase_staff(view: Callable):
    """Protect staff-only sync or async views with a Supabase principal."""
    parent = require_supabase_user(view)

    import inspect

    if inspect.iscoroutinefunction(parent):
        @wraps(parent)
        async def async_wrapper(request, *args, **kwargs):
            if verify_supabase_token(request) is None:
                return _unauthorized()
            if not request.user.is_staff:
                return _forbidden()
            return await parent(request, *args, **kwargs)
    else:
        @wraps(parent)
        def wrapper(request, *args, **kwargs):
            if verify_supabase_token(request) is None:
                return _unauthorized()
            if not request.user.is_staff:
                return _forbidden()
            return parent(request, *args, **kwargs)

    return wrapper
