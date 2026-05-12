#!/bin/bash
set -e

python manage.py migrate --noinput

# Create or update admin user
python manage.py shell -c "
from django.contrib.auth.models import User
import os
pwd = os.environ.get('ADMIN_PASSWORD', 'testik1234')
user, created = User.objects.get_or_create(username='admin', defaults={'email': 'admin@inboxclerk.com', 'is_superuser': True, 'is_staff': True})
user.set_password(pwd)
user.is_superuser = True
user.is_staff = True
user.save()
print('Admin user created' if created else 'Admin password updated')
"

exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
