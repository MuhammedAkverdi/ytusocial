import os

class Config:
    SECRET_KEY = 'yildiz-teknik-gizli-anahtar'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///users.db'
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
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