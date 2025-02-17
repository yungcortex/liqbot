bind = "0.0.0.0:10000"
worker_class = "eventlet"
workers = 1
worker_connections = 1000
keepalive = 120
timeout = 300
graceful_timeout = 300
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
    'EVENTLET_NO_GREENDNS=yes'
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
    'worker_connections': 2000,
    'keepalive': 120,
    'client_timeout': 300,
    'websocket_max_message_size': 0,
    'websocket_ping_interval': 25,
    'websocket_ping_timeout': 120
} 