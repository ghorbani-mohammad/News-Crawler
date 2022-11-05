import os
import environ
from django.http.request import HttpRequest

env = environ.Env()

ALLOWED_HOSTS = ["*"]
DEBUG = env.bool("DEBUG")
SECRET_KEY = env.str("SECRET_KEY")
DATABASES = {
    "default": {
        "HOST": "postgres",
        "NAME": "postgres",
        "USER": env.str("DB_USER"),
        "PORT": env.str("DB_PORT"),
        "PASSWORD": env.str("DB_PASS"),
        "ENGINE": "django.db.backends.postgresql",
        "OPTIONS": {"options": "-c search_path=army"},
    },
}
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rangefilter",
    "rest_framework",
    # Our apps
    "agency",
    "notification",
    "clear_cache",
    "prettyjson",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "crawler.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "crawler.wsgi.application"


# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

USE_TZ = False
USE_I18N = True
USE_L10N = True
TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.0/howto/static-files/

STATIC_URL = "/static/"


REST_FRAMEWORK = {
    # When you enable API versioning, the request.version attribute will contain a string
    # that corresponds to the version requested in the incoming client request.
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
}

# Celery
BROKER_URL = "redis://news_crawler_redis:6379/10"
CELERY_RESULT_BACKEND = "redis://news_crawler_redis:6379/10"
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Tehran"


# monkey patch to get rid of message below in docker
# for bellow error (it happens because we have _ in container name)
# 'news_crawler_api:80'. The domain name provided is not valid according to RFC 1034/1035.
HttpRequest.get_host = HttpRequest._get_raw_host
