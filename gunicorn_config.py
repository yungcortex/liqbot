bind = "0.0.0.0:10000"
worker_class = "eventlet"
workers = 1
worker_connections = 1000
keepalive = 120
timeout = 0  # Disable timeout for WebSocket connections
graceful_timeout = 60
max_requests = 0
max_requests_jitter = 0

# Logging
errorlog = "-"
loglevel = "debug"
accesslog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Environment settings
raw_env = [
    'PYTHONUNBUFFERED=1',
    'EVENTLET_NO_GREENDNS=yes',
    'EVENTLET_WEBSOCKET=true',
    'EVENTLET_SERVE_METHOD=eventlet'
]

# Worker settings
worker_tmp_dir = "/dev/shm"
preload_app = True
reload = False
daemon = False

# WebSocket specific
wsgi_app = "wsgi:application"

# Additional settings for better WebSocket handling
worker_class_args = {
    'worker_connections': 1000,
    'keepalive': 120,
    'client_timeout': 0,  # Disable client timeout for WebSocket
    'websocket_max_message_size': 0,
    'websocket_ping_interval': 25,
    'websocket_ping_timeout': 120
}

def post_fork(server, worker):
    """Monkey patch after forking worker processes."""
    import eventlet
    eventlet.monkey_patch()

def worker_int(worker):
    """Force eventlet worker."""
    import eventlet
    eventlet.monkey_patch()
    return eventlet.listen(('0.0.0.0', 10000)) 