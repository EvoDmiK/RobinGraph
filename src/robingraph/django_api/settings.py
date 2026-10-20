"""Stateless Django API settings; existing ingest SQL retains schema ownership.

Auth/admin/session tables are deliberately not installed during the API migration.
Enabling them later requires an explicit database and migration ownership decision.
"""
import os
import secrets

SECRET_KEY = os.environ.get('ROBINGRAPH_DJANGO_SECRET_KEY') or secrets.token_urlsafe(48)
DEBUG = False
ALLOWED_HOSTS = [value.strip() for value in os.environ.get(
    'ROBINGRAPH_DJANGO_ALLOWED_HOSTS',
    'localhost,127.0.0.1,[::1],testserver,robingraph-test.dove-nest.com,robingraph.dove-nest.com,192.168.219.97',
).split(',') if value.strip()]
ROOT_URLCONF = 'robingraph.api.drf.urls'
INSTALLED_APPS = ['rest_framework']
MIDDLEWARE = []
DATABASES = {}
USE_TZ = True
TIME_ZONE = 'Asia/Seoul'
APPEND_SLASH = False
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.AllowAny'],
    'UNAUTHENTICATED_USER': None,
    'UNAUTHENTICATED_TOKEN': None,
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser'],
}

# Preserve the existing ingest batch contract (up to 500 bounded records).
# Django's default 2.5 MiB body cap rejects valid batches before DTO validation.
DATA_UPLOAD_MAX_MEMORY_SIZE = None
