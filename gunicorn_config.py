import eventlet
eventlet.monkey_patch()

import os

# Server socket settings
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"
backlog = 2048

# Worker processes
workers = 1
worker_class = "eventlet"
worker_connections = 1000

# Timeouts
timeout = 120
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# SSL
keyfile = None
certfile = None

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Process naming
proc_name = None

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

def post_fork(server, worker):
    """Set up worker after fork."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)
    eventlet.hubs.use_hub()

def worker_int(worker):
    """Handle worker interruption signals."""
    worker.log.info("worker received INT or QUIT signal")

def worker_exit(server, worker):
    """Clean up after worker exit."""
    try:
        hub = eventlet.hubs.get_hub()
        if hub:
            hub.abort()
    except Exception:
        pass

# WebSocket settings
websocket_max_message_size = 1024 * 1024  # 1MB
websocket_ping_interval = 10
websocket_ping_timeout = 30
websocket_per_message_deflate = True

# Environment settings
raw_env = [
    "PYTHONUNBUFFERED=1",
]

# Preload app
preload_app = True

# Buffer size
buffer_size = 65535

# Worker class args
worker_class_args = {
    'worker_connections': 1000,
    'websocket_max_message_size': 1024 * 1024,  # 1MB
    'websocket_ping_interval': 10,
    'websocket_ping_timeout': 30,
    'websocket_per_message_deflate': True,
    'keepalive': 5,
    'client_timeout': 60,
    'proxy_protocol': False,
    'proxy_allow_ips': '*'
} 