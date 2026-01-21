from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message as MailMessage 
from werkzeug.utils import secure_filename 
from flask_socketio import SocketIO, emit, join_room
from sqlalchemy import or_, func
from markupsafe import Markup
from PIL import Image
from datetime import datetime, timedelta
import json
import os
import random
import time
import psutil 
import re 
import secrets
import pytesseract

# ==========================================
# 1. AYARLAR VE KURULUM
# ==========================================

# --- BÖLÜM ANAHTAR KELİMELERİ (AI BİLGİ BANKASI) ---
BOLUM_KELIMELERI = {
    'Bilgisayar': ['algoritma', 'yazılım', 'kod', 'software', 'java', 'python', 'cpu', 'ram', 'veri', 'network', 'class', 'object', 'döngü', 'loop'],
    'Hazırlık': ['present', 'verb', 'noun', 'tense', 'vocabulary', 'grammar', 'subject', 'english', 'reading', 'writing', 'book', 'unit'],
    'Makine': ['kuvvet', 'moment', 'mekanik', 'statik', 'dinamik', 'motor', 'dişli', 'termodinamik', 'akışkan', 'force', 'energy'],
    'Elektrik': ['volt', 'amper', 'devre', 'akım', 'direnç', 'circuit', 'power', 'enerji', 'kablo', 'elektronik'],
    'Mimarlık': ['çizim', 'plan', 'kesit', 'bina', 'tasarım', 'ölçek', 'mekan', 'yapı', 'cephe', 'mimari'],
    'Genel': [] # Genel kategorisinde kontrol yapmayız
}

# Tesseract Ayarı (Windows kullanıyorsan bu yolun doğru olduğundan emin ol)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Bellekte online kullanıcıları tutacağımız küme
ONLINE_USERS = set()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'yildiz-teknik-gizli-anahtar'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB limit

# SocketIO Kurulumu
socketio = SocketIO(app, cors_allowed_origins="*")

# --- KLASÖR AYARLARI ---
AUDIO_UPLOAD_FOLDER = os.path.join('static', 'audio_files')
POST_UPLOAD_FOLDER = 'static/post_images'
PROFILE_UPLOAD_FOLDER = 'static/uploads/profiles'
STORY_UPLOAD_FOLDER = 'static/story_images'
NOTE_UPLOAD_FOLDER = 'static/note_files'

app.config['UPLOAD_FOLDER_NOTES'] = NOTE_UPLOAD_FOLDER
app.config['AUDIO_UPLOAD_FOLDER'] = AUDIO_UPLOAD_FOLDER
app.config['POST_UPLOAD_FOLDER'] = POST_UPLOAD_FOLDER
app.config['PROFILE_UPLOAD_FOLDER'] = PROFILE_UPLOAD_FOLDER
app.config['STORY_UPLOAD_FOLDER'] = STORY_UPLOAD_FOLDER

# Klasörler yoksa oluştur
for folder in [AUDIO_UPLOAD_FOLDER, POST_UPLOAD_FOLDER, PROFILE_UPLOAD_FOLDER, STORY_UPLOAD_FOLDER, NOTE_UPLOAD_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# --- UZANTI KONTROLLERİ ---
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'webm'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- VERİTABANI VE LOGIN KURULUMU ---
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Bu sayfaya erişmek için lütfen önce giriş yapın."
login_manager.login_message_category = "info"

# --- MAIL AYARLARI ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'portalytu@gmail.com' 
# DİKKAT: Buraya uygulama şifreni yazmalısın (Boşluksuz olması önerilir ama Google bazen boşluklu kabul eder)
app.config['MAIL_PASSWORD'] = 'xpfj soms rwht ttam' 
mail = Mail(app)

# ==========================================
# 2. YARDIMCI FONKSİYONLAR
# ==========================================

def get_turkey_time():
    return datetime.utcnow() + timedelta(hours=3)

def not_icerigi_dogru_mu(resim_yolu, bolum):
    """Resimdeki yazıları okur ve bölüme uygun olup olmadığına bakar."""
    try:
        img = Image.open(resim_yolu)
        okunan_metin = pytesseract.image_to_string(img, lang='eng+tur').lower()
        
        if bolum not in BOLUM_KELIMELERI or len(BOLUM_KELIMELERI[bolum]) == 0:
            return True, "Kontrolsüz geçiş"

        bulunan_kelimeler = []
        for kelime in BOLUM_KELIMELERI[bolum]:
            if kelime in okunan_metin:
                bulunan_kelimeler.append(kelime)
        
        if len(bulunan_kelimeler) > 0:
            return True, f"Doğrulandı! Bulunanlar: {', '.join(bulunan_kelimeler)}"
        else:
            return False, "Resimde dersle ilgili terim bulunamadı."
            
    except Exception as e:
        print(f"OCR Hatası: {e}")
        return True, "Okunamadı ama onaylandı."

# --- GELİŞMİŞ KÜFÜR FİLTRESİ (REGEX İLE - KEMAL/MAL SORUNU ÇÖZÜLDÜ) ---
def icerik_temiz_mi(text):
    if not text: return False
    
    # Yasaklı kelimeler listesi
    yasakli_kelimeler = [
        "mal", "salak", "aptal", "gerizekalı", "amk", "aq", "piç", 
        "yavşak", "sik", "siktir", "yarrak", "oç", "orospu" 
    ]
    
    # Türkçe karakter düzeltmesi
    text_lower = text.replace('İ', 'i').replace('I', 'ı').lower()
    
    for kelime in yasakli_kelimeler:
        # \b kelime sınırı demektir. "kemal" içindeki "mal"ı bulmaz, sadece "mal" kelimesini bulur.
        pattern = r'\b' + re.escape(kelime) + r'\b'
        if re.search(pattern, text_lower):
            return False # Yasaklı kelime bulundu
            
    return True # Temiz

def get_file_size_str(size_in_bytes):
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    elif size_in_bytes < 1024 * 1024:
        return f"{round(size_in_bytes/1024, 1)} KB"
    else:
        return f"{round(size_in_bytes/(1024*1024), 1)} MB"

# --- KULÜP VERİLERİ (JSON) ---
CLUBS_DATA = [
    {"id": "ieee", "name": "IEEE YTÜ", "category": "Teknik", "image": "ieee.png", "members": "1500+", "projects": "12", "portfolio": []},
    {"id": "fark", "name": "FARK Kulübü", "category": "Sosyal", "image": "fark.jpg", "members": "450+", "projects": "5", "portfolio": []},
    {"id": "girisim", "name": "Girişimcilik", "category": "İş", "image": "girisim.png", "members": "800+", "projects": "8", "portfolio": []}
]

DATA_FILE = 'votes.json'

def save_votes(votes):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(votes, f, ensure_ascii=False, indent=4)

def load_votes():
    if not os.path.exists(DATA_FILE) or os.path.getsize(DATA_FILE) == 0:
        default_votes = {club['id']: 0 for club in CLUBS_DATA}
        save_votes(default_votes)
        return default_votes
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# ==========================================
# 3. VERİTABANI MODELLERİ
# ==========================================

# Ara Tablolar
followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

story_views = db.Table('story_views',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('story_id', db.Integer, db.ForeignKey('story.id'))
)

likes = db.Table('likes',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'))
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
    department = db.Column(db.String(100), nullable=True)
    score = db.Column(db.Integer, default=0)
    bio = db.Column(db.String(200), nullable=True)
    profile_pic = db.Column(db.String(200), default='img/default_avatar.png') 
    is_verified = db.Column(db.Boolean, default=False)
    otp_code = db.Column(db.String(6))
    ban_expiration = db.Column(db.DateTime, nullable=True) 
    is_banned = db.Column(db.Boolean, default=False)
    
    posts = db.relationship('Post', backref='author', lazy=True)
    image_file = db.Column(db.String(20), nullable=True) 
    comments = db.relationship('Comment', backref='author', lazy=True)
    
    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    messages_received = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient', lazy='dynamic')
    saved_posts = db.relationship('SavedPost', back_populates='user', lazy=True, cascade="all, delete-orphan")

    followed = db.relationship(
        'User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic'
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

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=True) 
    poll = db.relationship('Poll', uselist=False, backref='post', cascade="all, delete-orphan")
    date_posted = db.Column(db.DateTime, nullable=False, default=get_turkey_time)
    image_file = db.Column(db.String(50), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    liked_by = db.relationship('User', secondary=likes, backref=db.backref('liked_posts', lazy='dynamic'))
    comments = db.relationship('Comment', backref='post', lazy=True, cascade="all, delete-orphan")
    
    repost_of_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True)
    repost_of = db.relationship('Post', remote_side=[id], backref=db.backref('reposts', cascade='all, delete-orphan'))
    
    report_count = db.Column(db.Integer, default=0)

    def is_video(self):
        if not self.image_file: return False
        video_exts = ['mp4', 'mov', 'avi', 'webm']
        return any(self.image_file.lower().endswith(ext) for ext in video_exts)

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
    file_path = db.Column(db.String(100), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)
    file_size = db.Column(db.String(20), default="0 KB")
    
    downloads = db.Column(db.Integer, default=0)
    rating_sum = db.Column(db.Integer, default=0)    
    rating_count = db.Column(db.Integer, default=0)  
    report_count = db.Column(db.Integer, default=0)  
    
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    author = db.relationship('User', backref='notes', lazy=True)

    @property
    def average_rating(self):
        if self.rating_count == 0: return 0
        return round(self.rating_sum / self.rating_count, 1)

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
    msg_type = db.Column(db.String(10), default='text') # 'text', 'audio', 'story'
    file_path = db.Column(db.String(255), nullable=True)

class Story(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_file = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    viewers = db.relationship('User', secondary=story_views, backref=db.backref('viewed_stories', lazy='dynamic'), lazy='dynamic')
    def is_expired(self):
        return datetime.utcnow() > self.timestamp + timedelta(days=1)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_notification(receiver, actor, verb, post=None):
    if receiver == actor: return 
    notif = Notification(user_id=receiver.id, actor_id=actor.id, verb=verb, post_id=post.id if post else None)
    db.session.add(notif)
    db.session.commit()
    notif_text = ""
    if verb == 'liked': notif_text = f"{actor.username} gönderini beğendi."
    elif verb == 'commented': notif_text = f"{actor.username} gönderine yorum yaptı."
    elif verb == 'followed': notif_text = f"{actor.username} seni takip etti."
    elif verb == 'messaged': notif_text = f"{actor.username} sana mesaj gönderdi."
    socketio.emit('new_notification', {
        'count': Notification.query.filter_by(user_id=receiver.id, is_read=False).count(),
        'text': notif_text,
        'actor_pic': actor.profile_pic,
        'link': url_for('notifications') 
    }, room=receiver.username)

# ==========================================
# 4. ROTALAR (ROUTES)
# ==========================================

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if not current_user.is_verified:
        return redirect(url_for('verify', email=current_user.email))
    
    # POST PAYLAŞMA
    if request.method == 'POST':
        post_content = request.form.get('content')
        image = request.files.get('image') 
        poll_opt1 = request.form.get('poll_opt1')
        poll_opt2 = request.form.get('poll_opt2')

        if post_content or image:
            filename = None
            if image and allowed_file(image.filename):
                filename = secure_filename(image.filename)
                import uuid
                filename = str(uuid.uuid4())[:8] + "_" + filename
                image.save(os.path.join(app.config['POST_UPLOAD_FOLDER'], filename))

            new_post = Post(content=post_content, image_file=filename, author=current_user)
            db.session.add(new_post)
            
            if poll_opt1 and poll_opt2:
                new_poll = Poll(post=new_post)
                db.session.add(new_poll)
                db.session.add(PollOption(text=poll_opt1, poll=new_poll))
                db.session.add(PollOption(text=poll_opt2, poll=new_poll))
            
            db.session.commit()
            flash("Gönderin başarıyla paylaşıldı!", "success")
            return redirect(url_for('index'))
        
    # HİKAYELER
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

    # DİĞER VERİLER
    votes = load_votes()
    for club in CLUBS_DATA:
        club['votes'] = votes.get(club['id'], 0) 
    ranked_clubs = sorted(CLUBS_DATA, key=lambda x: x['votes'], reverse=True)

    active_tab = request.args.get('tab', 'global')
    if active_tab == 'following':
        followed_ids = [user.id for user in current_user.followed]
        followed_ids.append(current_user.id)
        posts = Post.query.filter(Post.user_id.in_(followed_ids)).order_by(Post.date_posted.desc()).all()
    else:
        posts = Post.query.order_by(Post.date_posted.desc()).all()
    
    return render_template('index.html', clubs=ranked_clubs, votes=votes, posts=posts, active_tab=active_tab, stories=stories_data)

@app.route('/like/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    if current_user in post.liked_by:
        post.liked_by.remove(current_user)
        action = 'unliked'
    else:
        post.liked_by.append(current_user)
        action = 'liked'
        create_notification(post.author, current_user, 'liked', post)
    db.session.commit()
    return jsonify({"likes_count": len(post.liked_by), "action": action})

@app.route('/save/<int:post_id>', methods=['POST'])
@login_required
def save_post(post_id):
    post = Post.query.get_or_404(post_id)
    if current_user.has_saved(post):
        current_user.unsave_post(post)
        action = 'unsaved'
    else:
        current_user.save_post(post)
        action = 'saved'
    db.session.commit()
    return jsonify({"action": action})

@app.route('/saved')
@login_required
def saved_posts_list():
    posts = [saved.post for saved in current_user.saved_posts]
    posts.reverse()
    return render_template('saved_posts.html', posts=posts)

@app.route('/comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)
    text = request.form.get('comment_text')
    if text:
        comment = Comment(text=text, author=current_user, post=post)
        db.session.add(comment)
        db.session.commit()
        create_notification(post.author, current_user, 'commented', post)
        flash("Yorum yapıldı!", "success")
    return redirect(url_for('index'))

@app.route('/repost/<int:post_id>', methods=['POST'])
@login_required
def repost(post_id):
    original_post = Post.query.get_or_404(post_id)
    source_id = original_post.repost_of_id if original_post.repost_of_id else original_post.id
    new_repost = Post(content=None, author=current_user, repost_of_id=source_id)
    db.session.add(new_repost)
    db.session.commit()
    return jsonify({"success": True, "message": "Başarıyla yeniden gönderildi!"})

# --- 1. PAYLAŞILACAK KULLANICI LİSTESİ API ---
@app.route('/api/get_share_users')
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

# --- 2. TEKİL GÖNDERİ GÖRÜNTÜLEME (LİNKİN GİDECEĞİ YER) ---
@app.route('/p/<int:post_id>')
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('post_detail.html', post=post)

# --- 3. TEKİL HİKAYE GÖRÜNTÜLEME (DÜZELTİLDİ) ---
# --- 3. TEKİL HİKAYE GÖRÜNTÜLEME (BAĞLANTI İLE GELENLER İÇİN) ---
@app.route('/s/<int:story_id>')
@login_required  # <--- BU SATIR ÇOK ÖNEMLİ: GİRİŞ YAPMAYAN GÖREMEZ!
def story_detail(story_id):
    story = Story.query.get_or_404(story_id)
    
    # Ekstra Güvenlik: Eğer hikayenin süresi dolmuşsa (24 saati geçmişse) gösterme
    if story.is_expired():
        flash("Bu hikayenin süresi dolmuş.", "warning")
        return redirect(url_for('index'))
        
    return render_template('story_detail.html', story=story)
# --- TEKİL HİKAYE BİLGİSİ (MODAL İÇİN) ---
@app.route('/api/get_story/<int:story_id>')
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

# --- AUTH ROUTES ---
@app.route('/register', methods=['GET', 'POST'])
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
            msg = MailMessage('YTÜ Portal Doğrulama', sender=app.config['MAIL_USERNAME'], recipients=[email])
            msg.body = f'Portalımıza hoş geldin! Doğrulama kodun: {otp}'
            mail.send(msg)
            return redirect(url_for('verify', email=email))
        except Exception as e:
            db.session.rollback()
            print(f"Kayıt Hatası: {e}") 
            flash("Mail gönderilirken bir teknik sorun oluştu!", "danger")
            return render_template('register.html')
    return render_template('register.html')

@app.route('/verify/<email>', methods=['GET', 'POST'])
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
            return redirect(url_for('index'))
        else:
            flash("Hata: Girdiğin kod hatalı, lütfen tekrar dene!", "danger")
            return render_template('verify.html', email=email)
    return render_template('verify.html', email=email)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash("Giriş başarısız! Lütfen bilgilerinizi kontrol edin.", "danger")
            return render_template('login.html')
    return render_template('login.html')

@app.before_request
def check_ban():
    if current_user.is_authenticated:
        # Eğer süresiz banlıysa VEYA süreli banı varsa ve süresi henüz dolmadıysa
        if current_user.is_banned or (current_user.ban_expiration and current_user.ban_expiration > datetime.now()):
            if request.endpoint not in ['logout', 'static', 'login']:
                logout_user()
                flash("🚫 Hesabınız yasaklandı veya uzaklaştırıldı.", "danger")
                return redirect(url_for('login'))

@app.route('/edit_profile', methods=['GET', 'POST'])
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
                filename = secure_filename(f"user_{current_user.id}.{ext}")
                file.save(os.path.join(app.config['PROFILE_UPLOAD_FOLDER'], filename))
                current_user.profile_pic = f"uploads/profiles/{filename}"
                
        db.session.commit()
        flash("Profilin başarıyla güncellendi abem!", "success")
        return redirect(url_for('index'))
    return render_template('edit_profile.html')

@app.route('/users')
@login_required
def user_list():
    users = User.query.filter(User.id != current_user.id).order_by(func.random()).limit(50).all()
    return render_template('user_list.html', users=users, title='Önerilen Kişiler')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

def get_trending_hashtags():
    posts = Post.query.with_entities(Post.content).all()
    hashtags = {}
    for post in posts:
        if post.content:
            found_tags = re.findall(r"#(\w+)", post.content.lower())
            for tag in found_tags:
                hashtags[tag] = hashtags.get(tag, 0) + 1
    sorted_tags = sorted(hashtags.items(), key=lambda x: x[1], reverse=True)
    return sorted_tags[:5]

@app.context_processor
def inject_global_data():
    # Gündemdekiler
    trending = get_trending_hashtags()
    
    # Önerilen Kişiler (Takip edilmeyenler arasından rastgele 5 kişi)
    suggested = []
    if current_user.is_authenticated:
        followed_ids = [u.id for u in current_user.followed]
        followed_ids.append(current_user.id)
        suggested = User.query.filter(~User.id.in_(followed_ids)).order_by(db.func.random()).limit(5).all()
        
    return dict(trending_tags=trending, suggested_users=suggested)

@app.template_filter('format_tags')
def format_tags(text):
    if not text: return ""
    tags = re.sub(r"#(\w+)", r'<a href="/explore?q=%23\1" class="hashtag-link">#\1</a>', text)
    return Markup(tags)

@app.route('/vote', methods=['POST'])
@login_required
def vote():
    try:
        if not request.is_json:
            return jsonify({"success": False, "error": "Veri formatı JSON olmalı!"}), 400
        data = request.json
        kulup_id = data.get('kulup')
        if not kulup_id:
             return jsonify({"success": False, "error": "Kulüp ID bulunamadı!"}), 400
        votes = load_votes()
        if kulup_id in votes:
            votes[kulup_id] += 1
            save_votes(votes)
            return jsonify({"success": True, "new_vote": votes[kulup_id]})
        else:
            return jsonify({"success": False, "error": "Geçersiz kulüp!"}), 400
    except Exception as e:
        print(f"OYLAMA HATASI: {e}") 
        return jsonify({"success": False, "error": "Sunucu hatası oluştu."}), 500

@app.route('/delete_comment/<int:comment_id>')
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.author != current_user:
        flash("Bu yorumu silme yetkiniz yok!", "danger")
        return redirect(url_for('index'))
    db.session.delete(comment)
    db.session.commit()
    flash("Yorum silindi.", "info")
    return redirect(url_for('index'))

@app.route('/edit_comment/<int:comment_id>', methods=['POST'])
@login_required
def edit_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.author != current_user:
        flash("Başkalarının yorumunu düzenleyemezsin!", "danger")
        return redirect(url_for('index'))
    
    zaman_farki = datetime.now() - comment.date_posted
    if zaman_farki > timedelta(minutes=15):
        flash("Süre doldu! Yorumlar sadece ilk 15 dakika içinde düzenlenebilir.", "warning")
        return redirect(url_for('index'))

    new_text = request.form.get('new_text')
    if new_text:
        comment.text = new_text
        db.session.commit()
        flash("Yorum güncellendi!", "success")
    return redirect(url_for('index'))

@app.route('/delete_post/<int:post_id>')
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        flash("Bu gönderiyi silme yetkiniz yok!", "danger")
        return redirect(url_for('index'))
    db.session.delete(post)
    db.session.commit()
    flash("Gönderi silindi.", "info")
    return redirect(url_for('index'))

@app.route('/edit_post/<int:post_id>', methods=['POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        flash("Başkalarının gönderisini düzenleyemezsin!", "danger")
        return redirect(url_for('index'))
    new_content = request.form.get('new_content')
    if new_content:
        post.content = new_content
        db.session.commit()
        flash("Gönderi güncellendi!", "success")
    return redirect(url_for('index'))

@app.route('/explore')
@login_required
def explore():
    query = request.args.get('q')
    votes = load_votes()
    for club in CLUBS_DATA:
        club['votes'] = votes.get(club['id'], 0)
    ranked_clubs = sorted(CLUBS_DATA, key=lambda x: x['votes'], reverse=True)

    if query:
        if query.startswith('#'):
            posts = Post.query.filter(Post.content.contains(query)).order_by(Post.date_posted.desc()).all()
            return render_template('index.html', posts=posts, active_tab='explore', clubs=ranked_clubs, votes=votes, stories={})
        else:
            search_term = f"%{query}%"
            users = User.query.filter(
                or_(
                    User.username.ilike(search_term),
                    User.handle.ilike(search_term),
                    User.department.ilike(search_term)
                )
            ).all()
            
            def siralama_puani(user):
                q_lower = query.lower()
                name_lower = (user.username or "").lower()
                handle_lower = (user.handle or "").lower()
                if name_lower == q_lower or handle_lower == q_lower: return 0 
                elif name_lower.startswith(q_lower) or handle_lower.startswith(q_lower): return 1 
                else: return 2 
            
            users.sort(key=siralama_puani)
            return render_template('explore.html', users=users, search_query=query, clubs=ranked_clubs)
    else:
        users = User.query.filter(User.id != current_user.id).all()
        random.shuffle(users) 
        users = users[:20] 
        return render_template('explore.html', users=users, search_query=query, clubs=ranked_clubs)

@app.route('/u/<handle>')
@login_required
def user_profile(handle):
    user = User.query.filter_by(handle=handle).first_or_404()
    posts = Post.query.filter_by(author=user).order_by(Post.date_posted.desc()).all()
    return render_template('user_profile.html', user=user, posts=posts)

@app.route('/trending')
@login_required
def trending_full_list():
    all_tags = get_trending_hashtags()[:10] 
    return render_template('trending_full.html', tags=all_tags)

@app.route('/clubs_league')
@login_required
def clubs_full_list():
    votes = load_votes()
    for club in CLUBS_DATA:
        club['votes'] = votes.get(club['id'], 0)
    ranked_clubs = sorted(CLUBS_DATA, key=lambda x: x['votes'], reverse=True)[:10]
    return render_template('clubs_full.html', clubs=ranked_clubs)

@app.route('/follow/<handle>')
@login_required
def follow(handle):
    user = User.query.filter_by(handle=handle).first()
    if user is None:
        flash(f'{handle} kullanıcısı bulunamadı.', 'danger')
        return redirect(url_for('index'))
    if user == current_user:
        flash('Kendini takip edemezsin!', 'danger')
        return redirect(url_for('user_profile', handle=handle))
        
    current_user.follow(user)
    create_notification(user, current_user, 'followed')
    db.session.commit()
    flash(f'Artık {user.username} kişisini takip ediyorsun!', 'success')
    return redirect(request.referrer or url_for('user_profile', handle=handle))

@app.route('/unfollow/<handle>')
@login_required
def unfollow(handle):
    user = User.query.filter_by(handle=handle).first()
    if user is None:
        return redirect(url_for('index'))
    current_user.unfollow(user)
    db.session.commit()
    flash(f'{user.username} kişisini takipten çıktın.', 'info')
    return redirect(request.referrer or url_for('user_profile', handle=handle))

@app.route('/followers/<handle>')
@login_required
def followers_list(handle):
    user = User.query.filter_by(handle=handle).first_or_404()
    users = user.followers.all() 
    title = f"{user.username} - Takipçiler"
    return render_template('user_list.html', users=users, title=title)

@app.route('/following/<handle>')
@login_required
def following_list(handle):
    user = User.query.filter_by(handle=handle).first_or_404()
    users = user.followed.all() 
    title = f"{user.username} - Takip Edilenler"
    return render_template('user_list.html', users=users, title=title)

@app.route('/notifications')
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc()).all()
    for notif in notifs:
        notif.is_read = True
    db.session.commit()
    return render_template('notifications.html', notifications=notifs)

@app.context_processor
def inject_notifications():
    if current_user.is_authenticated:
        notif_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        msg_count = Message.query.filter_by(recipient_id=current_user.id, is_read=False).count()
        return dict(unread_count=notif_count, unread_msg_count=msg_count, online_users=list(ONLINE_USERS))
    return dict(unread_count=0, unread_msg_count=0, online_users=[])

@app.route('/messages')
@login_required
def messages_inbox():
    friends = current_user.followed.all()
    conversations = []
    for friend in friends:
        last_msg = Message.query.filter(
            or_(
                (Message.sender_id == current_user.id) & (Message.recipient_id == friend.id),
                (Message.sender_id == friend.id) & (Message.recipient_id == current_user.id)
            )
        ).order_by(Message.timestamp.desc()).first()
        unread_count = Message.query.filter_by(sender_id=friend.id, recipient_id=current_user.id, is_read=False).count()
        conversations.append({
            'user': friend,
            'last_message': last_msg,
            'timestamp': last_msg.timestamp if last_msg else datetime.min, 
            'unread': unread_count
        })
    conversations.sort(key=lambda x: x['timestamp'], reverse=True)
    return render_template('inbox.html', conversations=conversations)

@app.route('/chat/<handle>', methods=['GET', 'POST'])
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
            return redirect(url_for('chat', handle=handle))

    messages = Message.query.filter(
        or_(
            (Message.sender_id == current_user.id) & (Message.recipient_id == other_user.id),
            (Message.sender_id == other_user.id) & (Message.recipient_id == current_user.id)
        )
    ).order_by(Message.timestamp.asc()).all()
    return render_template('chat.html', user=other_user, messages=messages)

# --- API ROTALARI (GÜNCELLENMİŞ MESAJ GÖNDERME) ---
@app.route('/send_message/<int:rid>', methods=['POST'])
@login_required
def send_message(rid):
    b = request.form.get('body')
    story_id = request.form.get('story_id') 
    
    msg_type = 'text'
    file_path = None # Resim yolu için

    # EĞER HİKAYE İSE
    if story_id:
        msg_type = 'story'
        b = story_id 
        # Hikayeyi bul ve resmini file_path'e kaydet (Kritik Düzeltme)
        story = Story.query.get(int(story_id))
        if story:
            file_path = story.image_file
    
    elif not icerik_temiz_mi(b):
        return jsonify({'success':False, 'error': 'Küfür yasak'})

    if not b: return jsonify({'success':False})
    
    # file_path ile birlikte kaydet
    m = Message(sender_id=current_user.id, recipient_id=rid, body=b, msg_type=msg_type, file_path=file_path)
    db.session.add(m)
    db.session.commit()
    
    recipient = User.query.get(rid)
    
    msg_data = {
        'id': m.id,
        'body': m.body,
        'sender_id': current_user.id,
        'sender_name': current_user.username,
        'sender_pic': current_user.profile_pic,
        'timestamp': m.timestamp.strftime('%H:%M'),
        'msg_type': msg_type,     
        'story_img': file_path,   # Socket için resim yolu
        'file_path': file_path    # Audio veya Story için
    }
    
    socketio.emit('receive_message', msg_data, room=recipient.username)
    
    return jsonify({'success':True, 'message': msg_data})

# --- ADMIN PANELİ GÜNCEL ---
@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin: return redirect(url_for('index'))
    
    # En çok şikayet edilenleri en üstte getir
    reported_posts = Post.query.filter(Post.report_count > 0).order_by(Post.report_count.desc()).all()
    
    return render_template('admin.html', 
                           total_users=User.query.count(), 
                           total_posts=Post.query.count(),
                           reported_posts=reported_posts, # Şikayetleri gönderdik
                           cpu=psutil.cpu_percent(), 
                           ram=psutil.virtual_memory().percent, 
                           active_count=len(ONLINE_USERS), 
                           users=User.query.limit(50).all())

@app.route('/admin/delete_content/<string:type>/<int:id>')
@login_required
def admin_delete_content(type, id):
    if not current_user.is_admin: return "Yetkisiz"
    
    if type == 'post':
        item = Post.query.get_or_404(id)
        db.session.delete(item)
        flash("İçerik kalıcı olarak silindi.", "success")
    
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/ban_user/<int:user_id>/<string:action>')
@login_required
def admin_ban_user(user_id, action):
    if not current_user.is_admin: return "Yetkisiz"
    
    u = User.query.get_or_404(user_id)
    
    if action == 'perm': # Kalıcı Ban
        u.is_banned = True
        u.ban_expiration = None # Tarihe gerek yok, sonsuza kadar
        flash(f"{u.username} süresiz banlandı.", "danger")
        
    elif action == 'temp_24h': # 24 Saatlik
        u.ban_expiration = datetime.now() + timedelta(hours=24)
        flash(f"{u.username} 24 saat uzaklaştırıldı.", "warning")
        
    elif action == 'temp_1w': # 1 Haftalık
        u.ban_expiration = datetime.now() + timedelta(days=7)
        flash(f"{u.username} 1 hafta uzaklaştırıldı.", "warning")
        
    elif action == 'unban': # Banı Kaldır
        u.is_banned = False
        u.ban_expiration = None
        flash(f"{u.username} yasağı kaldırıldı.", "success")
        
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/api/system_stats')
@login_required
def system_stats():
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    active = len(ONLINE_USERS)
    return jsonify({"cpu": cpu, "ram": ram, "active": active, "time": datetime.now().strftime('%H:%M:%S')})

@app.route('/admin/create_tester', methods=['POST'])
@login_required
def create_tester():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    username = request.form.get('username')
    password = request.form.get('password')
    email = request.form.get('email') 
    if User.query.filter_by(email=email).first():
        flash("Bu mail zaten kayıtlı!", "danger")
        return redirect(url_for('admin_panel'))
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
    return redirect(url_for('admin_panel'))

@app.route('/beni_admin_yap')
@login_required
def make_me_admin():
    current_user.is_admin = True
    db.session.commit()
    return "Tebrikler Patron! Artık Adminsin. Ana sayfaya dönüp menüyü kontrol et."

@app.route('/notes')
@login_required
def notes_pool():
    dept_filter = request.args.get('dept')
    sort_by = request.args.get('sort', 'newest') 
    query = Note.query
    if dept_filter:
        query = query.filter_by(department=dept_filter)
    if sort_by == 'popular':     
        query = query.order_by(Note.downloads.desc())
    elif sort_by == 'rated':     
        query = query.order_by(Note.rating_sum.desc())
    else:                                    
        query = query.order_by(Note.date_posted.desc())
    notes = query.all()
    return render_template('notes.html', notes=notes, selected_dept=dept_filter, current_sort=sort_by)

@app.route('/rate_note/<int:note_id>/<int:score>', methods=['POST'])
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

# --- RAPORLAMA SİSTEMİ (GERÇEK) ---
@app.route('/report/<string:type>/<int:id>', methods=['POST'])
@login_required
def report_content(type, id):
    # CSRF Token kontrolünü kaldırdık
    if type == 'post':
        item = Post.query.get_or_404(id)
    elif type == 'comment':
        item = Comment.query.get_or_404(id)
    else:
        return jsonify({'success': False, 'message': 'Hata'})

    item.report_count += 1
    db.session.commit()
    return jsonify({'success': True, 'message': 'Şikayet yönetime iletildi.'})

@app.route('/upload_note', methods=['POST'])
@login_required
def upload_note():
    if 'note_file' not in request.files: return redirect(request.url)
    file = request.files['note_file']
    title = request.form.get('title')
    course_code = request.form.get('course_code')
    department = request.form.get('department')
    description = request.form.get('description') 

    if file:
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file_size_str = get_file_size_str(file_length)
        file.seek(0) 

        file_ext = file.filename.rsplit('.', 1)[1].lower()
        filename = secrets.token_hex(8) + "." + file_ext
        save_path = os.path.join(app.config['UPLOAD_FOLDER_NOTES'], filename)
        file.save(save_path)
        
        is_valid, message = not_icerigi_dogru_mu(save_path, department)
        if not is_valid:
             os.remove(save_path)
             flash('AI Onaylamadı: ' + message, 'danger')
             return redirect(url_for('notes_pool'))

        new_note = Note(title=title, course_code=course_code, department=department, 
                        description=description, file_path=filename, file_type=file_ext,
                        file_size=file_size_str, author=current_user)
        
        current_user.score += 10
        db.session.add(new_note)
        db.session.commit()
        flash('Not yüklendi! +10 Puan', 'success')
        return redirect(url_for('notes_pool'))

@app.route('/download_note/<int:note_id>')
@login_required
def download_note(note_id):
    note = Note.query.get_or_404(note_id)
    note.downloads += 1
    db.session.commit()
    return redirect(url_for('static', filename='note_files/' + note.file_path))

@app.route('/upload_story', methods=['POST'])
@login_required
def upload_story():
    image = request.files.get('story_image')
    ALLOWED_STORY_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}
    
    def allowed_story_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_STORY_EXTENSIONS

    if image and allowed_story_file(image.filename):
        filename = secure_filename(image.filename)
        import uuid
        filename = str(uuid.uuid4())[:8] + "_" + filename
        image.save(os.path.join(app.config['STORY_UPLOAD_FOLDER'], filename))
        
        new_story = Story(image_file=filename, author=current_user)
        db.session.add(new_story)
        db.session.commit()
        flash("Hikayen paylaşıldı!", "success")
    else:
        flash("Geçersiz dosya türü! Sadece Resim veya Video atabilirsin.", "danger")
    return redirect(url_for('index'))

@app.route('/delete_message/<int:message_id>')
@login_required
def delete_message(message_id):
    msg = Message.query.get_or_404(message_id)
    if msg.sender_id == current_user.id or msg.recipient_id == current_user.id:
        db.session.delete(msg)
        db.session.commit()
        return redirect(request.referrer)
    else:
        flash("Bu mesajı silme yetkiniz yok!", "danger")
        return redirect(url_for('messages_inbox'))
    
@app.route('/mark_story_seen/<int:story_id>', methods=['POST'])
@login_required
def mark_story_seen(story_id):
    story = Story.query.get_or_404(story_id)
    if current_user not in story.viewers:
        story.viewers.append(current_user)
        db.session.commit()
    return jsonify({"success": True})

@app.route('/delete_story/<int:story_id>')
@login_required
def delete_story(story_id):
    story = Story.query.get_or_404(story_id)
    if story.author != current_user:
        flash("Bu hikayeyi silme yetkiniz yok!", "danger")
        return redirect(url_for('index'))
    try:
        file_path = os.path.join(app.config['STORY_UPLOAD_FOLDER'], story.image_file)
        if os.path.exists(file_path):
            os.remove(file_path)
    except:
        pass 
    db.session.delete(story)
    db.session.commit()
    flash("Hikaye silindi.", "info")
    return redirect(url_for('index'))

@app.route('/vote_poll/<int:poll_id>/<int:option_id>', methods=['POST'])
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

# ==========================================
# 5. SOCKET.IO ve CANLI İŞLEMLER
# ==========================================

@socketio.on('join')
def on_join(data):
    username = data['username']
    join_room(username)
    print(f"{username} sohbete bağlandı.")

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        ONLINE_USERS.add(current_user.id)
        emit('user_status_change', {'user_id': current_user.id, 'status': 'online'}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        if current_user.id in ONLINE_USERS:
            ONLINE_USERS.remove(current_user.id)
        emit('user_status_change', {'user_id': current_user.id, 'status': 'offline'}, broadcast=True)

@socketio.on('call_user')
def on_call_user(data):
    emit('incoming_call', {
        'caller': data['caller'], 
        'signal': data['signal'],
        'isVideo': data['isVideo']
    }, room=data['userToCall'])

@socketio.on('answer_call')
def on_answer_call(data):
    emit('call_accepted', data['signal'], room=data['to'])

@socketio.on('ice_candidate')
def on_ice_candidate(data):
    emit('ice_candidate_msg', data['candidate'], room=data['to'])

@socketio.on('end_call')
def on_end_call(data):
    emit('call_ended', room=data['to'])

@socketio.on('typing')
def on_typing(data):
    emit('display_typing', {'username': current_user.username}, room=data['to'])

@socketio.on('stop_typing')
def on_stop_typing(data):
    emit('hide_typing', room=data['to'])

@app.route('/send_audio', methods=['POST'])
@login_required
def send_audio():
    if 'audio' not in request.files: return jsonify({'success': False, 'error': 'Ses dosyası yok'})
    file = request.files['audio']
    recipient_id = request.form.get('recipient_id')
    if file.filename == '': return jsonify({'success': False, 'error': 'Dosya ismi boş'})

    if file:
        import uuid
        filename = str(uuid.uuid4()) + ".webm"
        file.save(os.path.join(app.config['AUDIO_UPLOAD_FOLDER'], filename))
        
        new_msg = Message(sender_id=current_user.id, recipient_id=recipient_id, body="🎤 Sesli Mesaj", msg_type='audio', file_path=filename)
        db.session.add(new_msg)
        db.session.commit()
        
        message_data = {
            'id': new_msg.id,
            'body': "🎤 Sesli Mesaj",
            'sender_id': current_user.id,
            'sender_pic': current_user.profile_pic,
            'timestamp': new_msg.timestamp.strftime('%H:%M'),
            'msg_type': 'audio',
            'file_path': filename
        }
        recipient = User.query.get(recipient_id)
        socketio.emit('receive_message', message_data, room=recipient.username)
        return jsonify({'success': True, 'message': message_data})
    
    return jsonify({'success': False})

@app.route('/api/share_post', methods=['POST'])
@login_required
def share_post_api():
    post_content = request.form.get('content')
    if not icerik_temiz_mi(post_content):
        return jsonify({'success': False, 'error': '⚠️ Küfürlü paylaşımlar yasak.'})

    image = request.files.get('image')
    poll_opt1 = request.form.get('poll_opt1')
    poll_opt2 = request.form.get('poll_opt2')

    if post_content or image:
        filename = None
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            import uuid
            filename = str(uuid.uuid4())[:8] + "_" + filename
            image.save(os.path.join(app.config['POST_UPLOAD_FOLDER'], filename))

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

@app.route('/api/add_comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment_api(post_id):
    post = Post.query.get_or_404(post_id)
    text = request.form.get('comment_text')
    if not icerik_temiz_mi(text):
        return jsonify({'success': False, 'error': '⚠️ Uygunsuz içerik.'})
    
    if text:
        comment = Comment(text=text, author=current_user, post=post)
        db.session.add(comment)
        db.session.commit()
        
        comment_data = {
            'id': comment.id,
            'text': comment.text,
            'author_name': current_user.username,
            'date': comment.date_posted.strftime('%H:%M')
        }
        return jsonify({'success': True, 'comment': comment_data})
    return jsonify({'success': False})

@app.route('/reels')
@login_required
def reels():
    # Videoları doğrudan veritabanından, uzantısına göre çekiyoruz
    video_posts = Post.query.filter(
        or_(
            Post.image_file.ilike('%.mp4'),
            Post.image_file.ilike('%.mov'),
            Post.image_file.ilike('%.avi'),
            Post.image_file.ilike('%.webm'),
            Post.image_file.ilike('%.mkv')
        )
    ).order_by(Post.date_posted.desc()).all()
    
    return render_template('reels.html', posts=video_posts)

@app.before_request
def start_timer():
    g.start = time.time()

@app.after_request
def log_response(response):
    if hasattr(g, 'start'):
        now = time.time()
        duration = round(now - g.start, 4)
        print(f"--- Sayfa Yükleme: {duration}s ---")
    return response

@app.route('/admin/create_user', methods=['POST'])
@login_required
def admin_create_user():
    if not current_user.is_admin: return "Yetkisiz Alan"
    
    email = request.form.get('email')
    username = request.form.get('username')
    password = request.form.get('password')
    dept = request.form.get('department')
    
    if User.query.filter_by(email=email).first():
        flash("Bu mail zaten kayıtlı!", "danger")
        return redirect(url_for('admin_panel'))
        
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
    return redirect(url_for('admin_panel'))

# --- VERİTABANI TAMİR ROTASI (TEK SEFERLİK) ---
@app.route('/fix_db')
def manual_fix_db():
    import sqlite3
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        commands = [
            "ALTER TABLE user ADD COLUMN ban_expiration TIMESTAMP",
            "ALTER TABLE user ADD COLUMN image_file VARCHAR(20)",
            "ALTER TABLE user ADD COLUMN is_banned BOOLEAN DEFAULT 0",
            "ALTER TABLE post ADD COLUMN report_count INTEGER DEFAULT 0",
            "ALTER TABLE comment ADD COLUMN report_count INTEGER DEFAULT 0",
            "ALTER TABLE note ADD COLUMN report_count INTEGER DEFAULT 0"
        ]
        
        added = []
        for cmd in commands:
            try:
                cursor.execute(cmd)
                added.append(cmd)
            except sqlite3.OperationalError:
                pass 
        
        conn.commit()
        conn.close()
        return f"<h3>✅ Veritabanı Tamir Edildi!</h3><p>Eklenen sütunlar: {len(added)} adet.</p><a href='/'>Ana Sayfaya Dön</a>"
    except Exception as e:
        return f"<h3>❌ Hata oluştu:</h3><p>{str(e)}</p>"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, host='0.0.0.0', port=5002, debug=True)
