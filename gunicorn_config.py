import os
import eventlet

# Server socket settings
bind = "0.0.0.0:10000"
backlog = 2048

# Worker processes
worker_class = "eventlet"
workers = 1
worker_connections = 1000

# Timeouts
timeout = 300  # 5 minutes
keepalive = 120
graceful_timeout = 60

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "debug"

# Environment settings
raw_env = [
    "PYTHONUNBUFFERED=1",
    "EVENTLET_NO_GREENDNS=yes",
    "EVENTLET_WEBSOCKET=true",
    "EVENTLET_SERVE_METHOD=eventlet"
]

# Preload application
preload_app = True

def post_fork(server, worker):
    """Monkey patch after forking worker processes."""
    eventlet.monkey_patch()

def worker_int(worker):
    """Handle worker interruption signals."""
    worker.log.info("worker received INT or QUIT signal")

# WebSocket specific settings
worker_class_args = {
    'worker_connections': 1000,
    'websocket_max_message_size': 16 * 1024 * 1024,  # 16MB
    'websocket_ping_interval': 25,  # Send ping every 25 seconds
    'websocket_ping_timeout': 120  # Wait 120 seconds for pong response
} 