worker_class = 'eventlet'
wsgi_app = 'wsgi:application'
bind = "0.0.0.0:10000"
workers = 1
worker_connections = 1000
keepalive = 65
timeout = 120
graceful_timeout = 120
forwarded_allow_ips = '*'
proxy_protocol = True
proxy_allow_ips = '*'
preload_app = True
reload = False
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None
errorlog = '-'
loglevel = 'debug'
accesslog = '-'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
proc_name = None
raw_env = [
    'PYTHONUNBUFFERED=1',
    'EVENTLET_NO_GREENDNS=yes',
    'EVENTLET_WEBSOCKET=True',
    'EVENTLET_SERVE_METHOD=eventlet'
]

# WebSocket specific settings
websocket_ping_interval = 25
websocket_ping_timeout = 60
websocket_max_message_size = 0
worker_tmp_dir = '/dev/shm' 