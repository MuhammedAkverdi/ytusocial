from datetime import datetime, timedelta
import random
from urllib.parse import urlparse
from threading import Thread

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_mail import Message as MailMessage
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, mail
from models import User

auth = Blueprint('auth', __name__)

OTP_VALIDITY_SECONDS = 90


def _safe_next_url(target):
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return None
    if not target.startswith('/'):
        return None
    return target


def _normalize_email(raw_email):
    return (raw_email or '').strip().lower()


def _now():
    return datetime.utcnow()


def _issue_otp(user):
    otp = str(random.randint(100000, 999999))
    user.otp_code = otp
    user.otp_expires_at = _now() + timedelta(seconds=OTP_VALIDITY_SECONDS)
    return otp


def _otp_is_active(user):
    return bool(user and user.otp_code and user.otp_expires_at and user.otp_expires_at > _now())


def _queue_otp_email(subject, email, intro_text, otp):
    app = current_app._get_current_object()

    def _worker():
        with app.app_context():
            try:
                msg = MailMessage(subject, sender=app.config['MAIL_USERNAME'], recipients=[email])
                msg.body = f'{intro_text}\n\nKodun: {otp}\nBu kod {OTP_VALIDITY_SECONDS} saniye geçerlidir.'
                with mail.connect() as connection:
                    connection.send(msg)
            except Exception as exc:
                print(f"Mail gönderim hatası ({email}): {exc}")

    Thread(target=_worker, daemon=False).start()


def _verify_redirect(email, next_url=None):
    safe_next = _safe_next_url(next_url)
    if safe_next:
        return redirect(url_for('auth.verify', email=email, next=safe_next))
    return redirect(url_for('auth.verify', email=email))


def _render_register(next_url=None):
    return render_template('register.html', next_url=next_url)


def _render_login(next_url=None):
    return render_template('login.html', next_url=next_url)


def _render_verify(email, next_url=None):
    return render_template('verify.html', email=email, next_url=next_url)


@auth.route('/register', methods=['GET', 'POST'])
def register():
    next_url = _safe_next_url(request.args.get('next') or request.form.get('next'))

    if request.method == 'POST':
        email = _normalize_email(request.form.get('email'))
        password = request.form.get('password') or ''
        accept_terms = request.form.get('accept_terms')
        accept_privacy = request.form.get('accept_privacy')

        if not accept_terms or not accept_privacy:
            flash("Hizmet Şartları ve Gizlilik Politikası'nı kabul etmelisin!", "danger")
            return _render_register(next_url)

        if not email.endswith('@std.yildiz.edu.tr'):
            flash("Sadece @std.yildiz.edu.tr uzantılı YTÜ maili kabul edilir!", "danger")
            return _render_register(next_url)

        if not password:
            flash("Şifre boş olamaz!", "danger")
            return _render_register(next_url)

        user = User.query.filter_by(email=email).first()
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')

        if user:
            if user.is_verified:
                flash("Bu mail adresiyle zaten kayıtlı bir hesap var. Giriş yapabilirsin.", "danger")
                return _render_register(next_url)

            user.password = hashed_pw

            if _otp_is_active(user):
                try:
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    print(f"Kayıt Hatası: {e}")
                    flash("Kayıt güncellenirken bir teknik sorun oluştu!", "danger")
                    return _render_register(next_url)

                flash("Doğrulama kodun zaten aktif. Aynı kodu kullanabilirsin.", "info")
                return _verify_redirect(email, next_url)

            otp = _issue_otp(user)
            try:
                db.session.commit()
                _queue_otp_email(
                    'YTÜ Portal Doğrulama',
                    email,
                    'Portalımıza hoş geldin! Doğrulama kodun aşağıda.',
                    otp,
                )
            except Exception as e:
                db.session.rollback()
                print(f"Kayıt Hatası: {e}")
                flash("Mail gönderilirken bir teknik sorun oluştu!", "danger")
                return _render_register(next_url)

            flash("Doğrulama kodu gönderiliyor. Birkaç saniye içinde mailinde olmalı.", "success")
            return _verify_redirect(email, next_url)

        base_handle = email.split('@')[0]
        handle = base_handle
        while User.query.filter_by(handle=handle).first():
            handle = base_handle + str(random.randint(1, 999))

        otp = str(random.randint(100000, 999999))
        new_user = User(
            email=email,
            password=hashed_pw,
            otp_code=otp,
            otp_expires_at=_now() + timedelta(seconds=OTP_VALIDITY_SECONDS),
            handle=handle,
        )

        try:
            db.session.add(new_user)
            db.session.commit()
            _queue_otp_email(
                'YTÜ Portal Doğrulama',
                email,
                'Portalımıza hoş geldin! Doğrulama kodun aşağıda.',
                otp,
            )
        except Exception as e:
            db.session.rollback()
            print(f"Kayıt Hatası: {e}")
            flash("Mail gönderilirken bir teknik sorun oluştu!", "danger")
            return _render_register(next_url)

        flash("Doğrulama kodu gönderiliyor. Birkaç saniye içinde mailinde olmalı.", "success")
        return _verify_redirect(email, next_url)

    return _render_register(next_url)


@auth.route('/verify/<email>', methods=['GET', 'POST'])
def verify(email):
    email = _normalize_email(email)
    next_url = _safe_next_url(request.args.get('next') or request.form.get('next'))
    user = User.query.filter_by(email=email).first()

    if not user:
        flash("Bu e-posta ile eşleşen bir hesap bulunamadı.", "danger")
        return redirect(url_for('auth.register', next=next_url) if next_url else url_for('auth.register'))

    if user.is_verified:
        flash("Hesabın zaten doğrulanmış.", "info")
        if current_user.is_authenticated and current_user.id == user.id:
            if next_url:
                return redirect(next_url)
            return redirect(url_for('main.index'))
        return redirect(url_for('auth.login', next=next_url) if next_url else url_for('auth.login'))

    if request.method == 'POST':
        girilen_kod = (request.form.get('kod') or '').strip()

        if not _otp_is_active(user):
            flash("Doğrulama kodunun süresi doldu. Lütfen tekrar giriş yapıp yeni kod iste.", "danger")
            return _render_verify(email, next_url)

        if user.otp_code == girilen_kod:
            user.is_verified = True
            user.otp_code = None
            user.otp_expires_at = None
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"Doğrulama Hatası: {e}")
                flash("Kod onaylanırken bir teknik sorun oluştu!", "danger")
                return _render_verify(email, next_url)
            login_user(user)
            flash("Kod onaylandı! YTU Social'a hoş geldin.", "success")
            if next_url:
                return redirect(next_url)
            return redirect(url_for('main.index'))

        flash("Hata: Girdiğin kod hatalı, lütfen tekrar dene!", "danger")
        return _render_verify(email, next_url)

    return _render_verify(email, next_url)


@auth.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = _normalize_email(request.form.get('email'))
        user = User.query.filter_by(email=email).first()
        if user:
            otp = _issue_otp(user)
            try:
                db.session.commit()
                _queue_otp_email(
                    'YTÜ Portal Şifre Sıfırlama',
                    email,
                    'Şifre sıfırlama kodun aşağıda.',
                    otp,
                )
                flash("Sıfırlama kodu e-posta adresine gönderildi.", "info")
                return redirect(url_for('auth.reset_password', email=email))
            except Exception as e:
                db.session.rollback()
                print(f"Mail Hatası: {e}")
                flash("Mail gönderilirken bir hata oluştu.", "danger")
        else:
            flash("Bu e-posta adresi sistemde kayıtlı değil.", "danger")
    return render_template('forgot_password.html')


@auth.route('/reset_password/<email>', methods=['GET', 'POST'])
def reset_password(email):
    email = _normalize_email(email)
    if request.method == 'POST':
        kod = (request.form.get('kod') or '').strip()
        password = request.form.get('password') or ''
        user = User.query.filter_by(email=email).first()

        if not password:
            flash("Şifre boş olamaz!", "danger")
        elif user and user.otp_code == kod and _otp_is_active(user):
            user.password = generate_password_hash(password, method='pbkdf2:sha256')
            user.otp_code = None
            user.otp_expires_at = None
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"Şifre Sıfırlama Hatası: {e}")
                flash("Şifre güncellenirken bir teknik sorun oluştu!", "danger")
                return render_template('reset_password.html', email=email)
            flash("Şifreniz başarıyla güncellendi. Giriş yapabilirsiniz.", "success")
            return redirect(url_for('auth.login'))
        elif user and user.otp_code == kod:
            flash("Kodun süresi doldu. Lütfen yeniden şifre sıfırlama iste.", "danger")
        else:
            flash("Geçersiz doğrulama kodu!", "danger")
    return render_template('reset_password.html', email=email)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    next_url = _safe_next_url(request.args.get('next') or request.form.get('next'))
    if request.method == 'POST':
        email = _normalize_email(request.form.get('email'))
        password = request.form.get('password') or ''
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            if not user.is_verified:
                if _otp_is_active(user):
                    flash("Hesabın henüz doğrulanmamış. Kod sayfasına yönlendiriliyorsun.", "info")
                    return _verify_redirect(email, next_url)

                otp = _issue_otp(user)
                try:
                    db.session.commit()
                    _queue_otp_email(
                        'YTÜ Portal Doğrulama',
                        email,
                        'Hesabını doğrulamak için yeni kodun aşağıda.',
                        otp,
                    )
                except Exception as e:
                    db.session.rollback()
                    print(f"Giriş Hatası: {e}")
                    flash("Yeni doğrulama kodu gönderilirken sorun oluştu.", "danger")
                    return _render_login(next_url)

                flash("Kodun süresi dolmuştu. Yeni kod gönderiliyor.", "success")
                return _verify_redirect(email, next_url)

            login_user(user)
            if next_url:
                return redirect(next_url)
            return redirect(url_for('main.index'))

        flash("Giriş başarısız! Lütfen bilgilerinizi kontrol edin.", "danger")
        return _render_login(next_url)

    return _render_login(next_url)


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))