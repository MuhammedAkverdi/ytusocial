from flask import Flask, g, redirect, url_for, flash, request
import os
import logging
from logging.handlers import RotatingFileHandler
from flask_login import current_user, logout_user
from sqlalchemy.exc import SQLAlchemyError
from extensions import db, login_manager, socketio, csrf, migrate
from config import Config
from models import User, Message, Notification
from routes.auth import auth as auth_blueprint
from routes.main import main as main_blueprint
from routes.api import api as api_blueprint
from routes.admin import admin as admin_blueprint
import importlib
import time
from datetime import datetime
from utils import get_trending_hashtags, ONLINE_USERS, club_logo_src
from markupsafe import Markup
import re
from sqlalchemy import func

importlib.import_module('events')


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    log_candidates = [
        os.path.join(app.root_path, 'security.log'),
        os.path.join(app.instance_path, 'logs', 'security.log'),
    ]
    for log_file in log_candidates:
        if any(getattr(handler, 'baseFilename', None) == log_file for handler in app.logger.handlers):
            continue
        try:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            file_handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024, backupCount=3, encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
            app.logger.addHandler(file_handler)
            break
        except OSError:
            continue
    app.logger.setLevel(logging.INFO)
    app.logger.propagate = False
    app.logger.info(
        'App started. SendGrid loaded=%s sender=%s',
        bool(app.config.get('SENDGRID_API_KEY')),
        app.config.get('SENDGRID_FROM_EMAIL') or '',
    )

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
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
        trending = []
        suggested = []
        try:
            trending = get_trending_hashtags()
        except Exception as exc:
            app.logger.warning('Trending hashtags unavailable: %s', exc, exc_info=True)

        if getattr(current_user, 'is_authenticated', False):
            try:
                followed_ids = [u.id for u in getattr(current_user, 'followed', [])]
                user_id = getattr(current_user, 'id', None)
                if user_id is not None:
                    followed_ids.append(user_id)
                suggested = User.query.filter(~User.id.in_(followed_ids)).order_by(func.random()).limit(5).all()
            except Exception as exc:
                app.logger.warning('Suggested users unavailable: %s', exc, exc_info=True)
        return dict(trending_tags=trending, suggested_users=suggested, club_logo_src=club_logo_src)

    @app.context_processor
    def inject_notifications():
        if getattr(current_user, 'is_authenticated', False):
            try:
                user_id = getattr(current_user, 'id', None)
                if user_id is None:
                    raise AttributeError('current_user.id is unavailable')
                notif_count = Notification.query.filter_by(user_id=user_id, is_read=False).count()
                msg_count = Message.query.filter_by(recipient_id=user_id, is_read=False).count()
                return dict(unread_count=notif_count, unread_msg_count=msg_count, online_users=list(ONLINE_USERS))
            except Exception as exc:
                app.logger.warning('Notification counters unavailable: %s', exc, exc_info=True)
                return dict(unread_count=0, unread_msg_count=0, online_users=[])
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
    def fill_missing_username():
        try:
            if getattr(current_user, 'is_authenticated', False):
                current_username = (getattr(current_user, 'username', '') or '').strip()
                if not current_username or current_username.lower() in {'none', 'null'}:
                    fallback_name = getattr(current_user, 'display_name', '')
                    if fallback_name:
                        current_user.username = fallback_name
                        db.session.commit()
        except SQLAlchemyError as exc:
            db.session.rollback()
            app.logger.warning('Missing username fallback skipped because database is unavailable: %s', exc, exc_info=True)
        except Exception as exc:
            app.logger.warning('Missing username fallback failed: %s', exc, exc_info=True)

    @app.before_request
    def check_ban():
        try:
            if getattr(current_user, 'is_authenticated', False):
                is_banned = getattr(current_user, 'is_banned', False)
                ban_expiration = getattr(current_user, 'ban_expiration', None)
                if is_banned or (ban_expiration and ban_expiration > datetime.now()):
                    if request.endpoint not in ['auth.logout', 'static', 'auth.login']:
                        logout_user()
                        flash("🚫 Hesabınız yasaklandı veya uzaklaştırıldı.", "danger")
                        return redirect(url_for('auth.login'))
        except SQLAlchemyError as exc:
            app.logger.warning('Ban check skipped because database is unavailable: %s', exc, exc_info=True)
            return None

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
        # db.create_all() # Dikkat: Canlıdayken her seferinde db sıfırlanmasın diye yorum satırı yaptım, istersen açabilirsin.
    debug_flag = os.environ.get('FLASK_DEBUG', '0') == '1' # Canlıda debug kapalı olması daha iyi
    socketio.run(app, host='0.0.0.0', port=5002, debug=debug_flag)