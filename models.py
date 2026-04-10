from extensions import db, login_manager
from flask_login import UserMixin
from datetime import datetime, timedelta
from sqlalchemy.exc import SQLAlchemyError
from utils import get_turkey_time

followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

blocked_users = db.Table('blocked_users',
    db.Column('blocker_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('blocked_id', db.Integer, db.ForeignKey('user.id'))
)

story_views = db.Table('story_views',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('story_id', db.Integer, db.ForeignKey('story.id'))
)

likes = db.Table('likes',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'))
)

club_followers = db.Table('club_followers',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('club_id', db.Integer, db.ForeignKey('club.id'))
)

class SavedPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    date_saved = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user = db.relationship('User', back_populates='saved_posts')
    post = db.relationship('Post')

class Poll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    options = db.relationship('PollOption', backref='poll', lazy=True, cascade="all, delete-orphan")
    votes = db.relationship('PollVote', backref='poll', lazy=True, cascade="all, delete-orphan")

    def user_voted(self, user):
        return PollVote.query.filter_by(user_id=user.id, poll_id=self.id).first()
    def total_votes(self):
        return sum(opt.vote_count for opt in self.options)

class Club(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    logo_file = db.Column(db.String(255), nullable=False, default='default_club.jpg')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    leader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    leader = db.relationship('User', foreign_keys=[leader_id], backref='led_clubs')

    posts = db.relationship('ClubPost', backref='club', lazy=True, cascade="all, delete-orphan")
    followers = db.relationship('User', secondary=club_followers, backref=db.backref('followed_clubs', lazy='dynamic'))
    vote_records = db.relationship('ClubVote', backref='club', lazy=True)

    @property
    def votes(self):
        return len(self.vote_records)

    def total_votes(self):
        return self.votes

class ClubPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_file = db.Column(db.String(255), nullable=True)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    club_id = db.Column(db.Integer, db.ForeignKey('club.id'), nullable=False)

    def is_video(self):
        if not self.image_file: return False
        video_exts = ['mp4', 'mov', 'avi', 'webm']
        return any(self.image_file.lower().endswith(ext) for ext in video_exts)

class ClubVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    club_id = db.Column(db.Integer, db.ForeignKey('club.id'), nullable=False)
    vote_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class PollOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(100), nullable=False)
    vote_count = db.Column(db.Integer, default=0)
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False)
    def percentage(self):
        total = self.poll.total_votes()
        if total == 0: return 0
        return int((self.vote_count / total) * 100)

class PollVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey('poll_option.id'), nullable=False)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    username = db.Column(db.String(50), nullable=True)
    handle = db.Column(db.String(30), unique=True, nullable=True)
    stories = db.relationship('Story', backref='author', lazy=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_moderator = db.Column(db.Boolean, default=False)
    department = db.Column(db.String(100), nullable=True)
    score = db.Column(db.Integer, default=0)
    bio = db.Column(db.String(200), nullable=True)
    profile_pic = db.Column(db.String(200), default='img/default_avatar.png')
    is_verified = db.Column(db.Boolean, default=False)
    otp_code = db.Column(db.String(6))
    otp_expires_at = db.Column(db.DateTime, nullable=True)
    ban_expiration = db.Column(db.DateTime, nullable=True)
    is_banned = db.Column(db.Boolean, default=False)
    
    posts = db.relationship('Post', backref='author', lazy=True)
    image_file = db.Column(db.String(255), nullable=True) 
    comments = db.relationship('Comment', backref='author', lazy=True)
    
    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    messages_received = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient', lazy='dynamic')
    saved_posts = db.relationship('SavedPost', back_populates='user', lazy=True, cascade="all, delete-orphan")

    @property
    def display_name(self):
        raw_username = (self.username or '').strip()
        if raw_username and raw_username.lower() not in {'none', 'null'}:
            return raw_username

        handle_value = (self.handle or '').strip()
        if not handle_value:
            handle_value = (self.email or '').split('@')[0].strip()

        if handle_value:
            return handle_value.replace('.', ' ').strip()

        return ''

    followed = db.relationship(
        'User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic'
    )

    blocking = db.relationship(
        'User', secondary=blocked_users,
        primaryjoin=(blocked_users.c.blocker_id == id),
        secondaryjoin=(blocked_users.c.blocked_id == id),
        backref=db.backref('blocked_by', lazy='dynamic'), lazy='dynamic'
    )

    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)
    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)
    def is_following(self, user):
        return self.followed.filter(followers.c.followed_id == user.id).count() > 0
    def has_saved(self, post):
        return SavedPost.query.filter_by(user_id=self.id, post_id=post.id).first() is not None
    def save_post(self, post):
        if not self.has_saved(post):
            s = SavedPost(user_id=self.id, post_id=post.id)
            db.session.add(s)
    def unsave_post(self, post):
        s = SavedPost.query.filter_by(user_id=self.id, post_id=post.id).first()
        if s: db.session.delete(s)

    def block_user(self, user):
        if not self.is_blocking(user):
            self.blocking.append(user)
    def unblock_user(self, user):
        if self.is_blocking(user):
            self.blocking.remove(user)
    def is_blocking(self, user):
        return self.blocking.filter(blocked_users.c.blocked_id == user.id).count() > 0

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=True)
    poll = db.relationship('Poll', uselist=False, backref='post', cascade="all, delete-orphan")
    date_posted = db.Column(db.DateTime, nullable=False, default=get_turkey_time)
    image_file = db.Column(db.String(255), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    club_id = db.Column(db.Integer, db.ForeignKey('club.id'), nullable=True)  # Kulüp duyurusu ise set edilir
    club = db.relationship('Club', foreign_keys=[club_id], backref=db.backref('feed_posts', lazy=True))
    
    liked_by = db.relationship('User', secondary=likes, backref=db.backref('liked_posts', lazy='dynamic'))
    comments = db.relationship('Comment', backref='post', lazy=True, cascade="all, delete-orphan")
    
    repost_of_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True)
    repost_of = db.relationship('Post', remote_side=[id], backref=db.backref('reposts', cascade='all, delete-orphan'))
    
    report_count = db.Column(db.Integer, default=0)

    def has_reposted(self, user):
        if not user.is_authenticated: return False
        return Post.query.filter_by(user_id=user.id, repost_of_id=self.id).first() is not None

    def is_video(self):
        if not self.image_file: return False
        video_exts = ['mp4', 'mov', 'avi', 'webm']
        return any(self.image_file.lower().endswith(ext) for ext in video_exts)

    def get_file_type(self):
        if not self.image_file: return 'none'
        ext = self.image_file.rsplit('.', 1)[1].lower() if '.' in self.image_file else ''
        if ext in ['mp4', 'mov', 'avi', 'webm']: return 'video'
        if ext in ['png', 'jpg', 'jpeg', 'gif']: return 'image'
        return 'file'

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=get_turkey_time)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    report_count = db.Column(db.Integer, default=0)

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    course_code = db.Column(db.String(20), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)
    file_size = db.Column(db.String(20), default="0 KB")
    
    downloads = db.Column(db.Integer, default=0)
    rating_sum = db.Column(db.Integer, default=0)
    rating_count = db.Column(db.Integer, default=0)
    report_count = db.Column(db.Integer, default=0)
    is_approved = db.Column(db.Boolean, default=False)
    
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    author = db.relationship('User', backref='notes', lazy=True)
    
    @property
    def average_rating(self):
        if self.rating_count == 0: return 0
        return round(self.rating_sum / self.rating_count, 1)

class Advert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    contact_info = db.Column(db.String(100), nullable=True)
    
    date_posted = db.Column(db.DateTime, nullable=False, default=get_turkey_time)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    author = db.relationship('User', backref='adverts', lazy=True)

class NoteVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    note_id = db.Column(db.Integer, db.ForeignKey('note.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    verb = db.Column(db.String(50))
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True)
    timestamp = db.Column(db.DateTime, default=get_turkey_time)
    is_read = db.Column(db.Boolean, default=False)
    actor = db.relationship('User', foreign_keys=[actor_id], lazy=True)
    post = db.relationship('Post', foreign_keys=[post_id], lazy=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    body = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    msg_type = db.Column(db.String(10), default='text')
    file_path = db.Column(db.String(255), nullable=True)

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False) # Öneri, Şikayet, Diğer
    message = db.Column(db.Text, nullable=False)
    date_sent = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user = db.relationship('User', backref='feedbacks', lazy=True)

class Story(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_file = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    viewers = db.relationship('User', secondary=story_views, backref=db.backref('viewed_stories', lazy='dynamic'), lazy='dynamic')
    
    def is_expired(self):
        return datetime.utcnow() > self.timestamp + timedelta(days=1)

class StoryView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('story.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    story = db.relationship('Story', backref=db.backref('view_records', lazy='dynamic', cascade='all, delete-orphan'))
    user = db.relationship('User', backref=db.backref('story_views', lazy='dynamic'))
    
    __table_args__ = (db.UniqueConstraint('story_id', 'user_id', name='unique_story_view'),)

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except (TypeError, ValueError):
        return None
    except SQLAlchemyError:
        db.session.remove()
        return None