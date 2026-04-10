from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app, send_from_directory
from flask_login import login_required, current_user
from extensions import db, socketio
from models import User, Post, Story, Club, ClubVote, ClubPost, Poll, PollOption, PollVote, SavedPost, Comment, Message, Notification, Feedback, Note, NoteVote, Advert, StoryView, likes
from utils import optimize_and_save_image, allowed_file, create_notification, get_trending_hashtags, get_file_size_str, icerik_temiz_mi, scan_file_safety, ALLOWED_NOTE_EXTENSIONS, allowed_image_file, upload_club_logo_to_spaces
from sqlalchemy import or_, func
from datetime import datetime, timedelta
import os
import re
import secrets
from werkzeug.utils import secure_filename

main = Blueprint('main', __name__)


def _purge_post_tree(post):
    deleted_count = 1

    for repost in list(post.reposts):
        deleted_count += _purge_post_tree(repost)

    with db.session.no_autoflush:
        if post.image_file:
            file_path = os.path.join(current_app.root_path, 'static', 'post_images', post.image_file)
            if os.path.exists(file_path):
                os.remove(file_path)

        SavedPost.query.filter_by(post_id=post.id).delete(synchronize_session=False)
        Notification.query.filter_by(post_id=post.id).update({Notification.post_id: None}, synchronize_session=False)

        db.session.execute(likes.delete().where(likes.c.post_id == post.id))

        Comment.query.filter_by(post_id=post.id).delete(synchronize_session=False)

        if post.poll:
            db.session.delete(post.poll)

        db.session.delete(post)

    return deleted_count

@main.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if not current_user.is_verified:
        return redirect(url_for('auth.verify', email=current_user.email))
    
    if request.method == 'POST':
        post_content = request.form.get('content')
        image = request.files.get('image')
        poll_opt1 = request.form.get('poll_opt1')
        poll_opt2 = request.form.get('poll_opt2')

        if post_content or image:
            filename = None
            if image and allowed_file(image.filename):
                filename = optimize_and_save_image(image, current_app.config['POST_UPLOAD_FOLDER'])

            new_post = Post(content=post_content, image_file=filename, author=current_user)
            db.session.add(new_post)
            
            if poll_opt1 and poll_opt2:
                new_poll = Poll(post=new_post)
                db.session.add(new_poll)
                db.session.add(PollOption(text=poll_opt1, poll=new_poll))
                db.session.add(PollOption(text=poll_opt2, poll=new_poll))
            
            db.session.commit()
            flash("Gönderin başarıyla paylaşıldı!", "success")
            return redirect(url_for('main.index'))
        
    one_day_ago = datetime.utcnow() - timedelta(days=1)
    active_stories = Story.query.filter(Story.timestamp > one_day_ago).order_by(Story.timestamp.asc()).all()
    stories_data = {}
    
    for story in active_stories:
        if story.author not in stories_data:
            stories_data[story.author] = {'stories': [], 'all_seen': True}
        
        seen_by_me = current_user in story.viewers
        if not seen_by_me and story.author != current_user:
            stories_data[story.author]['all_seen'] = False
            
        stories_data[story.author]['stories'].append({
            'id': story.id,
            'file': story.image_file,
            'timestamp': story.timestamp.strftime('%H:%M'),
            'seen': seen_by_me,
            'viewers': [u.username for u in story.viewers] if story.author == current_user else []
        })

    all_clubs = Club.query.all()
    ranked_clubs = sorted(all_clubs, key=lambda c: c.total_votes(), reverse=True)
    top_clubs = ranked_clubs[:3]
    votes = {c.id: c.total_votes() for c in all_clubs}

    active_tab = request.args.get('tab', 'global')
    if active_tab == 'following':
        followed_ids = [user.id for user in current_user.followed]
        followed_ids.append(current_user.id)
        posts = Post.query.filter(Post.user_id.in_(followed_ids)).order_by(Post.date_posted.desc()).all()
    else:
        posts = Post.query.order_by(Post.date_posted.desc()).all()
    
    return render_template('index.html', clubs=ranked_clubs, votes=votes, posts=posts, active_tab=active_tab, stories=stories_data, top_clubs=top_clubs)

@main.route('/like/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    target_post = post.repost_of if post.repost_of else post

    if current_user in target_post.liked_by:
        target_post.liked_by.remove(current_user)
        action = 'unliked'
    else:
        target_post.liked_by.append(current_user)
        action = 'liked'
        create_notification(target_post.author, current_user, 'liked', target_post)
    db.session.commit()
    return jsonify({"likes_count": len(target_post.liked_by), "action": action})

@main.route('/save/<int:post_id>', methods=['POST'])
@login_required
def save_post(post_id):
    post = Post.query.get_or_404(post_id)
    target_post = post.repost_of if post.repost_of else post

    if current_user.has_saved(target_post):
        current_user.unsave_post(target_post)
        action = 'unsaved'
    else:
        current_user.save_post(target_post)
        action = 'saved'
    db.session.commit()
    return jsonify({"action": action})

@main.route('/saved')
@login_required
def saved_posts_list():
    posts = [saved.post for saved in current_user.saved_posts if saved.post]
    posts.reverse()
    return render_template('saved_posts.html', posts=posts)

@main.route('/comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)
    target_post = post.repost_of if post.repost_of else post

    text = request.form.get('comment_text')
    if text:
        comment = Comment(text=text, author=current_user, post=target_post)
        db.session.add(comment)
        db.session.commit()
        create_notification(target_post.author, current_user, 'commented', target_post)
        
        mentions = re.findall(r"@([\w\u00C0-\u024F-]+(?:\.[\w\u00C0-\u024F-]+)*)", text)
        for handle in set(mentions):
            mentioned_user = User.query.filter_by(handle=handle).first()
            if mentioned_user:
                create_notification(mentioned_user, current_user, 'mentioned', target_post)
        
        flash("Yorum yapıldı!", "success")
    return redirect(url_for('main.index'))

@main.route('/repost/<int:post_id>', methods=['POST'])
@login_required
def repost(post_id):
    original_post = Post.query.get_or_404(post_id)
    source_id = original_post.repost_of_id if original_post.repost_of_id else original_post.id
    existing_repost = Post.query.filter_by(user_id=current_user.id, repost_of_id=source_id).first()

    new_post_data = None
    target_post_for_data = Post.query.get(source_id)
    deleted_repost_id = None

    if existing_repost:
        deleted_repost_id = existing_repost.id
        db.session.delete(existing_repost)
        action = 'unreposted'
    else:
        new_repost = Post(content=None, author=current_user, repost_of_id=source_id)
        db.session.add(new_repost)
        db.session.commit()
        action = 'reposted'
        
        new_post_data = {
            'id': new_repost.id,
            'original_id': source_id,
            'content': target_post_for_data.content,
            'author_name': target_post_for_data.author.username,
            'author_pic': target_post_for_data.author.profile_pic,
            'author_dept': target_post_for_data.author.department or 'Bölüm Yok',
            'author_handle': target_post_for_data.author.handle,
            'date': new_repost.date_posted.strftime('%H:%M'),
            'image_file': target_post_for_data.image_file,
            'is_video': target_post_for_data.is_video(),
            'has_poll': False,
            'repost_of': True,
            'reposter_name': current_user.username,
            'likes_count': len(target_post_for_data.liked_by),
            'user_has_reposted': True
        }
    
    db.session.commit()
    return jsonify({"success": True, "action": action, "post": new_post_data, "repost_id": deleted_repost_id})

@main.route('/p/<int:post_id>')
@login_required
def post_detail(post_id):
    if not current_user.is_verified:
        return redirect(url_for('auth.verify', email=current_user.email, next=request.path))
    post = Post.query.get_or_404(post_id)
    return render_template('post_detail.html', post=post)

@main.route('/s/<int:story_id>')
@login_required
def story_detail(story_id):
    story = Story.query.get_or_404(story_id)
    if story.is_expired():
        flash("Bu hikayenin süresi dolmuş.", "warning")
        return redirect(url_for('main.index'))
    
    # Record this view if not already viewed by current user
    existing_view = StoryView.query.filter_by(story_id=story_id, user_id=current_user.id).first()
    if not existing_view:
        view = StoryView(story_id=story_id, user_id=current_user.id)
        db.session.add(view)
        db.session.commit()
    
    # Get all viewers
    viewers = StoryView.query.filter_by(story_id=story_id).order_by(StoryView.viewed_at.desc()).all()
    
    return render_template('story_detail.html', story=story, viewers=viewers)

@main.route('/club/<string:slug>', methods=['GET', 'POST'])
@login_required
def club_detail(slug):
    club = Club.query.filter_by(slug=slug).first_or_404()
    if request.method == 'POST':
        if current_user != club.leader:
            flash("Sadece kulüp başkanı etkinlik paylaşabilir!", "danger")
            return redirect(url_for('main.club_detail', slug=slug))
        
        if 'update_settings' in request.form:
            new_desc = request.form.get('description')
            if new_desc:
                club.description = new_desc
            if 'logo' in request.files:
                file = request.files['logo']
                if file and file.filename and allowed_image_file(file.filename):
                    club.logo_file = upload_club_logo_to_spaces(file)
            db.session.commit()
            flash("Kulüp bilgileri güncellendi!", "success")
            return redirect(url_for('main.club_detail', slug=slug))
            
        title = request.form.get('title')
        content = request.form.get('content')
        file = request.files.get('file')
        filename = None
        if file and allowed_file(file.filename):
            filename = optimize_and_save_image(file, current_app.config['POST_UPLOAD_FOLDER'])
        
        new_event = ClubPost(title=title, content=content, image_file=filename, club=club)
        db.session.add(new_event)

        # Kulüp liderinin duyurusunu global feed'e de ekle
        feed_content = f"{title}\n\n{content}"
        feed_post = Post(content=feed_content, image_file=filename, user_id=current_user.id, club_id=club.id)
        db.session.add(feed_post)

        db.session.commit()
        flash("Etkinlik başarıyla duyuruldu!", "success")
        return redirect(url_for('main.club_detail', slug=slug))

    user_has_voted = False
    if current_user.is_authenticated:
        user_has_voted = ClubVote.query.filter_by(user_id=current_user.id, club_id=club.id).first() is not None

    return render_template('club_details.html', club=club, user_has_voted=user_has_voted)

@main.route('/delete_club_post/<int:post_id>')
@login_required
def delete_club_post(post_id):
    post = ClubPost.query.get_or_404(post_id)
    if current_user != post.club.leader and not current_user.is_admin:
        flash("Yetkisiz işlem!", "danger")
        return redirect(url_for('main.club_detail', slug=post.club.slug))
    slug = post.club.slug

    # İlişkili feed postunu da sil
    linked = Post.query.filter_by(club_id=post.club_id, user_id=post.club.leader_id)\
        .order_by(Post.date_posted.desc()).first()
    if linked:
        db.session.delete(linked)

    db.session.delete(post)
    db.session.commit()
    flash("Etkinlik silindi.", "info")
    return redirect(url_for('main.club_detail', slug=slug))

@main.route('/vote_club/<int:club_id>')
@login_required
def vote_club(club_id):
    club = Club.query.get_or_404(club_id)
    existing_vote = ClubVote.query.filter_by(user_id=current_user.id, club_id=club.id).first()
    if existing_vote:
        return jsonify({'success': False, 'message': "Zaten bu kulübe oy verdin!"})
    else:
        new_vote = ClubVote(user_id=current_user.id, club_id=club.id)
        db.session.add(new_vote)
        db.session.commit()
    return jsonify({'success': True, 'new_total': club.total_votes()})

@main.route('/follow_club/<int:club_id>')
@login_required
def follow_club(club_id):
    club = Club.query.get_or_404(club_id)
    if current_user in club.followers:
        club.followers.remove(current_user)
        action = 'unfollowed'
    else:
        club.followers.append(current_user)
        action = 'followed'
    db.session.commit()
    return jsonify({'success': True, 'action': action, 'count': len(club.followers)})

@main.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.username = request.form.get('username')
        current_user.handle = request.form.get('handle')
        current_user.department = request.form.get('department')
        current_user.bio = request.form.get('bio')
        
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename != '' and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                custom_filename = f"user_{current_user.id}.{ext}"
                saved_filename = optimize_and_save_image(file, current_app.config['PROFILE_UPLOAD_FOLDER'], base_filename=custom_filename, max_size=(400, 400))
                current_user.profile_pic = f"uploads/profiles/{saved_filename}"
                
        db.session.commit()
        flash("Profilin başarıyla güncellendi abem!", "success")
        return redirect(url_for('main.index'))
    return render_template('edit_profile.html')

@main.route('/users')
@login_required
def user_list():
    users = User.query.filter(User.id != current_user.id).order_by(func.random()).limit(50).all()
    return render_template('user_list.html', users=users, title='Önerilen Kişiler')

@main.route('/vote', methods=['POST'])
@login_required
def vote():
    try:
        if not request.is_json:
            return jsonify({"success": False, "error": "Veri formatı JSON olmalı!"}), 400
        data = request.json
        kulup_id = data.get('kulup')
        club = Club.query.get(kulup_id)
        if not club:
            return jsonify({"success": False, "error": "Kulüp bulunamadı!"})
        if not ClubVote.query.filter_by(user_id=current_user.id, club_id=club.id).first():
            db.session.add(ClubVote(user_id=current_user.id, club_id=club.id))
            db.session.commit()
        return jsonify({"success": True, "new_vote": club.total_votes()})
    except Exception as e:
        print(f"OYLAMA HATASI: {e}")
        return jsonify({"success": False, "error": "Sunucu hatası oluştu."}), 500

@main.route('/delete_comment/<int:comment_id>')
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.author != current_user:
        flash("Bu yorumu silme yetkiniz yok!", "danger")
        return jsonify({'success': False, 'error': 'Yetkisiz işlem'})
    db.session.delete(comment)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Yorum silindi'})

@main.route('/edit_comment/<int:comment_id>', methods=['POST'])
@login_required
def edit_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.author != current_user:
        flash("Başkalarının yorumunu düzenleyemezsin!", "danger")
        return redirect(url_for('main.index'))
    zaman_farki = datetime.now() - comment.date_posted
    if zaman_farki > timedelta(minutes=15):
        flash("Süre doldu! Yorumlar sadece ilk 15 dakika içinde düzenlenebilir.", "warning")
        return redirect(url_for('main.index'))
    new_text = request.form.get('new_text')
    if new_text:
        comment.text = new_text
        db.session.commit()
        flash("Yorum güncellendi!", "success")
    return redirect(url_for('main.index'))

@main.route('/delete_post/<int:post_id>')
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        flash("Bu gönderiyi silme yetkiniz yok!", "danger")
        return redirect(url_for('main.index'))
    try:
        _purge_post_tree(post)
        db.session.commit()
        flash("Gönderi silindi.", "info")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Post deletion failed for post %s", post_id)
        flash("Gönderi silinirken hata oluştu.", "danger")
    return redirect(url_for('main.index'))

@main.route('/edit_post/<int:post_id>', methods=['POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        flash("Başkalarının gönderisini düzenleyemezsin!", "danger")
        return redirect(url_for('main.index'))
    new_content = request.form.get('new_content')
    if new_content:
        post.content = new_content
        db.session.commit()
        flash("Gönderi güncellendi!", "success")
    return redirect(url_for('main.index'))

@main.route('/explore')
@login_required
def explore():
    query = request.args.get('q')
    all_clubs = Club.query.all()
    ranked_clubs = sorted(all_clubs, key=lambda c: c.total_votes(), reverse=True)
    votes = {c.id: c.total_votes() for c in all_clubs}

    if query:
        if query.startswith('#'):
            posts = Post.query.filter(Post.content.contains(query)).order_by(Post.date_posted.desc()).all()
            hashtag_stats = {'name': query, 'post_count': len(posts)}
            # Hikaye verisini yükle (ana sayfayla aynı mantık)
            one_day_ago = datetime.utcnow() - timedelta(days=1)
            active_stories = Story.query.filter(Story.timestamp > one_day_ago).order_by(Story.timestamp.asc()).all()
            stories_data = {}
            for story in active_stories:
                if story.author not in stories_data:
                    stories_data[story.author] = {'stories': [], 'all_seen': True}
                seen_by_me = current_user in story.viewers
                if not seen_by_me and story.author != current_user:
                    stories_data[story.author]['all_seen'] = False
                stories_data[story.author]['stories'].append({
                    'id': story.id,
                    'file': story.image_file,
                    'timestamp': story.timestamp.strftime('%H:%M'),
                    'seen': seen_by_me,
                    'viewers': [u.username for u in story.viewers] if story.author == current_user else []
                })
            return render_template('index.html', posts=posts, active_tab='explore', clubs=ranked_clubs, votes=votes, stories=stories_data, top_clubs=ranked_clubs[:3], hashtag_stats=hashtag_stats)
        else:
            search_term = f"%{query}%"
            users = User.query.filter(or_(User.username.ilike(search_term), User.handle.ilike(search_term), User.department.ilike(search_term))).all()
            def siralama_puani(user):
                q_lower = query.lower()
                name_lower = (user.username or "").lower()
                handle_lower = (user.handle or "").lower()
                if name_lower == q_lower or handle_lower == q_lower:
                    return 0
                elif name_lower.startswith(q_lower) or handle_lower.startswith(q_lower):
                    return 1
                else:
                    return 2
            users.sort(key=siralama_puani)
            return render_template('explore.html', users=users, search_query=query, clubs=ranked_clubs, posts=[])
    else:
        users = []
        posts = db.session.query(Post).filter(Post.image_file.isnot(None)).outerjoin(likes).group_by(Post.id).order_by(func.count(likes.c.user_id).desc()).limit(10).all()
        return render_template('explore.html', users=users, search_query=query, clubs=ranked_clubs, posts=posts)

@main.route('/u/<handle>')
@login_required
def user_profile(handle):
    user = User.query.filter_by(handle=handle).first_or_404()
    posts = Post.query.filter_by(author=user).order_by(Post.date_posted.desc()).all()
    media_posts = [p for p in posts if p.image_file]
    return render_template('user_profile.html', user=user, posts=posts, media_posts=media_posts)

@main.route('/trending')
@login_required
def trending_full_list():
    all_tags = get_trending_hashtags()[:10]
    return render_template('trending_full.html', tags=all_tags)

@main.route('/clubs_league')
@login_required
def clubs_full_list():
    all_clubs = Club.query.all()
    ranked_clubs = sorted(all_clubs, key=lambda c: c.total_votes(), reverse=True)
    voted_ids = {v.club_id for v in ClubVote.query.filter_by(user_id=current_user.id).all()}
    return render_template('clubs_full.html', clubs=ranked_clubs, voted_ids=voted_ids)

@main.route('/follow/<handle>')
@login_required
def follow(handle):
    user = User.query.filter_by(handle=handle).first()
    if user is None:
        flash(f'{handle} kullanıcısı bulunamadı.', 'danger')
        return redirect(url_for('main.index'))
    if user == current_user:
        flash('Kendini takip edemezsin!', 'danger')
        return redirect(url_for('main.user_profile', handle=handle))
    current_user.follow(user)
    create_notification(user, current_user, 'followed')
    db.session.commit()
    flash(f'Artık {user.username} kişisini takip ediyorsun!', 'success')
    return redirect(request.referrer or url_for('main.user_profile', handle=handle))

@main.route('/unfollow/<handle>')
@login_required
def unfollow(handle):
    user = User.query.filter_by(handle=handle).first()
    if user is None:
        return redirect(url_for('main.index'))
    current_user.unfollow(user)
    db.session.commit()
    flash(f'{user.username} kişisini takipten çıktın.', 'info')
    return redirect(request.referrer or url_for('main.user_profile', handle=handle))

@main.route('/followers/<handle>')
@login_required
def followers_list(handle):
    user = User.query.filter_by(handle=handle).first_or_404()
    users = user.followers.all()
    title = f"{user.username} - Takipçiler"
    return render_template('user_list.html', users=users, title=title)

@main.route('/following/<handle>')
@login_required
def following_list(handle):
    user = User.query.filter_by(handle=handle).first_or_404()
    users = user.followed.all()
    title = f"{user.username} - Takip Edilenler"
    return render_template('user_list.html', users=users, title=title)

@main.route('/notifications')
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc()).all()
    for notif in notifs:
        notif.is_read = True
    db.session.commit()
    all_clubs = Club.query.all()
    ranked_clubs = sorted(all_clubs, key=lambda c: c.total_votes(), reverse=True)
    top_clubs = ranked_clubs[:3]
    return render_template('notifications.html', notifications=notifs, top_clubs=top_clubs)

@main.route('/messages')
@login_required
def messages_inbox():
    sent_ids = db.session.query(Message.recipient_id).filter(Message.sender_id == current_user.id)
    received_ids = db.session.query(Message.sender_id).filter(Message.recipient_id == current_user.id)
    contact_ids = [r[0] for r in sent_ids.union(received_ids).all()]
    contacts = User.query.filter(User.id.in_(contact_ids)).all() if contact_ids else []
    conversations = []
    for contact in contacts:
        last_msg = Message.query.filter(or_((Message.sender_id == current_user.id) & (Message.recipient_id == contact.id), (Message.sender_id == contact.id) & (Message.recipient_id == current_user.id))).order_by(Message.timestamp.desc()).first()
        unread_count = Message.query.filter_by(sender_id=contact.id, recipient_id=current_user.id, is_read=False).count()
        conversations.append({'user': contact, 'last_message': last_msg, 'timestamp': last_msg.timestamp if last_msg else datetime.min, 'unread': unread_count})
    conversations.sort(key=lambda x: (x['unread'] > 0, x['timestamp']), reverse=True)
    following_users = current_user.followed.all()
    return render_template('inbox.html', conversations=conversations, following_users=following_users)

@main.route('/chat/<handle>', methods=['GET', 'POST'])
@login_required
def chat(handle):
    other_user = User.query.filter_by(handle=handle).first_or_404()
    unreads = Message.query.filter_by(sender_id=other_user.id, recipient_id=current_user.id, is_read=False).all()
    for msg in unreads:
        msg.is_read = True
    db.session.commit()
    if request.method == 'POST':
        body = request.form.get('body')
        if body:
            msg = Message(sender=current_user, recipient=other_user, body=body)
            db.session.add(msg)
            create_notification(other_user, current_user, 'messaged', None)
            db.session.commit()
            return redirect(url_for('main.chat', handle=handle))
    messages = Message.query.filter(or_((Message.sender_id == current_user.id) & (Message.recipient_id == other_user.id), (Message.sender_id == other_user.id) & (Message.recipient_id == current_user.id))).order_by(Message.timestamp.asc()).all()
    return render_template('chat.html', user=other_user, messages=messages)

@main.route('/send_message/<int:rid>', methods=['POST'])
@login_required
def send_message(rid):
    b = request.form.get('body')
    story_id = request.form.get('story_id')
    file = request.files.get('file')
    msg_type = 'text'
    file_path = None 
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        import uuid
        ext = os.path.splitext(filename)[1].lower()
        mime_type = (file.mimetype or '').lower()
        audio_exts = {'.webm', '.wav', '.ogg', '.mp3', '.m4a', '.aac', '.flac'}
        image_exts = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
        video_exts = {'.mp4', '.mov', '.avi', '.webm', '.mkv', '.flv'}

        if mime_type.startswith('audio/') or (ext in audio_exts and not mime_type.startswith('video/')):
            msg_type = 'audio'
            upload_folder = current_app.config.get('AUDIO_UPLOAD_FOLDER', os.path.join('static', 'audio_files'))
        else:
            upload_folder = current_app.config['MESSAGE_FILE_UPLOAD_FOLDER']
            msg_type = 'file'
            if mime_type.startswith('image/') or ext in image_exts:
                msg_type = 'image'
            elif mime_type.startswith('video/') or ext in video_exts:
                msg_type = 'video'

        unique_filename = str(uuid.uuid4()) + ext
        os.makedirs(upload_folder, exist_ok=True)
        file.save(os.path.join(upload_folder, unique_filename))
        file_path = unique_filename
        if not b:
            b = '🎵 Sesli Mesaj' if msg_type == 'audio' else filename
    elif story_id:
        msg_type = 'story'
        b = story_id
        story = Story.query.get(int(story_id))
        if story:
            file_path = story.image_file
    elif not icerik_temiz_mi(b):
        return jsonify({'success':False, 'error': 'Küfür yasak'})
    if not b:
        return jsonify({'success':False})
    m = Message(sender_id=current_user.id, recipient_id=rid, body=b, msg_type=msg_type, file_path=file_path)
    db.session.add(m)
    db.session.commit()
    recipient = User.query.get(rid)
    msg_data = {'id': m.id, 'body': m.body, 'sender_id': current_user.id, 'sender_name': current_user.username, 'sender_handle': current_user.handle, 'sender_pic': current_user.profile_pic, 'timestamp': m.timestamp.strftime('%H:%M'), 'msg_type': msg_type, 'story_img': file_path, 'file_path': file_path}
    socketio.emit('receive_message', msg_data, room=recipient.username)
    return jsonify({'success':True, 'message': msg_data})

@main.route('/notes')
@login_required
def notes_pool():
    dept_filter = request.args.get('dept')
    sort_by = request.args.get('sort', 'newest')
    search_query = request.args.get('q', '').strip()
    query = Note.query.filter_by(is_approved=True)
    if dept_filter:
        query = query.filter_by(department=dept_filter)
    if search_query:
        like_query = f"%{search_query}%"
        query = query.filter(or_(Note.title.ilike(like_query), Note.course_code.ilike(like_query)))
    if sort_by == 'popular':
        query = query.order_by(Note.downloads.desc())
    elif sort_by == 'rated':
        query = query.order_by(Note.rating_sum.desc())
    else:
        query = query.order_by(Note.date_posted.desc())
    notes = query.all()
    return render_template('notes.html', notes=notes, selected_dept=dept_filter, current_sort=sort_by, search_query=search_query)

@main.route('/rate_note/<int:note_id>/<int:score>', methods=['POST'])
@login_required
def rate_note(note_id, score):
    if score < 1 or score > 5:
        return jsonify({'success': False, 'error': 'Geçersiz puan.'})
    note = Note.query.get_or_404(note_id)
    existing_vote = NoteVote.query.filter_by(user_id=current_user.id, note_id=note_id).first()
    if existing_vote:
        return jsonify({'success': False, 'error': 'Zaten oy verdin!'})
    new_vote = NoteVote(user_id=current_user.id, note_id=note_id, score=score)
    note.rating_sum += score
    note.rating_count += 1
    db.session.add(new_vote)
    db.session.commit()
    return jsonify({'success': True, 'new_average': note.average_rating, 'count': note.rating_count})

@main.route('/report/<string:type>/<int:id>', methods=['POST'])
@login_required
def report_content(type, id):
    if type == 'post':
        item = Post.query.get_or_404(id)
    elif type == 'comment':
        item = Comment.query.get_or_404(id)
    elif type == 'note':
        item = Note.query.get_or_404(id)
    else:
        return jsonify({'success': False, 'message': 'Hata'})
    item.report_count += 1
    db.session.commit()
    return jsonify({'success': True, 'message': 'Şikayet yönetime iletildi.'})

@main.route('/upload_note', methods=['POST'])
@login_required
def upload_note():
    if 'note_file' not in request.files:
        flash('Dosya seçilmedi.', 'danger')
        return redirect(url_for('main.notes_pool'))
    file = request.files['note_file']
    if not file or not file.filename:
        flash('Geçersiz dosya.', 'danger')
        return redirect(url_for('main.notes_pool'))

    title = request.form.get('title', '').strip()
    course_code = request.form.get('course_code', '').strip()
    department = request.form.get('department', '').strip()
    description = request.form.get('description', '').strip()

    if not title or not course_code or not department:
        flash('Başlık, ders kodu ve bölüm alanları zorunludur.', 'danger')
        return redirect(url_for('main.notes_pool'))

    # Uzantı kontrolü
    if '.' not in file.filename:
        flash('Uzantısız dosya yüklenemez.', 'danger')
        return redirect(url_for('main.notes_pool'))
    file_ext = file.filename.rsplit('.', 1)[1].lower()
    if file_ext not in ALLOWED_NOTE_EXTENSIONS:
        flash(f'İzin verilmeyen dosya türü: .{file_ext}. Sadece PDF, TXT, DOC, DOCX, PPT, PPTX yüklenebilir.', 'danger')
        return redirect(url_for('main.notes_pool'))

    # Boyut ölçümü
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    file.seek(0)
    file_size_str = get_file_size_str(file_length)

    filename = secrets.token_hex(8) + '.' + file_ext
    save_path = os.path.join(current_app.config['UPLOAD_FOLDER_NOTES'], filename)
    file.save(save_path)

    # Güvenlik taraması (magic bytes + boyut + içerik)
    is_safe, scan_msg = scan_file_safety(save_path, file_ext)
    if not is_safe:
        os.remove(save_path)
        flash('Güvenlik taraması başarısız: ' + scan_msg, 'danger')
        return redirect(url_for('main.notes_pool'))

    new_note = Note(
        title=title, course_code=course_code.upper(), department=department,
        description=description, file_path=filename, file_type=file_ext,
        file_size=file_size_str, author=current_user,
        is_approved=False
    )
    db.session.add(new_note)
    db.session.commit()
    flash('Notun incelemeye alındı! Onaylandıktan sonra havuzda görünecek ve +10 puan kazanacaksın 🎓', 'success')
    return redirect(url_for('main.notes_pool'))

@main.route('/download_note/<int:note_id>')
@login_required
def download_note(note_id):
    note = Note.query.get_or_404(note_id)
    note.downloads += 1
    db.session.commit()
    notes_folder = os.path.join(current_app.root_path, 'static', 'note_files')
    return send_from_directory(notes_folder, note.file_path, as_attachment=True)

@main.route('/delete_note/<int:note_id>', methods=['POST'])
@login_required
def delete_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Yetkisiz'}), 403
    file_path = os.path.join(current_app.root_path, 'static', 'note_files', note.file_path)
    if os.path.exists(file_path):
        os.remove(file_path)
    db.session.delete(note)
    db.session.commit()
    return jsonify({'success': True})

@main.route('/edit_note/<int:note_id>', methods=['POST'])
@login_required
def edit_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Yetkisiz'}), 403
    note.title       = request.form.get('title',       note.title).strip()
    note.course_code = request.form.get('course_code', note.course_code).strip()
    note.department  = request.form.get('department',  note.department).strip()
    note.description = request.form.get('description', note.description or '').strip()
    db.session.commit()
    return jsonify({'success': True})

@main.route('/upload_story', methods=['POST'])
@login_required
def upload_story():
    image = request.files.get('story_image')
    ALLOWED_STORY_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}
    def allowed_story_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_STORY_EXTENSIONS
    if image and allowed_story_file(image.filename):
        filename = optimize_and_save_image(image, current_app.config['STORY_UPLOAD_FOLDER'], max_size=(1080, 1920))
        new_story = Story(image_file=filename, author=current_user)
        db.session.add(new_story)
        db.session.commit()
        flash("Hikayen paylaşıldı!", "success")
    else:
        flash("Geçersiz dosya türü! Sadece Resim veya Video atabilirsin.", "danger")
    return redirect(url_for('main.index'))

@main.route('/delete_message/<int:message_id>')
@login_required
def delete_message(message_id):
    msg = Message.query.get_or_404(message_id)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if msg.sender_id == current_user.id or msg.recipient_id == current_user.id:
        db.session.delete(msg)
        db.session.commit()
        if is_ajax:
            return jsonify({'success': True})
        return redirect(request.referrer)
    else:
        if is_ajax:
            return jsonify({'success': False, 'error': 'Yetki yok'})
        flash("Bu mesajı silme yetkiniz yok!", "danger")
        return redirect(url_for('main.messages_inbox'))
    
@main.route('/delete_conversation/<int:partner_id>')
@login_required
def delete_conversation(partner_id):
    messages = Message.query.filter(or_((Message.sender_id == current_user.id) & (Message.recipient_id == partner_id), (Message.sender_id == partner_id) & (Message.recipient_id == current_user.id))).all()
    for msg in messages:
        db.session.delete(msg)
    db.session.commit()
    flash("Sohbet ve tüm mesajlar silindi.", "info")
    return redirect(url_for('main.messages_inbox'))

@main.route('/block_user/<int:user_id>', methods=['POST'])
@login_required
def block_user(user_id):
    target = User.query.get_or_404(user_id)
    if target == current_user:
        return jsonify({'success': False, 'error': 'Kendinizi engelleyemezsiniz.'})
    if current_user.is_blocking(target):
        current_user.unblock_user(target)
        db.session.commit()
        return jsonify({'success': True, 'blocked': False, 'message': f'@{target.handle} engellemesi kaldırıldı.'})
    else:
        current_user.block_user(target)
        db.session.commit()
        return jsonify({'success': True, 'blocked': True, 'message': f'@{target.handle} engellendi.'})

@main.route('/submit_feedback', methods=['POST'])
@login_required
def submit_feedback():
    type = request.form.get('type')
    message = request.form.get('message')
    if type and message:
        fb = Feedback(user_id=current_user.id, type=type, message=message)
        db.session.add(fb)
        db.session.commit()
        flash("Geri bildiriminiz alındı, teşekkürler!", "success")
    return redirect(request.referrer or url_for('main.index'))

@main.route('/mark_story_seen/<int:story_id>', methods=['POST'])
@login_required
def mark_story_seen(story_id):
    story = Story.query.get_or_404(story_id)
    if current_user not in story.viewers:
        story.viewers.append(current_user)
        db.session.commit()
    return jsonify({"success": True})

@main.route('/delete_story/<int:story_id>')
@login_required
def delete_story(story_id):
    story = Story.query.get_or_404(story_id)
    if story.author != current_user:
        flash("Bu hikayeyi silme yetkiniz yok!", "danger")
        return redirect(url_for('main.index'))
    try:
        file_path = os.path.join(current_app.config['STORY_UPLOAD_FOLDER'], story.image_file)
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        pass
    db.session.delete(story)
    db.session.commit()
    flash("Hikaye silindi.", "info")
    return redirect(url_for('main.index'))

@main.route('/vote_poll/<int:poll_id>/<int:option_id>', methods=['POST'])
@login_required
def vote_poll(poll_id, option_id):
    poll = Poll.query.get_or_404(poll_id)
    option = PollOption.query.get_or_404(option_id)
    if poll.user_voted(current_user):
        return jsonify({"success": False, "message": "Zaten oy kullandınız!"})
    vote = PollVote(user_id=current_user.id, poll_id=poll.id, option_id=option.id)
    option.vote_count += 1
    db.session.add(vote)
    db.session.commit()
    return jsonify({"success": True})

@main.route('/send_audio', methods=['POST'])
@login_required
def send_audio():
    if 'audio' not in request.files:
        return jsonify({'success': False, 'error': 'Ses dosyası yok'})
    file = request.files['audio']
    recipient_id = request.form.get('recipient_id')
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Dosya ismi boş'})

    from werkzeug.utils import secure_filename
    import uuid

    allowed_ext = {'webm', 'wav', 'ogg', 'mp3', 'm4a'}
    orig_name = secure_filename(file.filename)
    ext = os.path.splitext(orig_name)[1].lower().lstrip('.')
    if ext not in allowed_ext:
        filename = f"{uuid.uuid4()}.webm"
    else:
        filename = f"{uuid.uuid4()}.{ext}"

    upload_folder = current_app.config.get('AUDIO_UPLOAD_FOLDER', os.path.join('static', 'audio_files'))
    os.makedirs(upload_folder, exist_ok=True)
    save_path = os.path.join(upload_folder, filename)
    file.save(save_path)

    new_msg = Message(sender_id=current_user.id, recipient_id=recipient_id, body="🎤 Sesli Mesaj", msg_type='audio', file_path=filename)
    db.session.add(new_msg)
    db.session.commit()

    message_data = {'id': new_msg.id, 'body': "🎤 Sesli Mesaj", 'sender_id': current_user.id, 'sender_pic': current_user.profile_pic, 'timestamp': new_msg.timestamp.strftime('%H:%M'), 'msg_type': 'audio', 'file_path': filename}
    try:
        recipient = User.query.get(recipient_id)
        if recipient:
            socketio.emit('receive_message', message_data, room=recipient.username)
    except Exception:
        # emit hatası uygulamayı bozmasın
        pass

    return jsonify({'success': True, 'message': message_data})

@main.route('/reels')
@login_required
def reels():
    video_posts = Post.query.filter(or_(Post.image_file.ilike('%.mp4'), Post.image_file.ilike('%.mov'), Post.image_file.ilike('%.avi'), Post.image_file.ilike('%.webm'), Post.image_file.ilike('%.mkv'))).order_by(Post.date_posted.desc()).all()
    return render_template('reels.html', posts=video_posts)

@main.route('/adverts', methods=['GET', 'POST'])
@login_required
def adverts():
    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        description = request.form.get('description')
        contact = request.form.get('contact') 
        if title and description and category:
            new_adv = Advert(title=title, category=category, description=description, contact_info=contact, author=current_user)
            db.session.add(new_adv)
            db.session.commit()
            flash("İlanın başarıyla yayınlandı!", "success")
            return redirect(url_for('main.adverts'))
    cat_filter = request.args.get('category')
    if cat_filter:
        ads = Advert.query.filter_by(category=cat_filter).order_by(Advert.date_posted.desc()).all()
    else:
        ads = Advert.query.order_by(Advert.date_posted.desc()).all()
    return render_template('adverts.html', adverts=ads, selected_cat=cat_filter)

@main.route('/delete_advert/<int:adv_id>')
@login_required
def delete_advert(adv_id):
    adv = Advert.query.get_or_404(adv_id)
    if adv.author != current_user and not current_user.is_admin:
        flash("Bu ilanı silme yetkiniz yok!", "danger")
        return redirect(url_for('main.adverts'))
    db.session.delete(adv)
    db.session.commit()
    flash("İlan kaldırıldı.", "info")
    return redirect(url_for('main.adverts'))

@main.route('/edit_advert/<int:adv_id>', methods=['POST'])
@login_required
def edit_advert(adv_id):
    adv = Advert.query.get_or_404(adv_id)
    if adv.author != current_user and not current_user.is_admin:
        flash("Bu ilanı düzenleme yetkiniz yok!", "danger")
        return redirect(url_for('main.adverts'))
    adv.title = request.form.get('title')
    adv.category = request.form.get('category')
    adv.description = request.form.get('description')
    adv.contact_info = request.form.get('contact')
    db.session.commit()
    flash("İlan başarıyla güncellendi.", "success")
    return redirect(url_for('main.adverts'))

@main.route('/ulasim')
@login_required
def ulasim():
    if not current_user.is_verified:
        return redirect(url_for('auth.verify', email=current_user.email))
    return render_template('ulasim.html')

@main.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@main.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        from werkzeug.security import check_password_hash, generate_password_hash
        
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not check_password_hash(current_user.password, current_password):
            flash("Mevcut şifre hatalı!", "danger")
            return render_template('change_password.html')
        
        if len(new_password) < 6:
            flash("Yeni şifre en az 6 karakter olmalı!", "danger")
            return render_template('change_password.html')
        
        if new_password != confirm_password:
            flash("Şifreler eşleşmiyor!", "danger")
            return render_template('change_password.html')
        
        current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
        db.session.commit()
        flash("Şifren başarıyla değiştirildi!", "success")
        return redirect(url_for('main.settings'))
    
    return render_template('change_password.html')

@main.route('/blocked_users')
@login_required
def blocked_users():
    blocked = current_user.blocking.all()
    return render_template('blocked_users.html', blocked_users=blocked)

@main.route('/terms')
def terms():
    from datetime import date
    return render_template('terms.html', today=date.today().strftime('%d.%m.%Y'))

@main.route('/privacy')
def privacy():
    from datetime import date
    return render_template('privacy.html', today=date.today().strftime('%d.%m.%Y'), contact_email='support@ytusocial.com')


@main.route('/sitemap.xml')
def sitemap():
    return send_from_directory(current_app.root_path, 'sitemap.xml', mimetype='application/xml')


@main.route('/robots.txt')
def robots_txt():
    sitemap_url = url_for('main.sitemap', _external=True)
    robots_text = f'User-agent: *\nAllow: /\nSitemap: {sitemap_url}\n'
    return current_app.response_class(robots_text, mimetype='text/plain')

@main.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    from werkzeug.security import check_password_hash
    from flask_login import logout_user
    
    try:
        data = request.get_json() or {}
        password = data.get('password', '')
        
        if not check_password_hash(current_user.password, password):
            return jsonify({'success': False, 'message': 'Şifre hatalı!'})
        
        user_id = current_user.id
        
        # Tüm post'ları sil
        posts = Post.query.filter_by(author_id=user_id).all()
        for post in posts:
            _purge_post_tree(post)
        
        # Tüm story'leri sil
        Story.query.filter_by(author_id=user_id).delete()
        
        # Tüm takip ilişkilerini sil
        current_user.followers.clear()
        current_user.following.clear()
        
        # Tüm mesajları sil
        Message.query.filter(
            (Message.sender_id == user_id) | (Message.recipient_id == user_id)
        ).delete()
        
        # Tüm yorum/beğenleri sil
        Comment.query.filter_by(author_id=user_id).delete()
        likes.delete().where(likes.c.user_id == user_id)
        
        # Hesabı kapat (silme yerine is_active = False yapabilirsin)
        db.session.delete(current_user)
        db.session.commit()
        
        logout_user()
        return jsonify({'success': True, 'message': 'Hesab silindi!'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Bir hata oluştu: ' + str(e)})

