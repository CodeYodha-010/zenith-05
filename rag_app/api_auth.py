"""
JSON authentication endpoints for the Zenith landing page (React).
Session-cookie based. These views are CSRF-protected on purpose —
the frontend sends the X-CSRFToken header obtained from /api/auth/csrf/.

Also exposes require_login_json: a decorator that gates any view
(sync or async) behind an authenticated session, returning a JSON 401.
"""
import json
import inspect
import logging
import time
from functools import wraps

from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

logger = logging.getLogger('rag_pipeline')


def throttle(rate, scope, by='ip'):
    """
    Fixed-window rate limiter backed by Django's default cache.

    rate : 'N/period' with period in ('min', 'hour')
    scope: distinct bucket namespace (e.g. 'login', 'register')
    by   : 'ip' (safe for anonymous views) or 'user' (requires an
           authentication decorator to run before this one)

    Returns 429 JSON when the window's allowance is exhausted.
    Safe for sync and async views (LocMem cache is an in-process dict).
    """
    count_s, period_s = rate.split('/')
    count = int(count_s)
    seconds = {'min': 60, 'hour': 3600}[period_s]

    def _window_key(request):
        if by == 'user' and getattr(request, 'user', None) and request.user.is_authenticated:
            ident = f'u{request.user.id}'
        else:
            ident = request.META.get('REMOTE_ADDR', 'unknown')
        return f'thr:{scope}:{ident}:{int(time.time() // seconds)}'

    def _allow(request):
        key = _window_key(request)
        if cache.get(key) is None:
            cache.add(key, 0, seconds)
        try:
            return cache.incr(key) <= count
        except ValueError:
            # key expired between get and incr (window edge) - treat as allowed
            return True

    def _denied():
        return JsonResponse(
            {'success': False, 'error': 'Too many requests. Please slow down and try again shortly.'},
            status=429,
        )

    def decorator(view):
        if inspect.iscoroutinefunction(view):
            @wraps(view)
            async def async_wrapper(request, *args, **kwargs):
                if not _allow(request):
                    return _denied()
                return await view(request, *args, **kwargs)
            return async_wrapper

        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not _allow(request):
                return _denied()
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


def require_login_json(view):
    """Gate a view behind authentication; JSON 401 for anonymous callers."""

    if inspect.iscoroutinefunction(view):
        @wraps(view)
        async def async_wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse(
                    {'success': False, 'error': 'Authentication required. Please sign in.'},
                    status=401,
                )
            return await view(request, *args, **kwargs)
        return async_wrapper

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {'success': False, 'error': 'Authentication required. Please sign in.'},
                status=401,
            )
        return view(request, *args, **kwargs)
    return wrapper


def require_staff_json(view):
    """Gate a destructive view behind staff status; JSON 403 for everyone else."""

    if inspect.iscoroutinefunction(view):
        @wraps(view)
        async def async_wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse(
                    {'success': False, 'error': 'Authentication required. Please sign in.'},
                    status=401,
                )
            if not request.user.is_staff:
                return JsonResponse(
                    {'success': False, 'error': 'Staff permission required.'},
                    status=403,
                )
            return await view(request, *args, **kwargs)
        return async_wrapper

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {'success': False, 'error': 'Authentication required. Please sign in.'},
                status=401,
            )
        if not request.user.is_staff:
            return JsonResponse(
                {'success': False, 'error': 'Staff permission required.'},
                status=403,
            )
        return view(request, *args, **kwargs)
    return wrapper


def _user_payload(user: User) -> dict:
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'date_joined': user.date_joined.isoformat() if user.date_joined else None,
    }


def _json_body(request) -> dict:
    try:
        return json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return {}


@ensure_csrf_cookie
@require_http_methods(['GET'])
def csrf(request):
    """Hand the client a csrftoken cookie."""
    return JsonResponse({'ok': True})


@throttle('10/hour', 'register')
@require_http_methods(['POST'])
def register(request):
    data = _json_body(request)
    email = (data.get('email') or '').strip().lower()
    username = (data.get('username') or (email.split('@')[0] if email else '')).strip()
    password = data.get('password') or ''

    errors = {}
    if not email or '@' not in email:
        errors['email'] = 'Enter a valid email address.'
    if not username:
        errors['username'] = 'Username is required.'
    elif len(username) > 150:
        errors['username'] = 'Username is too long.'
    # Deliberately generic: telling the caller which of username/email is
    # taken lets an attacker enumerate registered accounts.
    if username and User.objects.filter(username__iexact=username).exists():
        errors['account'] = 'Registration failed. An account with these details may already exist, or the details cannot be used.'
    if email and User.objects.filter(email__iexact=email).exists():
        errors['account'] = 'Registration failed. An account with these details may already exist, or the details cannot be used.'
    if not password:
        errors['password'] = 'Password is required.'
    else:
        try:
            validate_password(password)
        except ValidationError as exc:
            errors['password'] = ' '.join(exc.messages)

    if errors:
        return JsonResponse({'success': False, 'errors': errors}, status=400)

    user = User.objects.create_user(username=username, email=email, password=password)
    login(request, user)
    logger.info(f"New registration: {username}")
    return JsonResponse({'success': True, 'user': _user_payload(user)})


@throttle('10/min', 'login')
@require_http_methods(['POST'])
def login_view(request):
    data = _json_body(request)
    identifier = (data.get('email') or data.get('username') or '').strip()
    password = data.get('password') or ''

    if not identifier or not password:
        return JsonResponse(
            {'success': False, 'errors': {'detail': 'Email and password are required.'}},
            status=400,
        )

    user = authenticate(request, username=identifier, password=password)
    if user is None and '@' in identifier:
        try:
            match = User.objects.get(email__iexact=identifier)
            user = authenticate(request, username=match.username, password=password)
        except User.DoesNotExist:
            pass

    if user is None:
        return JsonResponse(
            {'success': False, 'errors': {'detail': 'Invalid email or password.'}},
            status=400,
        )

    login(request, user)
    return JsonResponse({'success': True, 'user': _user_payload(user)})


@require_http_methods(['POST'])
def logout_view(request):
    logout(request)
    return JsonResponse({'success': True})


@require_http_methods(['GET'])
def me(request):
    if not request.user.is_authenticated:
        return JsonResponse({'user': None})
    return JsonResponse({'user': _user_payload(request.user)})
