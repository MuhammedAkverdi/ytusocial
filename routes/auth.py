from datetime import datetime, timedelta
import html
import random
from email.utils import parseaddr
from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import User

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Content, Email, Mail, To
    _SENDGRID_SDK_AVAILABLE = True
except ImportError:
    SendGridAPIClient = None
    Content = Email = Mail = To = None
    _SENDGRID_SDK_AVAILABLE = False

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


def _render_verify(email, next_url=None):
    return render_template('verify.html', email=email, next_url=next_url)


def _sendgrid_api_key():
    return (current_app.config.get('SENDGRID_API_KEY') or '').strip()


def _sendgrid_sender_details():
    raw_sender = (current_app.config.get('MAIL_DEFAULT_SENDER') or '').strip()
    if not raw_sender:
        raise RuntimeError('MAIL_DEFAULT_SENDER is not configured.')

    sender_name, sender_email = parseaddr(raw_sender)
    sender_email = (sender_email or raw_sender).strip()
    sender_name = (sender_name or '').strip() or 'YTU Social'
    if not sender_email:
        raise RuntimeError('MAIL_DEFAULT_SENDER is not configured.')
    return sender_email, sender_name


def _build_otp_email_payload(subject, intro_text, otp):
    text_body = f'{intro_text}\n\nKodun: {otp}\nBu kod {OTP_VALIDITY_SECONDS} saniye geçerlidir.'
    escaped_subject = html.escape(subject)
    escaped_intro = html.escape(intro_text)
    html_body = f'''<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="margin:0;padding:0;background:#eef4fb;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#eef4fb;padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;background:#ffffff;border-radius:24px;overflow:hidden;box-shadow:0 18px 50px rgba(15,45,82,.12);">
          <tr>
            <td style="padding:32px 40px;background:linear-gradient(135deg,#0f2d52,#1d4f91);color:#fff;">
              <div style="font-size:12px;letter-spacing:.14em;text-transform:uppercase;opacity:.75;">YTU Social</div>
              <div style="margin-top:10px;font-size:30px;line-height:1.2;font-weight:700;">{escaped_subject}</div>
              <div style="margin-top:14px;font-size:15px;line-height:1.7;opacity:.94;">{escaped_intro}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:40px;">
              <div style="font-size:15px;line-height:1.8;color:#29415f;margin-bottom:18px;">Aşağıdaki doğrulama kodunu uygulamaya gir:</div>
              <div style="text-align:center;padding:18px 16px;border:1px dashed #b7c7da;border-radius:18px;background:#f8fbff;color:#0f2d52;font-size:42px;letter-spacing:.28em;font-weight:800;">{otp}</div>
              <div style="margin-top:20px;font-size:14px;line-height:1.8;color:#5b6f86;">Bu kod {OTP_VALIDITY_SECONDS} saniye geçerlidir. Güvenliğin için kimseyle paylaşma.</div>
              <div style="margin-top:12px;font-size:13px;line-height:1.7;color:#7f8da3;">Bu isteği sen yapmadıysan bu e-postayı yok sayabilirsin.</div>
            </td>
          </tr>
          <tr>
            <td style="padding:0 40px 28px;">
              <div style="height:1px;background:#e4ebf3;"></div>
              <div style="margin-top:16px;font-size:12px;line-height:1.6;color:#9aa7b8;">YTU Social transactional mail</div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>'''
    return text_body, html_body


def _mail_log(message, level='error'):
    try:
        logger = current_app.logger
    except RuntimeError:
        print(message)
        return

    log_method = getattr(logger, level, logger.error)
    log_method(message)


def _build_sendgrid_message(subject, recipient_email, text_body, html_body=None):
    sender_email, sender_name = _sendgrid_sender_details()
    message = Mail(
        from_email=Email(sender_email, sender_name),
        to_emails=To(recipient_email),
        subject=subject,
        plain_text_content=Content('text/plain', text_body),
        html_content=Content('text/html', html_body or text_body.replace('\n', '<br>')),
    )
    return message


def _send_sendgrid_job(app, recipient_email, subject, text_body, html_body=None):
    with app.app_context():
        try:
            if app.config.get('SENDGRID_SANDBOX_MODE'):
                _mail_log(f"SendGrid sandbox modu açık ({recipient_email}); gerçek gönderim atlandı.", 'warning')
                return True

            api_key = (app.config.get('SENDGRID_API_KEY') or '').strip()
            if not api_key:
                _mail_log(f"SendGrid gönderim hatası ({recipient_email}): SENDGRID_API_KEY eksik.")
                return False

            if not _SENDGRID_SDK_AVAILABLE:
                _mail_log(f"SendGrid gönderim hatası ({recipient_email}): SendGrid SDK yüklü değil.")
                return False

            message = _build_sendgrid_message(subject, recipient_email, text_body, html_body)
            response = SendGridAPIClient(api_key).send(message)
            if response.status_code in (200, 202):
                return True

            response_body = getattr(response, 'body', b'')
            if isinstance(response_body, bytes):
                response_body = response_body.decode('utf-8', errors='ignore')
            _mail_log(f"SendGrid API Hatası ({response.status_code}) ({recipient_email}): {response_body}")
            return False
        except Exception as exc:
            _mail_log(f"SendGrid mail gönderim hatası ({recipient_email}): {exc}", 'exception')
            return False


def _queue_sendgrid_email(subject, email, text_body, html_body=None):
    app = current_app._get_current_object()
    api_key = (app.config.get('SENDGRID_API_KEY') or '').strip()
    if not api_key:
        _mail_log(f"SendGrid gönderim hatası ({email}): SENDGRID_API_KEY eksik.")
        return False

    return _send_sendgrid_job(app, email, subject, text_body, html_body)


def _queue_otp_email(subject, email, intro_text, otp):
    text_body, html_body = _build_otp_email_payload(subject, intro_text, otp)
    return _queue_sendgrid_email(subject, email, text_body, html_body)


def _verify_redirect(email, next_url=None):
    safe_next = _safe_next_url(next_url)
    if safe_next:
        return redirect(url_for('auth.verify', email=email, next=safe_next))
    return redirect(url_for('auth.verify', email=email))


def _render_register(next_url=None):
    return render_template('register.html', next_url=next_url)


def _render_login(next_url=None):
    return render_template('login.html', next_url=next_url)


def _redirect_register_with_flash(message, next_url=None):
    flash(message, 'danger')
    safe_next = _safe_next_url(next_url)
    if safe_next:
        return redirect(url_for('auth.register', next=safe_next))
    return redirect(url_for('auth.register'))


def _render_database_unavailable(template_name, next_url=None, email=None):
    flash('Veritabanına şu an ulaşılamıyor. Biraz sonra tekrar dene.', 'danger')
    if template_name == 'register':
        return _render_register(next_url)
    if template_name == 'verify':
        return _render_verify(email, next_url)
    if template_name == 'login':
        return _render_login(next_url)
    if template_name == 'forgot_password':
        return render_template('forgot_password.html')
    if template_name == 'reset_password':
        return render_template('reset_password.html', email=email)
    return redirect(url_for('main.index'))


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

        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')

        try:
            user = User.query.filter_by(email=email).first()
        except SQLAlchemyError as exc:
            db.session.rollback()
            _mail_log(f"Kayıt sırasında veritabanı erişilemedi ({email}): {exc}", 'exception')
            return _render_database_unavailable('register', next_url=next_url)

        if user:
            if user.is_verified:
                flash("Bu mail adresiyle zaten kayıtlı bir hesap var. Giriş yapabilirsin.", "danger")
                return _render_register(next_url)

            user.password = hashed_pw
            user.is_verified = False
            otp = _issue_otp(user)
            try:
                db.session.commit()
                if not _queue_otp_email(
                    'YTÜ Portal Doğrulama',
                    email,
                    'Portalımıza hoş geldin! Doğrulama kodun aşağıda.',
                    otp,
                ):
                    return _redirect_register_with_flash("Doğrulama kodu gönderilemedi. Lütfen tekrar dene.", next_url)
            except SQLAlchemyError as exc:
                db.session.rollback()
                _mail_log(f"Kayıt güncellenirken veritabanı erişilemedi ({email}): {exc}", 'exception')
                return _render_database_unavailable('register', next_url=next_url)
            except Exception as e:
                db.session.rollback()
                print(f"Kayıt Hatası: {e}")
                return _redirect_register_with_flash("Doğrulama kodu gönderilemedi. Lütfen tekrar dene.", next_url)

            flash("Doğrulama kodu gönderiliyor. Birkaç saniye içinde mailinde olmalı.", "success")
            return _verify_redirect(email, next_url)

        try:
            base_handle = email.split('@')[0]
            handle = base_handle
            while User.query.filter_by(handle=handle).first():
                handle = base_handle + str(random.randint(1, 999))

            new_user = User(
                email=email,
                password=hashed_pw,
                handle=handle,
                is_verified=False,
            )
            otp = _issue_otp(new_user)

            db.session.add(new_user)
            db.session.commit()
            if not _queue_otp_email(
                'YTÜ Portal Doğrulama',
                email,
                'Portalımıza hoş geldin! Doğrulama kodun aşağıda.',
                otp,
            ):
                return _redirect_register_with_flash("Doğrulama kodu gönderilemedi. Lütfen tekrar dene.", next_url)
        except SQLAlchemyError as exc:
            db.session.rollback()
            _mail_log(f"Kayıt oluşturulurken veritabanı erişilemedi ({email}): {exc}", 'exception')
            return _render_database_unavailable('register', next_url=next_url)
        except Exception as e:
            db.session.rollback()
            print(f"Kayıt Hatası: {e}")
            return _redirect_register_with_flash("Doğrulama kodu gönderilemedi. Lütfen tekrar dene.", next_url)

        flash("Doğrulama kodu gönderiliyor. Birkaç saniye içinde mailinde olmalı.", "success")
        return _verify_redirect(email, next_url)

    return _render_register(next_url)


@auth.route('/verify/<email>', methods=['GET', 'POST'])
def verify(email):
    email = _normalize_email(email)
    next_url = _safe_next_url(request.args.get('next') or request.form.get('next'))
    try:
        user = User.query.filter_by(email=email).first()
    except SQLAlchemyError as exc:
        db.session.rollback()
        _mail_log(f"Doğrulama sırasında veritabanı erişilemedi ({email}): {exc}", 'exception')
        return _render_database_unavailable('verify', next_url=next_url, email=email)

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
            except SQLAlchemyError as exc:
                db.session.rollback()
                _mail_log(f"Doğrulama kodu onaylanırken veritabanı erişilemedi ({email}): {exc}", 'exception')
                return _render_database_unavailable('verify', next_url=next_url, email=email)
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
        try:
            user = User.query.filter_by(email=email).first()
        except SQLAlchemyError as exc:
            db.session.rollback()
            _mail_log(f"Şifre sıfırlama sırasında veritabanı erişilemedi ({email}): {exc}", 'exception')
            return _render_database_unavailable('forgot_password')
        if user:
            if _otp_is_active(user):
                otp = user.otp_code
            else:
                otp = _issue_otp(user)
            try:
                db.session.commit()
                if not _queue_otp_email(
                    'YTÜ Portal Şifre Sıfırlama',
                    email,
                    'Şifre sıfırlama kodun aşağıda.',
                    otp,
                ):
                    flash("Sıfırlama kodu gönderilemedi. Lütfen tekrar dene.", "danger")
                    return render_template('forgot_password.html')
                flash("Sıfırlama kodu gönderiliyor. Birkaç saniye içinde mailinde olmalı.", "info")
                return redirect(url_for('auth.reset_password', email=email))
            except SQLAlchemyError as exc:
                db.session.rollback()
                _mail_log(f"Şifre sıfırlama kodu kaydedilirken veritabanı erişilemedi ({email}): {exc}", 'exception')
                return _render_database_unavailable('forgot_password')
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
        try:
            user = User.query.filter_by(email=email).first()
        except SQLAlchemyError as exc:
            db.session.rollback()
            _mail_log(f"Şifre güncelleme sırasında veritabanı erişilemedi ({email}): {exc}", 'exception')
            return _render_database_unavailable('reset_password', email=email)

        if not password:
            flash("Şifre boş olamaz!", "danger")
        elif user and user.otp_code == kod and _otp_is_active(user):
            user.password = generate_password_hash(password, method='pbkdf2:sha256')
            user.otp_code = None
            user.otp_expires_at = None
            try:
                db.session.commit()
            except SQLAlchemyError as exc:
                db.session.rollback()
                _mail_log(f"Şifre güncellenirken veritabanı erişilemedi ({email}): {exc}", 'exception')
                return _render_database_unavailable('reset_password', email=email)
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
        try:
            user = User.query.filter_by(email=email).first()
        except SQLAlchemyError as exc:
            db.session.rollback()
            _mail_log(f"Giriş sırasında veritabanı erişilemedi ({email}): {exc}", 'exception')
            return _render_database_unavailable('login', next_url=next_url)

        if user and check_password_hash(user.password, password):
            if not user.is_verified:
                if _otp_is_active(user):
                    otp = user.otp_code
                else:
                    otp = _issue_otp(user)
                try:
                    db.session.commit()
                    if not _queue_otp_email(
                        'YTÜ Portal Doğrulama',
                        email,
                        'Hesabını doğrulamak için kodun aşağıda.',
                        otp,
                    ):
                        flash("Doğrulama kodu yeniden gönderilemedi.", "danger")
                        return _render_login(next_url)
                except SQLAlchemyError as exc:
                    db.session.rollback()
                    _mail_log(f"Giriş sırasında veritabanı erişilemedi ({email}): {exc}", 'exception')
                    return _render_database_unavailable('login', next_url=next_url)
                except Exception as e:
                    db.session.rollback()
                    print(f"Giriş Hatası: {e}")
                    flash("Doğrulama kodu yeniden gönderilirken sorun oluştu.", "danger")
                    return _render_login(next_url)

                flash("Hesabın henüz doğrulanmamış. Doğrulama kodu yeniden gönderiliyor.", "info")
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