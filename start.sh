#!/bin/bash
exec gunicorn -c gunicorn_config.py wsgi:application 