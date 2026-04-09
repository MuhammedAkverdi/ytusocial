from flask_socketio import emit, join_room
from flask_login import current_user
from extensions import socketio
from utils import ONLINE_USERS

@socketio.on('join')
def on_join(data):
    username = data['username']
    join_room(username)
    print(f"{username} sohbete bağlandı.")

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        ONLINE_USERS.add(current_user.id)
        join_room(current_user.username)
        emit('user_status_change', {'user_id': current_user.id, 'status': 'online'}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        if current_user.id in ONLINE_USERS:
            ONLINE_USERS.remove(current_user.id)
        emit('user_status_change', {'user_id': current_user.id, 'status': 'offline'}, broadcast=True)

@socketio.on('typing')
def on_typing(data):
    emit('display_typing', {'username': current_user.username}, room=data['to'])

@socketio.on('stop_typing')
def on_stop_typing(data):
    emit('hide_typing', room=data['to'])