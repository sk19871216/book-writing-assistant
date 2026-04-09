#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Web server with Flask and WebSocket for writing assistant."""

import os
import sys
import json
import threading
import uuid
from datetime import datetime
from functools import wraps

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, render_template, jsonify, request, session
from flask_socketio import SocketIO, emit, join_room, leave_room

from src.storage import (
    init_db, create_conversation, get_conversation, list_conversations,
    append_entry, get_all_entries, save_user_selection, get_latest_user_selection
)
from src.workflow import start_workflow, continue_workflow, resume_workflow


app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = str(uuid.uuid4())
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

CLIENTS = {}

PROJECT_DIR = os.path.join(os.path.dirname(__file__), '..')
WORKFLOW_THREADS = {}


def broadcast_to_conv(conv_id: int, event: str, data: dict):
    """Broadcast event to all clients in a conversation room."""
    socketio.emit(event, data, room=f'conv_{conv_id}')


def workflow_broadcaster(conv_id: int):
    """Create a broadcaster function for a specific conversation."""
    def broadcaster(message: dict):
        broadcast_to_conv(conv_id, 'workflow_event', message)
    return broadcaster


@app.route('/')
def index():
    """Main page."""
    return render_template('index.html')


@app.route('/api/conversations', methods=['GET'])
def api_list_conversations():
    """List all conversations."""
    conversations = list_conversations(20)
    return jsonify(conversations)


@app.route('/api/conversations', methods=['POST'])
def api_create_conversation():
    """Create a new conversation."""
    data = request.get_json() or {}
    topic = data.get('topic', '')
    
    if not topic:
        return jsonify({'error': 'Topic is required'}), 400
    
    conv_id = create_conversation(topic)
    
    broadcast_to_conv(0, 'conversation_created', {
        'id': conv_id,
        'topic': topic
    })
    
    return jsonify({'id': conv_id, 'topic': topic})


@app.route('/api/conversations/<int:conv_id>', methods=['GET'])
def api_get_conversation(conv_id: int):
    """Get conversation details."""
    conv = get_conversation(conv_id)
    if not conv:
        return jsonify({'error': 'Conversation not found'}), 404
    return jsonify(conv)


@app.route('/api/conversations/<int:conv_id>', methods=['DELETE'])
def api_delete_conversation(conv_id: int):
    """Delete a conversation."""
    from src.storage import delete_conversation
    try:
        delete_conversation(conv_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/conversations/<int:conv_id>/entries', methods=['GET'])
def api_get_entries(conv_id: int):
    """Get all entries for a conversation."""
    entries = get_all_entries(conv_id)
    return jsonify(entries)


@app.route('/api/conversations/<int:conv_id>/entries', methods=['POST'])
def api_add_entry(conv_id: int):
    """Add a user entry to conversation."""
    data = request.get_json() or {}
    content = data.get('content', '')
    
    if not content:
        return jsonify({'error': 'Content is required'}), 400
    
    conv = get_conversation(conv_id)
    if not conv:
        return jsonify({'error': 'Conversation not found'}), 404
    
    append_entry(conv_id, 'user', conv['round'], content)
    
    return jsonify({'success': True})


@app.route('/api/conversations/<int:conv_id>/selection', methods=['POST'])
def api_save_selection(conv_id: int):
    """Save user selection."""
    data = request.get_json() or {}
    direction = data.get('direction')
    feedback = data.get('feedback')
    
    conv = get_conversation(conv_id)
    if not conv:
        return jsonify({'error': 'Conversation not found'}), 404
    
    save_user_selection(conv_id, conv['round'], direction, feedback)
    
    return jsonify({'success': True})


def run_workflow_async(conv_id: int):
    """Run workflow in a separate thread."""
    broadcaster = workflow_broadcaster(conv_id)
    try:
        result = resume_workflow(conv_id, broadcaster)

        if result.get('action') == 'wait_for_user':
            broadcast_to_conv(conv_id, 'workflow_waiting', {
                'conv_id': conv_id,
                'round': result['round'],
                'phase': result['phase'],
                'state': result.get('state', 'direction_selection')
            })
    except Exception as e:
        broadcast_to_conv(conv_id, 'workflow_error', {
            'error': str(e)
        })


@app.route('/api/conversations/<int:conv_id>/start', methods=['POST'])
def api_start_workflow(conv_id: int):
    """Start workflow for a conversation."""
    conv = get_conversation(conv_id)
    if not conv:
        return jsonify({'error': 'Conversation not found'}), 404

    thread = threading.Thread(target=run_workflow_async, args=(conv_id,))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'started'})


@app.route('/api/conversations/<int:conv_id>/continue', methods=['POST'])
def api_continue_workflow(conv_id: int):
    """Continue workflow after user input."""
    data = request.get_json() or {}
    user_input = data.get('input', '')
    
    conv = get_conversation(conv_id)
    if not conv:
        return jsonify({'error': 'Conversation not found'}), 404
    
    def continue_callback(message: dict):
        broadcast_to_conv(conv_id, 'workflow_event', message)
    
    result = continue_workflow(conv_id, user_input, continue_callback)
    
    if result.get('action') == 'wait_for_user':
        return jsonify({
            'action': 'waiting',
            'round': result['round'],
            'phase': result['phase']
        })
    elif result.get('action') == 'complete':
        return jsonify({
            'action': 'complete',
            'verdict': result.get('verdict'),
            'outline': result.get('outline')
        })
    else:
        return jsonify(result)


@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    client_id = request.sid
    CLIENTS[client_id] = {'rooms': []}
    print(f'Client connected: {client_id}')


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    client_id = request.sid
    if client_id in CLIENTS:
        for room in CLIENTS[client_id].get('rooms', []):
            leave_room(room)
        del CLIENTS[client_id]
    print(f'Client disconnected: {client_id}')


@socketio.on('join_conversation')
def handle_join_conversation(data):
    """Join a conversation room."""
    conv_id = data.get('conv_id')
    if conv_id:
        room = f'conv_{conv_id}'
        join_room(room)
        if request.sid in CLIENTS:
            CLIENTS[request.sid]['rooms'].append(room)
        emit('joined', {'room': room})


@socketio.on('leave_conversation')
def handle_leave_conversation(data):
    """Leave a conversation room."""
    conv_id = data.get('conv_id')
    if conv_id:
        room = f'conv_{conv_id}'
        leave_room(room)
        if request.sid in CLIENTS:
            if room in CLIENTS[request.sid]['rooms']:
                CLIENTS[request.sid]['rooms'].remove(room)


@socketio.on('send_message')
def handle_send_message(data):
    """Handle user message."""
    conv_id = data.get('conv_id')
    message = data.get('message', '')
    
    if not conv_id or not message:
        emit('error', {'message': 'Invalid data'})
        return
    
    conv = get_conversation(conv_id)
    if not conv:
        emit('error', {'message': 'Conversation not found'})
        return
    
    append_entry(conv_id, 'user', conv['round'], message)

    broadcast_to_conv(conv_id, 'message_received', {
        'conv_id': conv_id,
        'agent': 'user',
        'content': message,
        'timestamp': datetime.now().isoformat()
    })

    def continue_workflow_async():
        def continue_callback(msg):
            broadcast_to_conv(conv_id, 'workflow_event', msg)

        try:
            result = continue_workflow(conv_id, message, continue_callback)

            if result.get('action') == 'wait_for_user':
                broadcast_to_conv(conv_id, 'workflow_waiting', {
                    'conv_id': conv_id,
                    'round': result['round'],
                    'phase': result.get('phase', result.get('state', 'feedback'))
                })
            elif result.get('action') == 'complete':
                broadcast_to_conv(conv_id, 'workflow_complete', {
                    'verdict': result.get('verdict'),
                    'outline': result.get('outline')
                })
            elif result.get('action') == 'needs_work' or result.get('action') == 'rejected':
                broadcast_to_conv(conv_id, 'workflow_waiting', {
                    'conv_id': conv_id,
                    'round': result.get('round', 1),
                    'phase': 'feedback'
                })
        except Exception as e:
            broadcast_to_conv(conv_id, 'workflow_error', {
                'error': str(e)
            })

    thread = threading.Thread(target=continue_workflow_async)
    thread.daemon = True
    thread.start()


if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting server on http://localhost:{port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
