from flask import Flask, g, redirect, url_for, flash, request
import os
from flask_login import current_user, logout_user
from extensions import db, login_manager, mail, socketio, csrf, migrate
from config import Config
from models import User, Message, Notification
from routes.auth import auth as auth_blueprint
from routes.main import main as main_blueprint
from routes.api import api as api_blueprint
from routes.admin import admin as admin_blueprint
import importlib
import time
from datetime import datetime
from utils import get_trending_hashtags, ONLINE_USERS
from markupsafe import Markup
import re
from sqlalchemy import func

importlib.import_module('events')

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    socketio.init_app(app)
    csrf.init_app(app)

    # Configure Login Manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Bu sayfaya erişmek için lütfen önce giriş yapın."
    login_manager.login_message_category = "info"

    # Register blueprints
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(main_blueprint)
    app.register_blueprint(api_blueprint)
    app.register_blueprint(admin_blueprint)

    # Context processors and filters
    @app.context_processor
    def inject_global_data():
        trending = get_trending_hashtags()
        suggested = []
        if current_user.is_authenticated:
            followed_ids = [u.id for u in current_user.followed]
            followed_ids.append(current_user.id)
            suggested = User.query.filter(~User.id.in_(followed_ids)).order_by(func.random()).limit(5).all()
        return dict(trending_tags=trending, suggested_users=suggested)

    @app.context_processor
    def inject_notifications():
        if current_user.is_authenticated:
            notif_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
            msg_count = Message.query.filter_by(recipient_id=current_user.id, is_read=False).count()
            return dict(unread_count=notif_count, unread_msg_count=msg_count, online_users=list(ONLINE_USERS))
        return dict(unread_count=0, unread_msg_count=0, online_users=[])

    @app.template_filter('format_tags')
    def format_tags(text):
        if not text:
            return ""
        text = re.sub(r'(https?://\S+)', r'<a href="\1" target="_blank" style="color: var(--ytu-lacivert); text-decoration: underline;">\1</a>', text)
        tags = re.sub(r"#(\w+)", r'<a href="/explore?q=%23\1" class="hashtag-link">#\1</a>', text)
        tags = re.sub(r"@([\w\u00C0-\u024F-]+(?:\.[\w\u00C0-\u024F-]+)*)", r'<a href="/u/\1" class="mention-link">@\1</a>', tags)
        return Markup(tags)

    @app.before_request
    def check_ban():
        if current_user.is_authenticated:
            if current_user.is_banned or (current_user.ban_expiration and current_user.ban_expiration > datetime.now()):
                if request.endpoint not in ['auth.logout', 'static', 'auth.login']:
                    logout_user()
                    flash("🚫 Hesabınız yasaklandı veya uzaklaştırıldı.", "danger")
                    return redirect(url_for('auth.login'))

    @app.before_request
    def start_timer():
        g.start = time.time()

    @app.after_request
    def log_response(response):
        if hasattr(g, 'start'):
            now = time.time()
            duration = round(now - g.start, 4)
            print(f"--- Sayfa Yükleme: {duration}s ---")
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    return app

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        os.makedirs(app.instance_path, exist_ok=True)
        db.drop_all() # Önce eski/hatalı her şeyi sil
        db.create_all()
    debug_flag = os.environ.get('FLASK_DEBUG', '1') == '1'
    socketio.run(app, host='0.0.0.0', port=5002, debug=debug_flag)