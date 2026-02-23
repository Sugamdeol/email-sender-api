"""
Notification API - Flask version
Self-hosted ntfy notification server with zero external dependencies.
"""

import os
import json
import time
import hashlib
import hmac
import threading
import subprocess
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Config
API_KEY = os.getenv('API_KEY', 'dev-key-change-in-production')
NTFY_PORT = 2586
NTFY_TOPIC = 'sugam-alerts'

# Simple rate limiter
class RateLimiter:
    def __init__(self, max_req=10, window=60):
        self.max_req = max_req
        self.window = window
        self.requests = {}
    
    def is_allowed(self, client_ip):
        now = time.time()
        if client_ip not in self.requests:
            self.requests[client_ip] = []
        # Clean old
        self.requests[client_ip] = [t for t in self.requests[client_ip] if now - t < self.window]
        if len(self.requests[client_ip]) >= self.max_req:
            return False
        self.requests[client_ip].append(now)
        return True

limiter = RateLimiter()

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get('X-API-Key')
        if not key or key != API_KEY:
            return jsonify({'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated

def check_rate_limit(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ',' in ip:
            ip = ip.split(',')[0].strip()
        if not limiter.is_allowed(ip):
            return jsonify({'error': 'Rate limit exceeded'}), 429
        return f(*args, **kwargs)
    return decorated

# Start ntfy server
def start_ntfy():
    try:
        subprocess.Popen(
            ['ntfy', 'serve', '--listen', f'0.0.0.0:{NTFY_PORT}'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print(f"ntfy server started on port {NTFY_PORT}")
    except Exception as e:
        print(f"Failed to start ntfy: {e}")

# Start ntfy in background
threading.Thread(target=start_ntfy, daemon=True).start()

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'notify-api',
        'timestamp': time.time()
    })

@app.route('/notify', methods=['POST'])
@require_api_key
@check_rate_limit
def notify():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400
    
    title = data.get('title', 'Notification')
    message = data.get('message', '')
    priority = data.get('priority', 3)
    
    if not message:
        return jsonify({'error': 'message is required'}), 400
    
    try:
        import requests
        resp = requests.post(
            f'http://localhost:{NTFY_PORT}/{NTFY_TOPIC}',
            data=message.encode('utf-8'),
            headers={
                'Title': title,
                'Priority': str(priority)
            },
            timeout=5
        )
        if resp.status_code == 200:
            return jsonify({
                'success': True,
                'message': 'Notification sent',
                'topic': NTFY_TOPIC
            })
        else:
            return jsonify({'error': f'ntfy error: {resp.status_code}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route(f'/{NTFY_TOPIC}', methods=['GET'])
def subscribe():
    """SSE endpoint for ntfy subscriptions"""
    def event_stream():
        import requests
        try:
            resp = requests.get(
                f'http://localhost:{NTFY_PORT}/{NTFY_TOPIC}/sse',
                stream=True,
                timeout=None
            )
            for line in resp.iter_lines():
                if line:
                    yield f"data: {line.decode()}\n\n"
        except:
            yield f"data: {{'error': 'connection lost'}}\n\n"
    
    return Response(
        event_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )

@app.route('/')
def root():
    return jsonify({
        'service': 'notify-api',
        'endpoints': {
            'health': '/health',
            'notify': 'POST /notify (requires X-API-Key header)',
            'subscribe': f'GET /{NTFY_TOPIC} (SSE stream)'
        }
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
