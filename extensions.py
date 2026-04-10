from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
import sys

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()

async_mode = None
if sys.platform == 'win32':
    async_mode = 'threading'
socketio = SocketIO(cors_allowed_origins="*", async_mode=async_mode)