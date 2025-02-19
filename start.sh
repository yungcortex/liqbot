#!/bin/bash

# Set environment variables
export PYTHONUNBUFFERED=1
export EVENTLET_NO_GREENDNS=yes
export EVENTLET_NONBLOCKING=1

# Trap SIGTERM and SIGINT
trap 'kill -TERM $PID' TERM INT

# Start Gunicorn with config file
gunicorn -c gunicorn_config.py 'wsgi:application' &

# Store PID
PID=$!

# Wait for process to complete
wait $PID

# Remove trap
trap - TERM INT

# Wait for process
wait $PID

# Exit with the same code
EXIT_STATUS=$?
exit $EXIT_STATUS 