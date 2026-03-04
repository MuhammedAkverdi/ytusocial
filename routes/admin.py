from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort, current_app
from flask_login import login_required, current_user
from extensions import db
from models import User, Post, Feedback, Club
from utils import optimize_and_save_image, allowed_file, ONLINE_USERS
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import psutil

admin = Blueprint('admin', __name__)

@admin.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin: return redirect(url_for('main.index'))
    
    reported_posts = Post.query.filter(Post.report_count > 0).order_by(Post.report_count.desc()).all()
    feedbacks = Feedback.query.order_by(Feedback.date_sent.desc()).all()
    
    return render_template('admin.html',
                           total_users=User.query.count(),
                           total_posts=Post.query.count(),
                           reported_posts=reported_posts, 
                           feedbacks=feedbacks,
                           cpu=psutil.cpu_percent(),
                           ram=psutil.virtual_memory().percent,
                           active_count=len(ONLINE_USERS),
                           users=User.query.limit(50).all())

@admin.route('/admin/delete_content/<string:type>/<int:id>')
@login_required
def admin_delete_content(type, id):
    if not current_user.is_admin: return "Yetkisiz"
    
    if type == 'post':
        item = Post.query.get_or_404(id)
        db.session.delete(item)
        flash("İçerik kalıcı olarak silindi.", "success")
    elif type == 'feedback':
        item = Feedback.query.get_or_404(id)
        db.session.delete(item)
        flash("Geri bildirim silindi.", "success")
    
    db.session.commit()
    return redirect(url_for('admin.admin_panel'))

@admin.route('/admin/ban_user/<int:user_id>/<string:action>')
@login_required
def admin_ban_user(user_id, action):
    if not current_user.is_admin: return "Yetkisiz"
    
    u = User.query.get_or_404(user_id)
    
    if action == 'perm': 
        u.is_banned = True
        u.ban_expiration = None 
        flash(f"{u.username} süresiz banlandı.", "danger")
        
    elif action == 'temp_24h': 
        u.ban_expiration = datetime.now() + timedelta(hours=24)
        flash(f"{u.username} 24 saat uzaklaştırıldı.", "warning")
        
    elif action == 'temp_1w': 
        u.ban_expiration = datetime.now() + timedelta(days=7)
        flash(f"{u.username} 1 hafta uzaklaştırıldı.", "warning")
        
    elif action == 'unban': 
        u.is_banned = False
        u.ban_expiration = None
        flash(f"{u.username} yasağı kaldırıldı.", "success")
        
    db.session.commit()
    return redirect(url_for('admin.admin_panel'))

@admin.route('/admin/reset_bio/<int:user_id>')
@login_required
def admin_reset_bio(user_id):
    if not current_user.is_admin: return "Yetkisiz"
    user = User.query.get_or_404(user_id)
    user.bio = None
    db.session.commit()
    flash(f"{user.username} biyografisi sıfırlandı.", "success")
    return redirect(url_for('admin.admin_panel'))

@admin.route('/admin/delete_user_posts/<int:user_id>')
@login_required
def admin_delete_user_posts(user_id):
    if not current_user.is_admin: return "Yetkisiz"
    user = User.query.get_or_404(user_id)
    posts = Post.query.filter_by(user_id=user.id).all()
    for p in posts:
        db.session.delete(p)
    db.session.commit()
    flash(f"{user.username} kullanıcısının tüm gönderileri silindi.", "success")
    return redirect(url_for('admin.admin_panel'))

@admin.route('/admin/create_tester', methods=['POST'])
@login_required
def create_tester():
    if not current_user.is_admin:
        return redirect(url_for('main.index'))
    username = request.form.get('username')
    password = request.form.get('password')
    email = request.form.get('email')
    if User.query.filter_by(email=email).first():
        flash("Bu mail zaten kayıtlı!", "danger")
        return redirect(url_for('admin.admin_panel'))
    hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
    new_user = User(
        username=username,
        email=email,
        password=hashed_pw,
        handle=username.lower().replace(" ", ""),
        is_verified=True,
        department="Tester / Misafir"
    )
    db.session.add(new_user)
    db.session.commit()
    flash(f"Tester hesabı '{username}' başarıyla oluşturuldu!", "success")
    return redirect(url_for('admin.admin_panel'))

@admin.route('/admin/create_club', methods=['POST'])
@login_required
def admin_create_club():
    if not current_user.is_admin: return redirect(url_for('main.index'))
    
    name = request.form.get('name')
    description = request.form.get('description')
    leader_username = request.form.get('leader_username')
    
    slug = name.lower().replace(' ', '-').replace('ı', 'i').replace('ğ', 'g').replace('ü', 'u').replace('ş', 's').replace('ö', 'o').replace('ç', 'c')
    
    leader = User.query.filter_by(username=leader_username).first()
    
    logo_filename = 'default_club.jpg'
    if 'logo' in request.files:
        file = request.files['logo']
        if file and allowed_file(file.filename):
            logo_filename = optimize_and_save_image(file, 'static/img', max_size=(400, 400))

    new_club = Club(name=name, slug=slug, description=description, logo_file=logo_filename)
    if leader:
        new_club.leader = leader
    
    db.session.add(new_club)
    db.session.commit()
    flash(f"Kulüp oluşturuldu: {name}", "success")
    return redirect(url_for('admin.admin_panel'))

@admin.route('/beni_admin_yap')
@login_required
def make_me_admin():
    # Bu endpoint tehlikeli olduğundan doğrudan admin atamasını kaldırdık
    abort(403)

@admin.route('/admin/create_user', methods=['POST'])
@login_required
def admin_create_user():
    if not current_user.is_admin: return "Yetkisiz Alan"
    
    email = request.form.get('email')
    username = request.form.get('username')
    password = request.form.get('password')
    dept = request.form.get('department')
    
    if User.query.filter_by(email=email).first():
        flash("Bu mail zaten kayıtlı!", "danger")
        return redirect(url_for('admin.admin_panel'))
        
    new_user = User(
        email=email,
        username=username,
        password=generate_password_hash(password),
        department=dept,
        handle=username.lower().replace(" ", ""),
        is_verified=True,
        is_admin=(dept == "Admin")
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    flash(f"✅ Kullanıcı oluşturuldu: {username}", "success")
    return redirect(url_for('admin.admin_panel'))

@admin.route('/fix_db')
@login_required
def manual_fix_db():
    # Sadece adminler veritabanı tamir işlemini başlatabilir
    if not current_user.is_admin:
        abort(403)
    try:
        from routes.db_fix import veritabani_tamir_et
        veritabani_tamir_et()
        return "<h3>✅ Veritabanı tamir işlemi başlatıldı. Logları sunucuda kontrol edin.</h3>"
    except Exception:
        current_app.logger.exception('DB tamir hatası')
        return "<h3>❌ Hata oluştu. Detaylar sunucu loglarında.</h3>", 500