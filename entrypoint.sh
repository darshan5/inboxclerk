#!/bin/bash
set -e

python manage.py migrate --noinput

# Create default admin user if none exists
python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@inboxclerk.com', 'admin')
    print('Created default admin user')
else:
    print('Admin user already exists')
"

exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
