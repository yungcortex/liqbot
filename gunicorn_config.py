import eventlet
eventlet.monkey_patch()

import os

# Server socket settings
bind = "0.0.0.0:" + str(os.getenv("PORT", "10000"))
backlog = 2048

# Worker processes
workers = 1  # Single worker to avoid session conflicts
worker_class = "eventlet"
worker_connections = 1000

# Timeouts
timeout = 120
keepalive = 5
graceful_timeout = 30

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# SSL
keyfile = None
certfile = None

# Security
limit_request_line = 0
limit_request_fields = 0

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

def on_exit(server):
    """Clean up on exit."""
    server.log.info("Shutting down")

# WebSocket settings
websocket_max_message_size = 16 * 1024 * 1024  # 16MB
websocket_ping_interval = 25
websocket_ping_timeout = 60
websocket_per_message_deflate = True

# Environment settings
raw_env = [
    "PYTHONUNBUFFERED=1",
]

# Preload app
preload_app = True

# Disable request line length check
limit_request_line = 0

# Increase max request fields
limit_request_fields = 0
limit_request_field_size = 0

# Enable keep-alive
keepalive = 5

# Set buffer size
buffer_size = 65535

def worker_int(worker):
    """Handle worker interruption signals."""
    worker.log.info("worker received INT or QUIT signal")

# WebSocket specific settings
worker_class_args = {
    'worker_connections': 2000,
    'websocket_max_message_size': 16 * 1024 * 1024,  # 16MB
    'websocket_ping_interval': 25,  # Send ping every 25 seconds
    'websocket_ping_timeout': 120  # Wait 120 seconds for pong response
} 