from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message as MailMessage
from extensions import db, mail
from models import User
import random
from flask import current_app

auth = Blueprint('auth', __name__)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
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
            return redirect(url_for('auth.verify', email=email))
        except Exception as e:
            db.session.rollback()
            print(f"Kayıt Hatası: {e}")
            flash("Mail gönderilirken bir teknik sorun oluştu!", "danger")
            return render_template('register.html')
    return render_template('register.html')

@auth.route('/verify/<email>', methods=['GET', 'POST'])
def verify(email):
    if request.method == 'POST':
        girilen_kod = request.form.get('kod')
        user = User.query.filter_by(email=email).first()
        if user and user.otp_code == girilen_kod:
            user.is_verified = True
            user.otp_code = None
            db.session.commit()
            login_user(user)
            flash("Kod onaylandı! YTU Social'a hoş geldin.", "success")
            return redirect(url_for('main.index'))
        else:
            flash("Hata: Girdiğin kod hatalı, lütfen tekrar dene!", "danger")
            return render_template('verify.html', email=email)
    return render_template('verify.html', email=email)

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
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('main.index'))
        else:
            flash("Giriş başarısız! Lütfen bilgilerinizi kontrol edin.", "danger")
            return render_template('login.html')
    return render_template('login.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))