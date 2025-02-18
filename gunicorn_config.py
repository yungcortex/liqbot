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
timeout = 120
graceful_timeout = 30
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
proc_name = "liqbot"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Worker lifecycle
def on_starting(server):
    """Initialize server."""
    logger.info("Server starting up")

def when_ready(server):
    """Called just after the server is started."""
    logger.info("Server is ready. Listening on: %s", bind)

def pre_fork(server, worker):
    """Pre-fork initialization."""
    logger.info("Pre-forking worker")
    eventlet.hubs.use_hub()

def post_fork(server, worker):
    """Set up worker after fork."""
    logger.info("Worker spawned (pid: %s)", worker.pid)
    # Ensure eventlet hub is initialized in worker
    eventlet.hubs.use_hub()
    # Clear any existing connections
    if hasattr(worker.wsgi.application, 'socketio'):
        worker.wsgi.application.socketio.server.eio.clients = {}

def pre_exec(server):
    """Pre-exec handler."""
    logger.info("Pre-exec phase")
    server.log.info("Forked child, re-executing.")

def worker_int(worker):
    """Handle worker interruption signals."""
    logger.info("Worker received INT or QUIT signal")
    # Get the current eventlet hub
    hub = eventlet.hubs.get_hub()
    if hub is not None:
        # Stop accepting new connections
        hub.abort()
        # Close all existing sockets
        for sock in hub.descriptors.values():
            try:
                sock.close()
            except Exception:
                pass

def worker_abort(worker):
    """Handle worker abort."""
    logger.info("Worker aborted")
    worker_int(worker)

def worker_exit(server, worker):
    """Clean up after worker exit."""
    logger.info("Worker exiting")
    try:
        # Get the current eventlet hub
        hub = eventlet.hubs.get_hub()
        if hub is not None:
            # Stop the hub
            hub.abort()
            # Clear all descriptors
            hub.descriptors.clear()
    except Exception as e:
        logger.error("Error cleaning up worker: %s", e)

# WebSocket settings
websocket_max_message_size = 1024 * 1024  # 1MB
websocket_ping_interval = 5
websocket_ping_timeout = 10
websocket_per_message_deflate = True

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
    'worker_connections': 1000,
    'websocket_max_message_size': 1024 * 1024,  # 1MB
    'websocket_ping_interval': 5,
    'websocket_ping_timeout': 10,
    'websocket_per_message_deflate': True,
    'keepalive': 5,
    'client_timeout': 30,
    'proxy_protocol': False,
    'proxy_allow_ips': '*',
    'graceful_timeout': 30,
    'timeout': 30
}

# Eventlet settings
worker_connections = 1000
worker_rlimit_nofile = 4096

def on_exit(server):
    """Handle server shutdown."""
    logger.info("Server shutting down")
    # Clean up any remaining connections
    if hasattr(server.app, 'wsgi') and hasattr(server.app.wsgi, 'application'):
        app = server.app.wsgi.application
        if hasattr(app, 'socketio'):
            try:
                # Close all socket connections
                for client in app.socketio.server.eio.clients.values():
                    try:
                        client.close()
                    except Exception:
                        pass
                # Clear all clients
                app.socketio.server.eio.clients.clear()
            except Exception as e:
                logger.error("Error cleaning up SocketIO: %s", e) 