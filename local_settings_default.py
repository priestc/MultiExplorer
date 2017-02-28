# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'my_cache_table',
        'TIMEOUT': 500000,
    }
}

# Database
# https://docs.djangoproject.com/en/1.8/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

WALLET_SUPPORTED_CRYPTOS = []
WALLET_SUPPORTED_FIATS = ['usd', 'eur', 'cny', 'jpy']

EXCHANGE_KICK_INTERVAL_MINUTES = 10
EXCHANGE_FEE_PERCENTAGE = 1.5

MAX_MEMO_SIZE_BYTES = 1000
MEMO_SERVER_PRIVATE_MODE = False
MEMO_SERVER_PULL = [
    'https://multiexplorer.com/memo/pull'
]
MEMO_SERVER_PUSH = [
    'https://multiexplorer.com/memo'
]
DEBUG = False
LOGIN_TRIES = 5
ALLOWED_HOSTS = []

PRICE_INTERVAL_SECONDS = 500
QUANDL_APIKEY = None
