from .base import *  # noqa: F401,F403

DEBUG = False

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT', default='3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

STORAGES = {
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
}

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# ── HTTPS / Reverse Proxy (IIS) ──────────────────────────────────
# IIS จัดการ SSL termination และส่ง X-Forwarded-Proto: https มาให้
# Django อ่าน header นี้เพื่อรู้ว่า request มาจาจาก HTTPS จริง
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST    = False

# IIS จัดการ HTTP→HTTPS redirect แล้ว ไม่ต้องให้ Django redirect ซ้ำ
SECURE_SSL_REDIRECT = False

_ssl = env.bool('HTTPS_ENABLED', default=True)
SESSION_COOKIE_SECURE          = _ssl
CSRF_COOKIE_SECURE             = _ssl
SECURE_HSTS_SECONDS            = 31536000 if _ssl else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = _ssl
SECURE_HSTS_PRELOAD            = _ssl

# CSRF: อนุญาต domain หลัก (ต้องมี https:// นำหน้า)
_csrf_origins = env.list('CSRF_TRUSTED_ORIGINS', default=[])
if _csrf_origins:
    CSRF_TRUSTED_ORIGINS = _csrf_origins

# ── Path-based routing (IIS strips prefix, Django adds it back) ───
# เมื่อ deploy ที่ lib.npu.ac.th/projects/
# IIS จะตัด /projects ออกก่อนส่งให้ Waitress
# FORCE_SCRIPT_NAME บอก Django ให้สร้าง URL กลับโดยใส่ /projects นำหน้า
_script_name = env('SCRIPT_NAME', default='')
if _script_name:
    FORCE_SCRIPT_NAME = _script_name
    LOGIN_URL = f'{_script_name}/accounts/login/'
