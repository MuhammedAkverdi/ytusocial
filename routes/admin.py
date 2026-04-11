from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort, current_app
from flask_login import login_required, current_user
from extensions import db
from models import User, Post, Feedback, Club, Note, ClubVote, NoteVote, Notification, Advert, ExamAnalysis, ExamAttempt, ExamResponse, ExamComment
from utils import allowed_image_file, upload_club_logo_to_spaces, get_online_user_count
from routes.main import _purge_post_tree
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from flask_wtf.csrf import validate_csrf
import os
import psutil
import re

admin = Blueprint('admin', __name__)


def _admin_csrf_valid():
    try:
        validate_csrf(request.form.get('csrf_token'))
        return True
    except Exception:
        return False


def _build_exam_overviews():
    exams = ExamAnalysis.query.order_by(ExamAnalysis.created_at.desc()).all()
    response_counts = dict(
        db.session.query(ExamResponse.exam_id, func.count(ExamResponse.id))
        .group_by(ExamResponse.exam_id)
        .all()
    )
    attempt_counts = dict(
        db.session.query(ExamAttempt.exam_id, func.count(ExamAttempt.id))
        .group_by(ExamAttempt.exam_id)
        .all()
    )
    comment_counts = dict(
        db.session.query(ExamComment.exam_id, func.count(ExamComment.id))
        .group_by(ExamComment.exam_id)
        .all()
    )

    overviews = []
    for exam in exams:
        overviews.append({
            'code': exam.code,
            'title': exam.title,
            'question_count': exam.question_count,
            'disclaimer': exam.disclaimer,
            'comments_enabled': exam.comments_enabled,
            'is_published': exam.is_published,
            'created_at': exam.created_at,
            'created_by': exam.created_by,
            'response_count': response_counts.get(exam.code, 0),
            'attempt_count': attempt_counts.get(exam.code, 0),
            'comment_count': comment_counts.get(exam.code, 0),
        })
    return overviews

@admin.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin: return redirect(url_for('main.index'))
    
    reported_posts = Post.query.filter(Post.report_count > 0).order_by(Post.report_count.desc()).all()
    reported_notes = Note.query.filter(Note.report_count > 0, Note.is_approved == True).order_by(Note.report_count.desc()).all()
    feedbacks = Feedback.query.order_by(Feedback.date_sent.desc()).all()
    pending_notes = Note.query.filter_by(is_approved=False).order_by(Note.date_posted.desc()).all()
    moderators = User.query.filter_by(is_moderator=True).all()
    exam_analyses = _build_exam_overviews()
    
    return render_template('admin.html',
                           total_users=User.query.count(),
                           total_posts=Post.query.count(),
                           reported_posts=reported_posts,
                           reported_notes=reported_notes,
                           feedbacks=feedbacks,
                           cpu=psutil.cpu_percent(),
                           ram=psutil.virtual_memory().percent,
                           active_count=get_online_user_count(),
                           users=User.query.limit(50).all(),
                           clubs=Club.query.order_by(Club.name).all(),
                           pending_notes=pending_notes,
                           moderators=moderators,
                           exam_analyses=exam_analyses)


@admin.route('/moderator')
@login_required
def moderator_panel():
    if not (current_user.is_admin or current_user.is_moderator):
        return redirect(url_for('main.index'))
    pending_notes = Note.query.filter_by(is_approved=False).order_by(Note.date_posted.desc()).all()
    reported_notes = Note.query.filter(Note.report_count > 0, Note.is_approved == True).order_by(Note.report_count.desc()).all()
    reported_posts = Post.query.filter(Post.report_count > 0).order_by(Post.report_count.desc()).all()
    reported_exam_comments = ExamComment.query.filter(ExamComment.report_count > 0, ExamComment.is_hidden == False).order_by(ExamComment.report_count.desc(), ExamComment.created_at.desc()).all()
    moderator_tasks = [
        {
            'anchor': 'pending-notes',
            'title': 'Bekleyen notları incele',
            'description': 'Onay bekleyen notları tek tek kontrol et. Uygun olanları onayla, uygun olmayanları reddet.',
            'count': len(pending_notes),
            'icon': 'fa-clipboard-check',
        },
        {
            'anchor': 'reported-notes',
            'title': 'Bildirilen notları değerlendir',
            'description': 'Şikayet edilen notları gözden geçir, içerik kurallarına uymuyorsa sil.',
            'count': len(reported_notes),
            'icon': 'fa-triangle-exclamation',
        },
        {
            'anchor': 'reported-posts',
            'title': 'Bildirilen gönderileri temizle',
            'description': 'Şikayet edilen gönderileri incele. Gerekirse kaldır, gerekirse kullanıcıyı işaretle.',
            'count': len(reported_posts),
            'icon': 'fa-bullhorn',
        },
        {
            'anchor': 'reported-exam-comments',
            'title': 'Sınav yorumlarını denetle',
            'description': 'Şikayet edilen soru yorumlarını gizle, tartışmayı temiz tut ve gerekirse içeriği kaldır.',
            'count': len(reported_exam_comments),
            'icon': 'fa-comments',
        },
    ]
    return render_template('moderator.html',
                           pending_notes=pending_notes,
                           reported_notes=reported_notes,
                           reported_posts=reported_posts,
                           reported_exam_comments=reported_exam_comments,
                           moderator_tasks=moderator_tasks)


@admin.route('/admin/approve_note/<int:note_id>')
@login_required
def approve_note(note_id):
    if not (current_user.is_admin or current_user.is_moderator): abort(403)
    note = Note.query.get_or_404(note_id)
    note.is_approved = True
    note.author.score += 10
    db.session.commit()
    flash(f'"{note.title}" onaylandı. {note.author.username} +10 puan kazandı.', 'success')
    if current_user.is_admin:
        return redirect(url_for('admin.admin_panel'))
    return redirect(url_for('admin.moderator_panel'))


@admin.route('/admin/reject_note/<int:note_id>')
@login_required
def reject_note(note_id):
    if not (current_user.is_admin or current_user.is_moderator): abort(403)
    note = Note.query.get_or_404(note_id)
    import os as _os
    file_path = _os.path.join(current_app.root_path, 'static', 'note_files', note.file_path)
    if _os.path.exists(file_path):
        _os.remove(file_path)
    db.session.delete(note)
    db.session.commit()
    flash('Not reddedildi ve silindi.', 'warning')
    if current_user.is_admin:
        return redirect(url_for('admin.admin_panel'))
    return redirect(url_for('admin.moderator_panel'))


@admin.route('/admin/add_moderator', methods=['POST'])
@login_required
def add_moderator():
    if not current_user.is_admin: abort(403)
    username = request.form.get('username', '').strip()
    user = User.query.filter_by(username=username).first()
    if not user:
        flash(f'"{username}" adlı kullanıcı bulunamadı.', 'danger')
    elif user.is_admin:
        flash('Admin zaten tüm yetkilere sahip.', 'warning')
    elif user.is_moderator:
        flash(f'{user.username} zaten moderatör.', 'warning')
    else:
        user.is_moderator = True
        db.session.commit()
        flash(f'{user.username} moderatör olarak atandı.', 'success')
    return redirect(url_for('admin.admin_panel'))


@admin.route('/admin/remove_moderator/<int:user_id>')
@login_required
def remove_moderator(user_id):
    if not current_user.is_admin: abort(403)
    user = User.query.get_or_404(user_id)
    user.is_moderator = False
    db.session.commit()
    flash(f'{user.username} moderatörlükten alındı.', 'success')
    return redirect(url_for('admin.admin_panel'))



@admin.route('/admin/delete_content/<string:type>/<int:id>')
@login_required
def admin_delete_content(type, id):
    if not current_user.is_admin: return "Yetkisiz"
    
    try:
        if type == 'post':
            item = Post.query.get_or_404(id)
            _purge_post_tree(item)
            flash("İçerik kalıcı olarak silindi.", "success")
        elif type == 'note':
            item = Note.query.get_or_404(id)
            import os
            file_path = os.path.join(current_app.root_path, 'static', 'note_files', item.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)
            db.session.delete(item)
            flash("Not kalıcı olarak silindi.", "success")
        elif type == 'feedback':
            item = Feedback.query.get_or_404(id)
            db.session.delete(item)
            flash("Geri bildirim silindi.", "success")

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Admin delete content failed: type=%s id=%s", type, id)
        flash("İçerik silinirken hata oluştu.", "danger")
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
    deleted_count = 0
    try:
        for post in posts:
            deleted_count += _purge_post_tree(post)

        db.session.commit()
        flash(f"{user.username} kullanıcısının {deleted_count} gönderisi silindi.", "success")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Admin delete user posts failed for user %s", user_id)
        flash("Gönderiler silinirken hata oluştu.", "danger")
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
    
    try:
        with db.session.no_autoflush:
            leader = User.query.filter_by(username=leader_username).first()

        logo_filename = 'default_club.png'
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename and allowed_image_file(file.filename):
                logo_filename = upload_club_logo_to_spaces(file)

        new_club = Club(name=name, slug=slug, description=description, logo_file=logo_filename)
        if leader:
            new_club.leader = leader

        db.session.add(new_club)
        db.session.commit()
        flash(f"Kulüp oluşturuldu: {name}", "success")
    except IntegrityError:
        db.session.rollback()
        flash(f"Bu isimde başka bir kulüp var: {name}", "danger")
    return redirect(url_for('admin.admin_panel'))


@admin.route('/admin/create_exam_analysis', methods=['POST'])
@login_required
def create_exam_analysis():
    if not (current_user.is_admin or current_user.is_moderator):
        abort(403)
    if not _admin_csrf_valid():
        flash('Güvenlik doğrulaması başarısız.', 'danger')
        return redirect(url_for('admin.admin_panel') if current_user.is_admin else url_for('admin.moderator_panel'))

    redirect_target = url_for('admin.admin_panel') if current_user.is_admin else url_for('admin.moderator_panel')

    code = (request.form.get('code') or '').strip()
    title = (request.form.get('title') or '').strip()
    disclaimer = (request.form.get('disclaimer') or '').strip() or 'Bu sonuçlar kullanıcı oylarıyla oluşmaktadır, resmi cevap anahtarı değildir.'
    comments_enabled = request.form.get('comments_enabled') == 'on'
    is_published = request.form.get('is_published') == 'on' if current_user.is_admin else False

    try:
        question_count = int((request.form.get('question_count') or '0').strip())
    except ValueError:
        question_count = 0

    if not code or not title:
        flash('Sınav kodu ve adı zorunlu.', 'danger')
        return redirect(redirect_target)
    if not re.fullmatch(r'[A-Za-z0-9_-]+', code):
        flash('Sınav kodu sadece harf, rakam, alt çizgi ve tire içerebilir.', 'danger')
        return redirect(redirect_target)
    if question_count < 1 or question_count > 200:
        flash('Soru sayısı 1 ile 200 arasında olmalı.', 'danger')
        return redirect(redirect_target)
    if ExamAnalysis.query.filter_by(code=code).first():
        flash(f'"{code}" kodlu sınav zaten mevcut.', 'warning')
        return redirect(redirect_target)

    exam = ExamAnalysis(
        code=code,
        title=title,
        question_count=question_count,
        disclaimer=disclaimer,
        comments_enabled=comments_enabled,
        is_published=is_published,
        created_by_id=current_user.id,
    )
    db.session.add(exam)
    db.session.commit()
    flash(f'Sınav analizi oluşturuldu: {code}', 'success')
    return redirect(redirect_target)


@admin.route('/admin/exam/<string:exam_code>/toggle_publish', methods=['POST'])
@login_required
def toggle_exam_publish(exam_code):
    if not current_user.is_admin:
        abort(403)
    if not _admin_csrf_valid():
        flash('Güvenlik doğrulaması başarısız.', 'danger')
        return redirect(url_for('admin.admin_panel'))

    exam = ExamAnalysis.query.get_or_404(exam_code)
    exam.is_published = not exam.is_published
    db.session.commit()
    flash(f'"{exam.code}" yayın durumu güncellendi.', 'success')
    return redirect(url_for('admin.admin_panel'))


@admin.route('/admin/exam/<string:exam_code>/delete', methods=['POST'])
@login_required
def delete_exam_analysis(exam_code):
    if not current_user.is_admin:
        abort(403)
    if not _admin_csrf_valid():
        flash('Güvenlik doğrulaması başarısız.', 'danger')
        return redirect(url_for('admin.admin_panel'))

    exam = ExamAnalysis.query.get_or_404(exam_code)
    db.session.delete(exam)
    db.session.commit()
    flash(f'"{exam.code}" sınav analizi silindi.', 'success')
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

@admin.route('/admin/delete_user/<int:user_id>')
@login_required
def admin_delete_user(user_id):
    if not current_user.is_admin: return "Yetkisiz"
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Kendi hesabınızı silemezsiniz.", "danger")
        return redirect(url_for('admin.admin_panel'))
    if user.is_admin:
        flash("Admin hesabı silinemez.", "danger")
        return redirect(url_for('admin.admin_panel'))
    username = user.username
    try:
        from models import Comment, Story
        Notification.query.filter(
            (Notification.user_id == user.id) | (Notification.actor_id == user.id)
        ).delete(synchronize_session=False)
        Feedback.query.filter_by(user_id=user.id).delete()
        ClubVote.query.filter_by(user_id=user.id).delete()
        NoteVote.query.filter_by(user_id=user.id).delete()
        Advert.query.filter_by(user_id=user.id).delete()
        Note.query.filter_by(user_id=user.id).delete()
        for exam in list(ExamAnalysis.query.filter_by(created_by_id=user.id)):
            db.session.delete(exam)
        ExamComment.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        ExamResponse.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        ExamAttempt.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        user.messages_sent.delete()
        user.messages_received.delete()
        Comment.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        Story.query.filter_by(user_id=user.id).delete()
        for post in list(user.posts):
            db.session.delete(post)
        db.session.flush()
        db.session.delete(user)
        db.session.commit()
        flash(f"✅ {username} hesabı kalıcı olarak silindi.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Hata oluştu: {str(e)}", "danger")
    return redirect(url_for('admin.admin_panel'))


@admin.route('/admin/edit_club/<int:club_id>', methods=['POST'])
@login_required
def admin_edit_club(club_id):
    if not current_user.is_admin: return "Yetkisiz"
    club = Club.query.get_or_404(club_id)
    new_name = (request.form.get('name') or club.name or '').strip()
    new_description = (request.form.get('description') or club.description or '').strip()
    leader_username = request.form.get('leader_username', '').strip()

    if not new_name:
        flash('Kulüp adı boş olamaz.', 'danger')
        return redirect(url_for('admin.admin_panel'))

    try:
        with db.session.no_autoflush:
            existing_club = Club.query.filter(Club.name == new_name, Club.id != club.id).first()
            leader = User.query.filter_by(username=leader_username).first() if leader_username else None

        if existing_club:
            flash(f'Bu isimde başka bir kulüp var: {new_name}', 'danger')
            return redirect(url_for('admin.admin_panel'))

        club.name = new_name
        club.description = new_description

        if leader_username:
            if leader:
                club.leader = leader
            else:
                flash(f'"{leader_username}" adlı kullanıcı bulunamadı.', 'warning')

        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename and allowed_image_file(file.filename):
                club.logo_file = upload_club_logo_to_spaces(file)

        db.session.commit()
        flash(f"Kulüp güncellendi: {club.name}", "success")
    except IntegrityError:
        db.session.rollback()
        flash(f"Bu isimde başka bir kulüp var: {new_name}", "danger")
    return redirect(url_for('admin.admin_panel'))


@admin.route('/admin/delete_club/<int:club_id>')
@login_required
def admin_delete_club(club_id):
    if not current_user.is_admin: return "Yetkisiz"
    club = Club.query.get_or_404(club_id)
    name = club.name
    # Feed postlarındaki club_id bağlantısını kaldır
    Post.query.filter_by(club_id=club.id).update({'club_id': None})
    ClubVote.query.filter_by(club_id=club.id).delete()
    db.session.flush()
    db.session.delete(club)
    db.session.commit()
    flash(f"Kulüp silindi: {name}", "success")
    return redirect(url_for('admin.admin_panel'))


@admin.route('/admin/edit_note/<int:note_id>', methods=['POST'])
@login_required
def admin_edit_note(note_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Yetkisiz'}), 403
    note = Note.query.get_or_404(note_id)
    note.title       = request.form.get('title',       note.title).strip()
    note.course_code = request.form.get('course_code', note.course_code).strip()
    note.department  = request.form.get('department',  note.department).strip()
    note.description = request.form.get('description', note.description or '').strip()
    db.session.commit()
    flash('Not güncellendi.', 'success')
    return redirect(url_for('admin.admin_panel'))


@admin.route('/admin/exam_comment/<int:comment_id>/hide', methods=['POST'])
@login_required
def hide_exam_comment(comment_id):
    if not (current_user.is_admin or current_user.is_moderator):
        abort(403)
    if not _admin_csrf_valid():
        flash('Güvenlik doğrulaması başarısız.', 'danger')
        return redirect(request.referrer or url_for('admin.moderator_panel'))

    comment = ExamComment.query.get_or_404(comment_id)
    comment.is_hidden = True
    db.session.commit()
    flash('Sınav yorumu gizlendi.', 'success')
    return redirect(request.referrer or url_for('admin.moderator_panel'))


@admin.route('/admin/exam_comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_exam_comment(comment_id):
    if not current_user.is_admin:
        abort(403)
    if not _admin_csrf_valid():
        flash('Güvenlik doğrulaması başarısız.', 'danger')
        return redirect(request.referrer or url_for('admin.admin_panel'))

    comment = ExamComment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    flash('Sınav yorumu silindi.', 'success')
    return redirect(request.referrer or url_for('admin.admin_panel'))

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