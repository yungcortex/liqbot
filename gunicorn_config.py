import eventlet
eventlet.monkey_patch()

import os
import logging

# Configure logging
logger = logging.getLogger('gunicorn.error')

# Server socket settings
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"
backlog = 2048

# Worker processes
workers = 1
worker_class = "eventlet"
worker_connections = 1000
threads = 1

# Timeouts
timeout = 300
graceful_timeout = 60
keepalive = 5

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
max_requests = 0
max_requests_jitter = 0
worker_tmp_dir = None

# Worker lifecycle
def on_starting(server):
    """Initialize server."""
    logger.info("Server starting up")
    eventlet.hubs.use_hub()

def when_ready(server):
    """Called just after the server is started."""
    logger.info("Server is ready. Listening on: %s", bind)

def pre_fork(server, worker):
    """Pre-fork initialization."""
    logger.info("Pre-forking worker")
    eventlet.hubs.use_hub()

def post_fork(server, worker):
    """Set up worker after fork."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)
    # Initialize eventlet hub
    eventlet.hubs.use_hub()

def pre_exec(server):
    """Pre-exec handler."""
    logger.info("Pre-exec phase")
    server.log.info("Forked child, re-executing.")

def worker_int(worker):
    """Handle worker interruption signals."""
    worker.log.info("worker received INT or QUIT signal")
    
    import sys
    sys.exit(0)

def worker_abort(worker):
    """Handle worker abort."""
    worker.log.info("worker received SIGABRT signal")

def worker_exit(server, worker):
    """Clean up after worker exit."""
    logger.info("Worker exiting")
    try:
        # Get the current eventlet hub
        hub = eventlet.hubs.get_hub()
        if hub is not None:
            # Stop the hub
            hub.abort()
            # Clear all sockets
            if hasattr(hub, 'sockets'):
                hub.sockets.clear()
    except Exception as e:
        logger.error("Error cleaning up worker: %s", e)

# WebSocket settings
websocket_max_message_size = 1024 * 1024  # 1MB
websocket_ping_interval = 25
websocket_ping_timeout = 60
websocket_per_message_deflate = False  # Disable compression for stability

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
    'worker_connections': 2000,
    'websocket_max_message_size': 1024 * 1024,
    'websocket_ping_interval': 25,
    'websocket_ping_timeout': 60,
    'websocket_per_message_deflate': False,
    'keepalive': 65,
    'client_timeout': 60,
    'proxy_protocol': True,
    'proxy_allow_ips': '*',
    'graceful_timeout': 60,
    'timeout': 300,
    'backlog': 2048
}

# Eventlet settings
worker_connections = 1000
worker_rlimit_nofile = 4096

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