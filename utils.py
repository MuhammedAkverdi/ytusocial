from datetime import datetime, timedelta
from PIL import Image
import pytesseract
import os
import json
import re
from werkzeug.utils import secure_filename
from flask import url_for, current_app
from extensions import db, socketio

BOLUM_KELIMELERI = {
    'Bilgisayar': ['algoritma', 'yazılım', 'kod', 'software', 'java', 'python', 'cpu', 'ram', 'veri', 'network', 'class', 'object', 'döngü', 'loop'],
    'Hazırlık': ['present', 'verb', 'noun', 'tense', 'vocabulary', 'grammar', 'subject', 'english', 'reading', 'writing', 'book', 'unit'],
    'Makine': ['kuvvet', 'moment', 'mekanik', 'statik', 'dinamik', 'motor', 'dişli', 'termodinamik', 'akışkan', 'force', 'energy'],
    'Elektrik': ['volt', 'amper', 'devre', 'akım', 'direnç', 'circuit', 'power', 'enerji', 'kablo', 'elektronik'],
    'Mimarlık': ['çizim', 'plan', 'kesit', 'bina', 'tasarım', 'ölçek', 'mekan', 'yapı', 'cephe', 'mimari'],
    'Genel': []
}

ONLINE_USERS = set()
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'webm', 'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'txt'}
DATA_FILE = 'votes.json'

def get_turkey_time():
    return datetime.utcnow() + timedelta(hours=3)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def not_icerigi_dogru_mu(resim_yolu, bolum):
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

def icerik_temiz_mi(text):
    return True

def get_file_size_str(size_in_bytes):
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    elif size_in_bytes < 1024 * 1024:
        return f"{round(size_in_bytes/1024, 1)} KB"
    else:
        return f"{round(size_in_bytes/(1024*1024), 1)} MB"

def optimize_and_save_image(file_storage, upload_folder, base_filename=None, max_size=(1080, 1080), quality=85):
    filename = secure_filename(file_storage.filename)
    ext = os.path.splitext(filename)[1].lower()
    
    if not base_filename:
        import uuid
        base_filename = str(uuid.uuid4())[:8] + "_" + filename

    filepath = os.path.join(upload_folder, base_filename)

    if ext in ['.jpg', '.jpeg', '.png', '.webp']:
        try:
            img = Image.open(file_storage)
            img.thumbnail(max_size)
            img.save(filepath, optimize=True, quality=quality)
            return base_filename
        except Exception as e:
            print(f"Resim optimizasyon hatası: {e}, orijinal kaydediliyor.")
    
    file_storage.seek(0)
    file_storage.save(filepath)
    return base_filename

def save_votes(votes):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(votes, f, ensure_ascii=False, indent=4)

def load_votes():
    if not os.path.exists(DATA_FILE) or os.path.getsize(DATA_FILE) == 0:
        return {}
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def create_notification(receiver, actor, verb, post=None):
    from models import Notification 
    if receiver == actor: return
    notif = Notification(user_id=receiver.id, actor_id=actor.id, verb=verb, post_id=post.id if post else None)
    db.session.add(notif)
    db.session.commit()
    notif_text = ""
    if verb == 'liked': notif_text = f"{actor.username} gönderini beğendi."
    elif verb == 'commented': notif_text = f"{actor.username} gönderine yorum yaptı."
    elif verb == 'followed': notif_text = f"{actor.username} seni takip etti."
    elif verb == 'messaged': notif_text = f"{actor.username} sana mesaj gönderdi."
    elif verb == 'mentioned': notif_text = f"{actor.username} bir yorumda senden bahsetti."
    socketio.emit('new_notification', {
        'count': Notification.query.filter_by(user_id=receiver.id, is_read=False).count(),
        'text': notif_text,
        'actor_pic': actor.profile_pic,
        'link': url_for('main.notifications')
    }, room=receiver.username)

def get_trending_hashtags():
    from models import Post
    posts = Post.query.with_entities(Post.content).all()
    hashtags = {}
    for post in posts:
        if post.content:
            found_tags = re.findall(r"#(\w+)", post.content.lower())
            for tag in found_tags:
                hashtags[tag] = hashtags.get(tag, 0) + 1
    sorted_tags = sorted(hashtags.items(), key=lambda x: x[1], reverse=True)
    return sorted_tags[:5]