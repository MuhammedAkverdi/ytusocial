import os
from urllib.parse import urlparse


def _load_important_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'important.env')
    if not os.path.exists(env_path):
        return

    with open(env_path, 'r', encoding='utf-8') as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


_load_important_env()


def _resolve_database_uri():
    raw_url = (os.environ.get('DATABASE_URL') or '').strip()
    local_url = (os.environ.get('LOCAL_DATABASE_URL') or '').strip()

    if not raw_url:
        if local_url:
            return _normalize_sqlite_uri(local_url)
        raise RuntimeError('DATABASE_URL is not set. Provide a valid remote database URL or LOCAL_DATABASE_URL for local development.')

    if raw_url.startswith('postgres://'):
        raw_url = raw_url.replace('postgres://', 'postgresql://', 1)

    if raw_url.startswith('postgresql://'):
        parsed = urlparse(raw_url)
        host = (parsed.hostname or '').strip()
        if not host or '...' in host or '...' in raw_url:
            if local_url:
                return _normalize_sqlite_uri(local_url)
            raise RuntimeError('DATABASE_URL looks truncated or invalid. Set a real remote database URL or LOCAL_DATABASE_URL for local development.')

    return raw_url


def _normalize_sqlite_uri(uri):
    if not uri.startswith('sqlite:///'):
        return uri

    sqlite_path = uri.replace('sqlite:///', '', 1)
    if ':' in sqlite_path[:3] or sqlite_path.startswith('/'):
        return uri

    absolute_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), sqlite_path))
    absolute_path = absolute_path.replace('\\', '/')
    return 'sqlite:///' + absolute_path

class Config:
    SECRET_KEY = 'yildiz-teknik-gizli-anahtar'
    SQLALCHEMY_DATABASE_URI = _resolve_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024 
    WTF_CSRF_CHECK_DEFAULT = False

    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'portalytu@gmail.com' 
    MAIL_PASSWORD = 'xpfj soms rwht ttam' 

    UPLOAD_FOLDER_NOTES = 'static/note_files'
    AUDIO_UPLOAD_FOLDER = os.path.join('static', 'audio_files')
    POST_UPLOAD_FOLDER = 'static/post_images'
    PROFILE_UPLOAD_FOLDER = 'static/uploads/profiles'
    STORY_UPLOAD_FOLDER = 'static/story_images'
    MESSAGE_FILE_UPLOAD_FOLDER = os.path.join('static', 'message_files')