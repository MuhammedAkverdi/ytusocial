from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message as MailMessage
from extensions import db, mail
from models import User
import random
from flask import current_app
from urllib.parse import urlparse

auth = Blueprint('auth', __name__)


def _safe_next_url(target):
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return None
    if not target.startswith('/'):
        return None
    return target

@auth.route('/register', methods=['GET', 'POST'])
def register():
    next_url = request.args.get('next') or request.form.get('next')
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        accept_terms = request.form.get('accept_terms')
        accept_privacy = request.form.get('accept_privacy')
        
        if not accept_terms or not accept_privacy:
            flash("Hizmet Şartları ve Gizlilik Politikası'nı kabul etmelisin!", "danger")
            return render_template('register.html')
        
        if not email.endswith('@std.yildiz.edu.tr'):
            flash("Sadece @std.yildiz.edu.tr uzantılı YTÜ maili kabul edilir!", "danger")
            return render_template('register.html')
        
        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash("Bu mail adresiyle daha önce kayıt olunmuş!", "danger")
            return render_template('register.html')

        base_handle = email.split('@')[0]
        handle = base_handle
        while User.query.filter_by(handle=handle).first():
            handle = base_handle + str(random.randint(1, 999))

        otp = str(random.randint(100000, 999999))
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        
        new_user = User(email=email, password=hashed_pw, otp_code=otp, handle=handle)
        try:
            db.session.add(new_user)
            db.session.commit()
            msg = MailMessage('YTÜ Portal Doğrulama', sender=current_app.config['MAIL_USERNAME'], recipients=[email])
            msg.body = f'Portalımıza hoş geldin! Doğrulama kodun: {otp}'
            mail.send(msg)
            verify_target = url_for('auth.verify', email=email)
            safe_next = _safe_next_url(next_url)
            if safe_next:
                verify_target = url_for('auth.verify', email=email, next=safe_next)
            return redirect(verify_target)
        except Exception as e:
            db.session.rollback()
            print(f"Kayıt Hatası: {e}")
            flash("Mail gönderilirken bir teknik sorun oluştu!", "danger")
            return render_template('register.html', next_url=next_url)
    return render_template('register.html', next_url=next_url)

@auth.route('/verify/<email>', methods=['GET', 'POST'])
def verify(email):
    next_url = request.args.get('next') or request.form.get('next')
    if request.method == 'POST':
        girilen_kod = request.form.get('kod')
        user = User.query.filter_by(email=email).first()
        if user and user.otp_code == girilen_kod:
            user.is_verified = True
            user.otp_code = None
            db.session.commit()
            login_user(user)
            flash("Kod onaylandı! YTU Social'a hoş geldin.", "success")
            safe_next = _safe_next_url(next_url)
            if safe_next:
                return redirect(safe_next)
            return redirect(url_for('main.index'))
        else:
            flash("Hata: Girdiğin kod hatalı, lütfen tekrar dene!", "danger")
            return render_template('verify.html', email=email, next_url=next_url)
    return render_template('verify.html', email=email, next_url=next_url)

@auth.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            otp = str(random.randint(100000, 999999))
            user.otp_code = otp
            db.session.commit()
            try:
                msg = MailMessage('YTÜ Portal Şifre Sıfırlama', sender=current_app.config['MAIL_USERNAME'], recipients=[email])
                msg.body = f'Şifre sıfırlama kodun: {otp}'
                mail.send(msg)
                flash("Sıfırlama kodu e-posta adresine gönderildi.", "info")
                return redirect(url_for('auth.reset_password', email=email))
            except Exception as e:
                print(f"Mail Hatası: {e}")
                flash("Mail gönderilirken bir hata oluştu.", "danger")
        else:
            flash("Bu e-posta adresi sistemde kayıtlı değil.", "danger")
    return render_template('forgot_password.html')

@auth.route('/reset_password/<email>', methods=['GET', 'POST'])
def reset_password(email):
    if request.method == 'POST':
        kod = request.form.get('kod')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and user.otp_code == kod:
            user.password = generate_password_hash(password, method='pbkdf2:sha256')
            user.otp_code = None
            db.session.commit()
            flash("Şifreniz başarıyla güncellendi. Giriş yapabilirsiniz.", "success")
            return redirect(url_for('auth.login'))
        else:
            flash("Geçersiz doğrulama kodu!", "danger")
    return render_template('reset_password.html', email=email)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next') or request.form.get('next')
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            safe_next = _safe_next_url(next_url)
            if safe_next:
                return redirect(safe_next)
            return redirect(url_for('main.index'))
        else:
            flash("Giriş başarısız! Lütfen bilgilerinizi kontrol edin.", "danger")
            return render_template('login.html', next_url=next_url)
    return render_template('login.html', next_url=next_url)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))