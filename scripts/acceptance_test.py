"""
Zenith acceptance test harness (Phase 0 of the deployment plan).
Run against a live server:  python scripts/acceptance_test.py [BASE_URL]

Asserts the behaviour that must stay green through every hardening phase.
Exit code 0 = all good; 1 = regression (do not proceed to the next phase).
"""
import json
import sys
import time

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8000'
STAMP = str(int(time.time()))
USERNAME = f'acc_test_{STAMP}'
EMAIL = f'{USERNAME}@zenith-test.dev'
PASSWORD = 'Gold-Ink-2026!Test'

results = []


def check(name, ok, detail=''):
    results.append((name, ok))
    print(('PASS  ' if ok else 'FAIL  ') + name + (f'  [{detail}]' if detail else ''))


def csrf_token(session):
    session.get(f'{BASE}/api/auth/csrf/', timeout=10)
    return session.cookies.get('csrftoken')


def post_json(session, path, payload, expect_token=True):
    headers = {}
    tok = csrf_token(session) if expect_token else session.cookies.get('csrftoken')
    if tok:
        headers['X-CSRFToken'] = tok
    headers['Referer'] = BASE + '/'
    return session.post(f'{BASE}{path}', json=payload, headers=headers, timeout=30)


# ---- 1. anonymous access is gated --------------------------------------
r = requests.get(f'{BASE}/search/', params={'q': 'wheat'}, timeout=10)
check('anonymous /search/ is 401', r.status_code == 401, f'got {r.status_code}')

r = requests.get(f'{BASE}/api/auth/me/', timeout=10)
check('anonymous /me/ reports no user', r.status_code == 200 and r.json().get('user') is None)

# ---- 2. registration validation ----------------------------------------
s = requests.Session()
r = post_json(s, '/api/auth/register/', {'email': 'not-an-email', 'username': '', 'password': 'x'})
check('bad register payload is 400', r.status_code == 400, f'got {r.status_code}')

r = post_json(s, '/api/auth/register/', {'email': EMAIL, 'username': USERNAME, 'password': 'weak'})
check('weak password rejected', r.status_code == 400)

# ---- 3. happy-path register -> session works ----------------------------
s2 = requests.Session()
r = post_json(s2, '/api/auth/register/', {'email': EMAIL, 'username': USERNAME, 'password': PASSWORD})
check('register succeeds', r.status_code == 200, f'got {r.status_code}')

r = s2.get(f'{BASE}/api/auth/me/', timeout=10)
check('me/ returns the new user', r.json().get('user', {}).get('username') == USERNAME)

r = s2.get(f'{BASE}/search/', params={'q': 'wheat'}, timeout=30)
check('authed /search/ works', r.status_code == 200, f'got {r.status_code}')

# ---- 3b. Phase 1 security gates -----------------------------------------
r = s2.post(f'{BASE}/ask/stream/', json={'question': 'test'}, timeout=10)
check('ask/stream without CSRF token is 403', r.status_code == 403, f'got {r.status_code}')

r = s2.post(f'{BASE}/upload-document/', files={'file': ('x.pdf', b'x')}, timeout=10)
check('upload without CSRF token is 403', r.status_code == 403, f'got {r.status_code}')

r = post_json(s2, '/clear/', {})
check('/clear/ blocked for non-staff users', r.status_code == 403, f'got {r.status_code}')

r = post_json(s2, '/api/auth/register/', {'email': EMAIL, 'username': USERNAME, 'password': PASSWORD})
check('duplicate registration rejected', r.status_code == 400)

# ---- 4. login / logout cycle ---------------------------------------------
s3 = requests.Session()
r = post_json(s3, '/api/auth/login/', {'email': EMAIL, 'password': 'WrongPassword!1'})
check('wrong password rejected', r.status_code == 400)

r = post_json(s3, '/api/auth/login/', {'email': EMAIL, 'password': PASSWORD})
check('email login succeeds', r.status_code == 200)

r = post_json(s3, '/api/auth/logout/', {})
check('logout succeeds', r.status_code == 200)

r = s3.get(f'{BASE}/api/auth/me/', timeout=10)
check('session cleared after logout', r.json().get('user') is None)

r = s3.get(f'{BASE}/search/', params={'q': 'wheat'}, timeout=10)
check('/search/ re-locked after logout', r.status_code == 401)

# ---- 5. chat page serves ------------------------------------------------
r = s2.get(f'{BASE}/', timeout=15)
check('chat page renders when authed', r.status_code == 200 and 'chat-messages' in r.text)

# ---- summary ------------------------------------------------------------
failed = [n for n, ok in results if not ok]
print('\n' + '=' * 60)
print(f'{len(results) - len(failed)}/{len(results)} checks passed')
if failed:
    print('FAILED: ' + ', '.join(failed))
    sys.exit(1)
print('ALL GREEN - safe to proceed')
