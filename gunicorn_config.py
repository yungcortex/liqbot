import eventlet
eventlet.monkey_patch()

import os
import logging

# Configure logging
logger = logging.getLogger('gunicorn.error')

# Server socket settings
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"
backlog = 512

# Worker processes - keep single worker for WebSocket
workers = 1
worker_class = "eventlet"
worker_connections = 500
threads = 1

# Timeouts - increased for WebSocket stability
timeout = 60
graceful_timeout = 20
keepalive = 20

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# SSL
keyfile = None
certfile = None

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Process naming
proc_name = "liqbot"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Worker settings
max_requests = 500
max_requests_jitter = 50
worker_tmp_dir = None

def on_starting(server):
    """Initialize server."""
    logger.info("Server starting up")

def when_ready(server):
    """Called just after the server is started."""
    logger.info("Server is ready. Listening on: %s", bind)

def post_fork(server, worker):
    """Set up worker after fork."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def worker_int(worker):
    """Handle worker interruption signals."""
    worker.log.info("worker received INT or QUIT signal")

def worker_abort(worker):
    """Handle worker abort."""
    worker.log.info("worker received SIGABRT signal")

def worker_exit(server, worker):
    """Clean up after worker exit."""
    logger.info("Worker exiting")

# WebSocket settings
websocket_max_message_size = 1024 * 1024  # 1MB
websocket_ping_interval = 15
websocket_ping_timeout = 30
websocket_per_message_deflate = False

# Environment settings
raw_env = [
    "PYTHONUNBUFFERED=1",
]

# Preload app for faster worker spawning
preload_app = True

# Buffer size
buffer_size = 65535

# Worker class args
worker_class_args = {
    'worker_connections': 500,
    'keepalive': 20,
    'client_timeout': 60,
    'proxy_protocol': False,
    'proxy_allow_ips': '*',
    'graceful_timeout': 20,
    'timeout': 60,
    'backlog': 512
}

# Eventlet settings
worker_connections = 500
worker_rlimit_nofile = 1024

def on_exit(server):
    """Handle server shutdown."""
    logger.info("Server shutting down")
    try:
        if hasattr(server, 'app') and hasattr(server.app, 'wsgi'):
            app = server.app.wsgi
            if hasattr(app, 'socketio'):
                # Gracefully disconnect all clients
                for sid, socket in app.socketio.server.eio.sockets.items():
                    try:
                        socket.close()
                    except Exception:
                        pass
                app.socketio.server.disconnect()
    except Exception as e:
        logger.error(f"Error in on_exit: {e}") 