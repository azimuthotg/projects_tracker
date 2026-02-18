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

# ตั้งค่า HTTPS — ปิดได้สำหรับ internal HTTP (default: True)
_ssl = env.bool('HTTPS_ENABLED', default=True)
SECURE_SSL_REDIRECT = _ssl
SESSION_COOKIE_SECURE = _ssl
CSRF_COOKIE_SECURE = _ssl
SECURE_HSTS_SECONDS = 31536000 if _ssl else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = _ssl
SECURE_HSTS_PRELOAD = _ssl
