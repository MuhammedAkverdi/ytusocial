from flask import Blueprint, jsonify, request, current_app
from bs4 import BeautifulSoup
from urllib.parse import urlencode
import html
import urllib.request
import urllib.error
import time
from flask_login import login_required, current_user
from extensions import db, socketio
from models import User, Story, Post, Poll, PollOption, Comment, ClubVote, Feedback
from utils import optimize_and_save_image, allowed_file, create_notification
from sqlalchemy import or_
import unicodedata
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
        'timestamp': story.timestamp.strftime('%H:%M'),
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
    from utils import get_online_user_count
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    active = get_online_user_count()
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
        
        mentions = re.findall(r"@([\w\u00C0-\u024F-]+(?:\.[\w\u00C0-\u024F-]+)*)", text)
        for handle in set(mentions):
            mentioned_user = User.query.filter_by(handle=handle).first()
            if mentioned_user:
                create_notification(mentioned_user, current_user, 'mentioned', post)
        
        comment_data = {
            'id': comment.id,
            'text': comment.text,
            'author_name': current_user.username,
            'author_handle': current_user.handle,
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

@api.route('/api/random_posts')
@login_required
def api_random_posts():
    import random
    posts = Post.query.filter(Post.image_file.isnot(None)).all()
    random.shuffle(posts)
    posts = posts[:20]
    results = []
    for p in posts:
        results.append({
            'id': p.id,
            'image_file': p.image_file,
            'is_video': p.is_video(),
            'like_count': len(p.liked_by),
            'comment_count': len(p.comments)
        })
    return jsonify({'success': True, 'posts': results})


@api.route('/api/story/report', methods=['POST'])
@login_required
def report_story_api():
    payload = request.get_json(silent=True) or {}
    story_id = payload.get('story_id')
    reason = (payload.get('reason') or 'Uygunsuz hikaye').strip()

    try:
        story_id = int(story_id)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Gecersiz hikaye id.'}), 400

    story = Story.query.get(story_id)
    if not story:
        return jsonify({'success': False, 'error': 'Hikaye bulunamadi.'}), 404

    feedback_text = f"Story report | story_id={story.id} | owner_id={story.user_id} | reason={reason}"
    fb = Feedback(user_id=current_user.id, type='Story Sikayet', message=feedback_text)
    db.session.add(fb)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Hikaye bildirimi alindi.'})


# ── IETT 41AT Rota Verisi ───────────────────────────────────────────────────
_IETT_41AT_ROUTE_URL = 'https://iett.istanbul/RouteDetail?hkod=41AT&routename=AYAZA%C4%9EA%20-%20DAVUTPA%C5%9EA%20Y.T.%C3%9C'
_IETT_BASE_URL = 'https://iett.istanbul'
_ulasim_route_cache = {}  # {"41AT": (timestamp, payload)}
_ROUTE_CACHE_TTL = 30 * 60


def _fetch_iett_html(url, data=None, referer=None):
    headers = {'User-Agent': 'Mozilla/5.0'}
    if referer:
        headers['Referer'] = referer
    body = urlencode(data).encode('utf-8') if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=12) as resp:
        return resp.read().decode('utf-8', errors='replace')


def _normalize_iett_text(value):
    if not value:
        return ''
    text = html.unescape(value)
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^A-Za-z0-9]+', ' ', text).strip().upper()
    return text


def _extract_stop_payload(stop_text, stop_href):
    stop_match = re.search(r'dkod=(\d+)', stop_href or '')
    text = html.unescape(stop_text or '').strip()
    text = re.sub(r'^\d+\.\s*', '', text)
    if ' - ' in text:
        stop_name, district = text.rsplit(' - ', 1)
    else:
        stop_name, district = text, ''

    return {
        'code': stop_match.group(1) if stop_match else None,
        'name': stop_name.strip(),
        'district': district.strip(),
        'search_key': _normalize_iett_text(f'{stop_name} {district}')
    }


def _select_campus_stops(stops, target_specs):
    selected = []
    used_codes = set()

    for spec in target_specs:
        if isinstance(spec, (list, tuple)):
            target_label = spec[0]
            display_label = spec[1] if len(spec) > 1 else spec[0]
        else:
            target_label = spec
            display_label = spec

        target_key = _normalize_iett_text(target_label)
        match = None
        for stop in stops:
            if stop['code'] in used_codes:
                continue
            if target_key in stop['search_key']:
                match = stop
                break

        if match:
            used_codes.add(match['code'])
            selected.append({
                'code': match['code'],
                'name': display_label,
                'district': match['district'],
                'raw_name': match['name'],
            })

    return selected


def _extract_time_value(value):
    match = re.search(r'(\d{2}:\d{2})', value or '')
    return match.group(1) if match else ''


def _parse_schedule_fragment(fragment_html):
    soup = BeautifulSoup(fragment_html, 'html.parser')
    schedules = []

    for table in soup.select('table.line-table'):
        heading = table.select_one('thead .routedetailstartend')
        raw_title = heading.get_text(' ', strip=True) if heading else 'Sefer Saatleri'
        if raw_title.upper().endswith(' KALKIŞ'):
            raw_title = raw_title[:-7].strip()

        header_cells = table.select('thead tr:nth-of-type(2) th')
        column_labels = [cell.get_text(' ', strip=True) for cell in header_cells]
        if len(column_labels) < 3:
            column_labels = ['Hafta içi', 'Cumartesi', 'Pazar']

        day_keys = ['weekdays', 'saturday', 'sunday']
        day_times = {key: [] for key in day_keys}

        for row in table.select('tbody tr'):
            cells = [cell.get_text(' ', strip=True) for cell in row.find_all('td')]
            if len(cells) != 3:
                continue

            for key, cell_text in zip(day_keys, cells):
                if not cell_text:
                    continue
                if cell_text not in day_times[key]:
                    day_times[key].append(cell_text)

        days = []
        for idx, key in enumerate(day_keys):
            times = day_times[key]
            clean_times = [value for value in times if _extract_time_value(value)]
            days.append({
                'key': key,
                'label': column_labels[idx] if idx < len(column_labels) else key,
                'times': clean_times,
                'summary': {
                    'first': _extract_time_value(clean_times[0]) if clean_times else '',
                    'last': _extract_time_value(clean_times[-1]) if clean_times else '',
                }
            })

        schedules.append({
            'title': raw_title,
            'days': days,
        })

    return schedules


def _build_ulasim_41at_payload():
    page_html = _fetch_iett_html(_IETT_41AT_ROUTE_URL, referer='https://iett.istanbul/')
    page_soup = BeautifulSoup(page_html, 'html.parser')

    route_inputs = {}
    for input_tag in page_soup.find_all('input'):
        input_id = input_tag.get('id')
        if input_id:
            route_inputs[input_id] = input_tag.get('value', '') or ''

    route_name = html.unescape(route_inputs.get('hatkod', '41AT'))
    route_start = html.unescape(route_inputs.get('SHATBASI') or route_inputs.get('hatstart') or 'AYAZAĞA')
    route_end = html.unescape(route_inputs.get('SHATSONU') or route_inputs.get('hatend') or 'YILDIZ TEKNİK ÜNİVERSİTESİ DAVUTPAŞA KAMPÜSÜ')
    language_id = route_inputs.get('languageid') or '1'

    notes = []
    notes_block = page_soup.select_one('#routedesc')
    if notes_block:
        for note in notes_block.find_all('p'):
            note_text = note.get_text(' ', strip=True)
            if note_text:
                notes.append(note_text)

    station_url = f"{_IETT_BASE_URL}/tr/RouteStation/GetStationForRoute?{urlencode({'hatkod': route_name, 'hatstart': route_start, 'hatend': route_end, 'langid': language_id})}"
    station_html = _fetch_iett_html(station_url, referer=_IETT_41AT_ROUTE_URL)
    station_soup = BeautifulSoup(station_html, 'html.parser')
    station_columns = station_soup.select('.col-md-6')
    parsed_columns = []

    for column in station_columns:
        stops = []
        for stop_anchor in column.select('.line-pass-item a'):
            stops.append(_extract_stop_payload(stop_anchor.get_text(' ', strip=True), stop_anchor.get('href')))
        parsed_columns.append(stops)

    tracker_specs = {
        'in': [
            ('YILDIZ TEKNIK UNIVERSITESI DAVUTPASA KAMPUSU', 'YTÜ Davutpaşa Kampüsü'),
            ('IKTISADI VE IDARI BILIMLER FAKULTESI', 'İktisadi ve İdari Bilimler Fak.'),
            ('FAKULTE B KAPISI', 'Fakülte B Kapısı'),
            ('UNIVERSITE CAMII', 'Üniversite Camii'),
            ('EGITIM FAKULTESI', 'Eğitim Fakültesi'),
            ('INSAAT FAKULTESI', 'İnşaat Fakültesi'),
            ('YABANCI DILLER OKULU', 'Yabancı Diller Okulu'),
            ('DAVUTPASA KAMPUSU', 'Davutpaşa Kampüsü'),
        ],
        'out': [
            ('YILDIZ TEKNIK UNIVERSITESI DAVUTPASA KAMPUSU', 'YTÜ Davutpaşa Kampüsü'),
            ('IKTISADI VE IDARI BILIMLER FAKULTESI', 'İktisadi ve İdari Bilimler Fak.'),
            ('FAKULTE B KAPISI', 'Fakülte B Kapısı'),
            ('UNIVERSITE CAMII', 'Üniversite Camii'),
            ('EGITIM FAKULTESI', 'Eğitim Fakültesi'),
            ('INSAAT FAKULTESI', 'İnşaat Fakültesi'),
            ('YABANCI DILLER OKULU', 'Yabancı Diller Okulu'),
            ('DAVUTPASA METRO', 'Davutpaşa Metro'),
        ],
    }

    tracker = {
        'in': _select_campus_stops(parsed_columns[0] if len(parsed_columns) > 0 else [], tracker_specs['in']),
        'out': _select_campus_stops(parsed_columns[1] if len(parsed_columns) > 1 else [], tracker_specs['out']),
    }

    schedule_html = _fetch_iett_html(
        f'{_IETT_BASE_URL}/tr/RouteStation/GetScheduledDepartureTimes',
        data={
            'rstart': route_inputs.get('SHATBASI') or route_start,
            'rend': route_inputs.get('SHATSONU') or route_end,
            'timeschule': route_inputs.get('GetPlanlananSeferSaati') or '',
            'freq': route_inputs.get('GetMetobusFrekans') or '',
            'lngid': language_id,
            'hCode': route_name,
        },
        referer=_IETT_41AT_ROUTE_URL,
    )
    schedules = _parse_schedule_fragment(schedule_html)

    return {
        'route': {
            'code': route_name,
            'title': '41AT',
            'from_label': 'AYAZAĞA',
            'to_label': 'YILDIZ TEKNİK ÜNİVERSİTESİ DAVUTPAŞA KAMPÜSÜ',
            'display_name': f'{route_start} - {route_end}',
            'route_link': _IETT_41AT_ROUTE_URL,
            'notes': notes,
            'directions': schedules,
        },
        'tracker': tracker,
        'loaded_at': int(time.time()),
        'refresh_interval': 30,
    }


@api.route('/api/ulasim_41at')
@login_required
def ulasim_41at():
    now = time.time()
    cached = _ulasim_route_cache.get('41AT')
    if cached and (now - cached[0]) < _ROUTE_CACHE_TTL:
        return jsonify({'success': True, 'route': cached[1], 'cached': True})

    try:
        payload = _build_ulasim_41at_payload()
        _ulasim_route_cache['41AT'] = (now, payload)
        return jsonify({'success': True, 'route': payload, 'cached': False})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 502


# ── IETT Gerçek Zamanlı Durak Proxy ──────────────────────────────────────────
_ulasim_cache = {}   # {stop_code: (timestamp, html)}
_CACHE_TTL = 30      # saniye

@api.route('/api/ulasim_live')
@login_required
def ulasim_live():
    import time
    stop_code = request.args.get('stop', '125851')
    # Sadece sayısal stop-code kabul et
    if not stop_code.isdigit():
        return jsonify({'success': False, 'error': 'Geçersiz durak kodu'}), 400

    now = time.time()
    cached = _ulasim_cache.get(stop_code)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return jsonify({'success': True, 'html': cached[1], 'cached': True})

    try:
        url = f'https://iett.istanbul/tr/RouteStation/GetStationInfo?dcode={stop_code}&langid=1'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://iett.istanbul/',
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode('utf-8')
        _ulasim_cache[stop_code] = (now, html)
        return jsonify({'success': True, 'html': html, 'cached': False})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 502