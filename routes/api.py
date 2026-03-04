from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from extensions import db, socketio
from models import User, Story, Post, Poll, PollOption, Comment, ClubVote
from utils import optimize_and_save_image, allowed_file, create_notification
from sqlalchemy import or_
import re

api = Blueprint('api', __name__)

@api.route('/api/get_share_users')
@login_required
def get_share_users():
    users = User.query.filter(User.id != current_user.id).all()
    user_list = []
    for u in users:
        user_list.append({
            'id': u.id,
            'username': u.username,
            'profile_pic': u.profile_pic,
            'department': u.department
        })
    return jsonify({'success': True, 'users': user_list})

@api.route('/api/get_story/<int:story_id>')
@login_required
def get_story_api(story_id):
    story = Story.query.get(story_id)
    if not story:
        return jsonify({'success': False, 'error': 'Hikaye bulunamadı veya süresi dolmuş.'})
    story_data = {
        'id': story.id,
        'file': story.image_file,
        'timestamp': story.date_posted.strftime('%H:%M'),
        'seen': False,
        'viewers': []
    }
    user_data = {
        'username': story.author.username,
        'profile_pic': story.author.profile_pic,
        'is_owner': (story.author == current_user)
    }
    return jsonify({'success': True, 'story': story_data, 'user': user_data})

@api.route('/api/system_stats')
@login_required
def system_stats():
    import psutil
    from datetime import datetime
    from utils import ONLINE_USERS
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    active = len(ONLINE_USERS)
    return jsonify({"cpu": cpu, "ram": ram, "active": active, "time": datetime.now().strftime('%H:%M:%S')})

@api.route('/api/share_post', methods=['POST'])
@login_required
def share_post_api():
    post_content = request.form.get('content')
    image = request.files.get('image')
    doc = request.files.get('doc')
    poll_opt1 = request.form.get('poll_opt1')
    poll_opt2 = request.form.get('poll_opt2')

    if post_content or image or doc:
        filename = None
        file_obj = image if image else doc
        if file_obj and allowed_file(file_obj.filename):
            filename = optimize_and_save_image(file_obj, current_app.config['POST_UPLOAD_FOLDER'])

        new_post = Post(content=post_content, image_file=filename, author=current_user)
        db.session.add(new_post)
        
        has_poll = False
        if poll_opt1 and poll_opt2:
            has_poll = True
            new_poll = Poll(post=new_post)
            db.session.add(new_poll)
            db.session.add(PollOption(text=poll_opt1, poll=new_poll))
            db.session.add(PollOption(text=poll_opt2, poll=new_poll))
        
        db.session.commit()

        post_data = {
            'id': new_post.id,
            'content': new_post.content,
            'author_name': current_user.username,
            'author_pic': current_user.profile_pic,
            'author_dept': current_user.department or 'Bölüm Yok',
            'author_handle': current_user.handle,
            'date': new_post.date_posted.strftime('%H:%M'),
            'image_file': new_post.image_file,
            'is_video': new_post.is_video() if new_post.image_file else False,
            'has_poll': has_poll,
            'poll_id': new_post.poll.id if has_poll else None,
            'poll_options': [{'id': opt.id, 'text': opt.text} for opt in new_post.poll.options] if has_poll else []
        }
        socketio.emit('new_global_post', post_data)
        return jsonify({'success': True})

    return jsonify({'success': False, 'error': 'İçerik boş'})

@api.route('/api/add_comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment_api(post_id):
    post = Post.query.get_or_404(post_id)
    text = request.form.get('comment_text')
    
    if text:
        comment = Comment(text=text, author=current_user, post=post)
        db.session.add(comment)
        db.session.commit()
        
        mentions = re.findall(r"@(\w+)", text)
        for handle in set(mentions):
            mentioned_user = User.query.filter_by(handle=handle).first()
            if mentioned_user:
                create_notification(mentioned_user, current_user, 'mentioned', post)
        
        comment_data = {
            'id': comment.id,
            'text': comment.text,
            'author_name': current_user.username,
            'author_pic': current_user.profile_pic,
            'date': comment.date_posted.strftime('%H:%M')
        }
        return jsonify({'success': True, 'comment': comment_data})
    return jsonify({'success': False})

@api.route('/api/get_comments/<int:post_id>')
@login_required
def get_comments_api(post_id):
    post = Post.query.get_or_404(post_id)
    comments_data = []
    for c in post.comments:
        comments_data.append({
            'id': c.id,
            'text': c.text,
            'author_name': c.author.username,
            'author_pic': c.author.profile_pic,
            'timestamp': c.date_posted.strftime('%H:%M')
        })
    return jsonify({'success': True, 'comments': comments_data})

@api.route('/api/search_users')
@login_required
def api_search_users():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'success': True, 'users': []})
    
    search_term = f"%{query}%"
    users = User.query.filter(
        or_(
            User.username.ilike(search_term),
            User.handle.ilike(search_term)
        )
    ).limit(5).all()
    
    results = []
    for u in users:
        results.append({
            'username': u.username,
            'handle': u.handle,
            'profile_pic': u.profile_pic,
            'department': u.department
        })
    
    return jsonify({'success': True, 'users': results})

@api.route('/api/follow_user/<int:user_id>', methods=['POST'])
@login_required
def api_follow_user(user_id):
    user = User.query.get_or_404(user_id)
    if user == current_user:
        return jsonify({'success': False, 'error': 'Kendini takip edemezsin'})
    
    if current_user.is_following(user):
        current_user.unfollow(user)
        action = 'unfollowed'
    else:
        current_user.follow(user)
        create_notification(user, current_user, 'followed')
        action = 'followed'
        
    db.session.commit()
    return jsonify({'success': True, 'action': action})

@api.route('/api/my_votes')
@login_required
def my_votes():
    user_votes = [v.club_id for v in ClubVote.query.filter_by(user_id=current_user.id).all()]
    return jsonify({'success': True, 'votes': user_votes})