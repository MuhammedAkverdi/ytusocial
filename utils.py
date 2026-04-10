from datetime import datetime, timedelta
from io import BytesIO
from urllib.parse import quote

import boto3
import mimetypes
from PIL import Image
import pytesseract
import os
import json
import re
from werkzeug.utils import secure_filename
from flask import url_for, current_app
from extensions import db, socketio
from threading import Lock

BOLUM_KELIMELERI = {
    'Bilgisayar': ['algoritma', 'yazılım', 'kod', 'software', 'java', 'python', 'cpu', 'ram', 'veri', 'network', 'class', 'object', 'döngü', 'loop'],
    'Hazırlık': ['present', 'verb', 'noun', 'tense', 'vocabulary', 'grammar', 'subject', 'english', 'reading', 'writing', 'book', 'unit'],
    'Makine': ['kuvvet', 'moment', 'mekanik', 'statik', 'dinamik', 'motor', 'dişli', 'termodinamik', 'akışkan', 'force', 'energy'],
    'Elektrik': ['volt', 'amper', 'devre', 'akım', 'direnç', 'circuit', 'power', 'enerji', 'kablo', 'elektronik'],
    'Mimarlık': ['çizim', 'plan', 'kesit', 'bina', 'tasarım', 'ölçek', 'mekan', 'yapı', 'cephe', 'mimari'],
    'Genel': []
}

ONLINE_USERS = set()
ONLINE_USER_CONNECTIONS = {}
ONLINE_USER_SID_MAP = {}
ONLINE_USERS_LOCK = Lock()
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'webm', 'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'txt'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
DATA_FILE = 'votes.json'

# Not havuzu için izin verilen uzantılar (sadece belge formatları)
ALLOWED_NOTE_EXTENSIONS = {'pdf', 'txt', 'doc', 'docx', 'ppt', 'pptx'}

# Dosya imzaları (magic bytes) - dosyanın gerçekten ne olduğunu doğrula
FILE_MAGIC_SIGNATURES = {
    'pdf':  [(0, b'%PDF')],
    'docx': [(0, b'PK\x03\x04')],
    'pptx': [(0, b'PK\x03\x04')],
    'doc':  [(0, b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')],
    'ppt':  [(0, b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')],
    'txt':  None,  # Sabit imza yok; null byte kontrolü yapılır
}

MAX_NOTE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB

def get_turkey_time():
    return datetime.utcnow() + timedelta(hours=3)

def register_online_user(user_id, sid=None):
    with ONLINE_USERS_LOCK:
        if sid is not None:
            previous_user_id = ONLINE_USER_SID_MAP.get(sid)
            if previous_user_id is not None and previous_user_id != user_id:
                previous_count = ONLINE_USER_CONNECTIONS.get(previous_user_id, 0)
                if previous_count <= 1:
                    ONLINE_USER_CONNECTIONS.pop(previous_user_id, None)
                    ONLINE_USERS.discard(previous_user_id)
                else:
                    ONLINE_USER_CONNECTIONS[previous_user_id] = previous_count - 1
            ONLINE_USER_SID_MAP[sid] = user_id

        current_count = ONLINE_USER_CONNECTIONS.get(user_id, 0) + 1
        ONLINE_USER_CONNECTIONS[user_id] = current_count
        ONLINE_USERS.add(user_id)
        return current_count == 1

def unregister_online_user(user_id=None, sid=None):
    with ONLINE_USERS_LOCK:
        resolved_user_id = user_id
        if sid is not None:
            mapped_user_id = ONLINE_USER_SID_MAP.pop(sid, None)
            if mapped_user_id is not None:
                resolved_user_id = mapped_user_id

        if resolved_user_id is None:
            return None, False

        current_count = ONLINE_USER_CONNECTIONS.get(resolved_user_id, 0)
        if current_count <= 1:
            ONLINE_USER_CONNECTIONS.pop(resolved_user_id, None)
            ONLINE_USERS.discard(resolved_user_id)
            return resolved_user_id, True

        ONLINE_USER_CONNECTIONS[resolved_user_id] = current_count - 1
        return resolved_user_id, False

def get_online_user_count():
    with ONLINE_USERS_LOCK:
        return len(ONLINE_USERS)

def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

def _get_spaces_config():
    access_key = (os.environ.get('SPACES_ACCESS_KEY') or '').strip()
    secret_key = (os.environ.get('SPACES_SECRET_KEY') or '').strip()
    bucket_name = (os.environ.get('SPACES_BUCKET_NAME') or '').strip()
    endpoint = (os.environ.get('SPACES_ENDPOINT') or '').strip()
    region = (os.environ.get('SPACES_REGION') or '').strip()

    if not access_key or not secret_key or not bucket_name or not endpoint or not region:
        return None

    return {
        'access_key': access_key,
        'secret_key': secret_key,
        'bucket_name': bucket_name,
        'endpoint': endpoint,
        'region': region,
    }

def club_logo_src(logo_file):
    if not logo_file:
        return '/static/img/default_club.png'

    if logo_file.startswith('http://') or logo_file.startswith('https://'):
        return logo_file

    if logo_file in {'default_club.jpg', 'default_club.png'}:
        return '/static/img/default_club.png'

    spaces_config = _get_spaces_config()
    if spaces_config:
        return f"https://{spaces_config['bucket_name']}.{spaces_config['region']}.digitaloceanspaces.com/{quote(logo_file, safe='/')}"

    return '/static/img/' + logo_file

def upload_club_logo_to_spaces(file_storage, object_key=None, max_size=(400, 400), quality=85):
    spaces_config = _get_spaces_config()
    if not spaces_config:
        raise RuntimeError('DigitalOcean Spaces ayarları eksik.')

    filename = secure_filename(file_storage.filename or '')
    if not filename:
        raise ValueError('Geçersiz logo dosyası.')

    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError('Kulüp logosu yalnızca PNG, JPG, JPEG veya WEBP olabilir.')

    object_key = object_key or filename
    content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    payload = BytesIO()

    try:
        file_storage.stream.seek(0)
        image = Image.open(file_storage.stream)
        image.thumbnail(max_size)

        save_format = 'JPEG' if ext in {'jpg', 'jpeg'} else ext.upper()
        if save_format == 'JPEG' and image.mode in {'RGBA', 'P'}:
            image = image.convert('RGB')

        save_kwargs = {'optimize': True}
        if save_format in {'JPEG', 'WEBP'}:
            save_kwargs['quality'] = quality

        image.save(payload, format=save_format, **save_kwargs)
        payload.seek(0)

        if save_format == 'JPEG':
            content_type = 'image/jpeg'
        elif save_format == 'PNG':
            content_type = 'image/png'
        elif save_format == 'WEBP':
            content_type = 'image/webp'
    except Exception:
        file_storage.stream.seek(0)
        payload = BytesIO(file_storage.read())
        payload.seek(0)

    client = boto3.client(
        's3',
        region_name=spaces_config['region'],
        endpoint_url=spaces_config['endpoint'],
        aws_access_key_id=spaces_config['access_key'],
        aws_secret_access_key=spaces_config['secret_key'],
    )
    client.put_object(
        Bucket=spaces_config['bucket_name'],
        Key=object_key,
        Body=payload.getvalue(),
        ACL='public-read',
        ContentType=content_type,
    )
    return object_key

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def scan_file_safety(file_path, ext):
    """
    Yüklenen dosyanın güvenli olup olmadığını kontrol eder:
    1. Uzantı izin verilenler listesinde mi?
    2. Dosya boyutu 15 MB'ı aşıyor mu?
    3. Magic bytes, uzantıyla eşleşiyor mu?
    4. TXT dosyaları binary içerik barındırıyor mu?
    """
    ext = ext.lower().strip('.')

    if ext not in ALLOWED_NOTE_EXTENSIONS:
        return False, f"İzin verilmeyen dosya türü: .{ext}. İzin verilenler: PDF, TXT, DOC, DOCX, PPT, PPTX"

    try:
        file_size = os.path.getsize(file_path)
    except OSError:
        return False, "Dosya boyutu okunamadı."

    if file_size > MAX_NOTE_SIZE_BYTES:
        return False, f"Dosya boyutu 15 MB sınırını aşıyor ({round(file_size / (1024*1024), 1)} MB)."

    if file_size == 0:
        return False, "Dosya boş."

    try:
        with open(file_path, 'rb') as f:
            header = f.read(8)

        signatures = FILE_MAGIC_SIGNATURES.get(ext)

        if signatures is None:
            # TXT: null byte kontrolü
            with open(file_path, 'rb') as f:
                chunk = f.read(4096)
            if b'\x00' in chunk:
                return False, "TXT dosyası geçersiz binary içerik barındırıyor."
        else:
            matched = False
            for offset, sig in signatures:
                if header[offset:offset + len(sig)] == sig:
                    matched = True
                    break
            if not matched:
                return False, f"Dosya içeriği .{ext} formatıyla uyuşmuyor. Dosya bozuk veya sahte olabilir."

    except Exception as e:
        print(f"Dosya tarama hatası: {e}")
        return False, "Dosya taranamadı."

    return True, "Dosya güvenli."

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
    try:
        posts = Post.query.with_entities(Post.content).all()
    except Exception as exc:
        try:
            current_app.logger.warning('Trending hashtag query unavailable: %s', exc, exc_info=True)
        except Exception:
            print(f'Trending hashtag query unavailable: {exc}')
        return []
    hashtags = {}
    for post in posts:
        if post.content:
            found_tags = set(re.findall(r"#(\w+)", post.content.lower()))
            for tag in found_tags:
                hashtags[tag] = hashtags.get(tag, 0) + 1
    sorted_tags = sorted(hashtags.items(), key=lambda x: x[1], reverse=True)
    return sorted_tags[:5]