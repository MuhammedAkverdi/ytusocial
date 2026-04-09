from flask import request
from flask_socketio import emit, join_room
from flask_login import current_user
from extensions import socketio
from utils import register_online_user, unregister_online_user

@socketio.on('join')
def on_join(data):
    username = data['username']
    join_room(username)
    print(f"{username} sohbete bağlandı.")

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        join_room(current_user.username)
        became_online = register_online_user(current_user.id, sid=request.sid)
        if became_online:
            emit('user_status_change', {'user_id': current_user.id, 'status': 'online'}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    resolved_user_id, became_offline = unregister_online_user(
        user_id=current_user.id if current_user.is_authenticated else None,
        sid=request.sid,
    )
    if became_offline and resolved_user_id is not None:
        emit('user_status_change', {'user_id': resolved_user_id, 'status': 'offline'}, broadcast=True)

@socketio.on('typing')
def on_typing(data):
    emit('display_typing', {'username': current_user.username}, room=data['to'])

@socketio.on('stop_typing')
def on_stop_typing(data):
    emit('hide_typing', room=data['to'])