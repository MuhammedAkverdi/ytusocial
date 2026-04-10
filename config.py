import os
from urllib.parse import urlparse


def _env_bool(name, default):
    raw_value = (os.environ.get(name) or '').strip().lower()
    if not raw_value:
        return default
    return raw_value in {'1', 'true', 'yes', 'on'}


def _load_important_env():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for file_name in ('instance/important.local.env', 'important.local.env', 'important.env'):
        env_path = os.path.join(base_dir, file_name)
        if not os.path.exists(env_path):
            continue

        with open(env_path, 'r', encoding='utf-8') as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                if not key or not value:
                    continue
                existing_value = (os.environ.get(key) or '').strip()
                if not existing_value:
                    os.environ[key] = value


_load_important_env()


def _resolve_database_uri():
    raw_url = (os.environ.get('DATABASE_URL') or '').strip()

    if not raw_url:
        raise RuntimeError('DATABASE_URL is not set. This app now requires a single live PostgreSQL database.')

    if raw_url.startswith('postgres://'):
        raw_url = raw_url.replace('postgres://', 'postgresql://', 1)

    if raw_url.startswith('postgresql://'):
        parsed = urlparse(raw_url)
        host = (parsed.hostname or '').strip()
        if not host or '...' in host or '...' in raw_url:
            raise RuntimeError('DATABASE_URL looks truncated or invalid. Set a real PostgreSQL connection string.')

    return raw_url

class Config:
    SECRET_KEY = 'yildiz-teknik-gizli-anahtar'
    SQLALCHEMY_DATABASE_URI = _resolve_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024 
    WTF_CSRF_CHECK_DEFAULT = False

    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'portalytu@gmail.com')
    SENDGRID_SANDBOX_MODE = _env_bool('SENDGRID_SANDBOX_MODE', False)

    UPLOAD_FOLDER_NOTES = 'static/note_files'
    AUDIO_UPLOAD_FOLDER = os.path.join('static', 'audio_files')
    POST_UPLOAD_FOLDER = 'static/post_images'
    PROFILE_UPLOAD_FOLDER = 'static/uploads/profiles'
    STORY_UPLOAD_FOLDER = 'static/story_images'
    MESSAGE_FILE_UPLOAD_FOLDER = os.path.join('static', 'message_files')