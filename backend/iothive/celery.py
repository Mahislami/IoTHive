# iothive/celery.py

from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab  # add this

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'iothive.settings')

app = Celery('iothive')

app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))

# Define periodic task schedule here
app.conf.beat_schedule = {
    'simulate-every-10-seconds': {
        'task': 'devices.tasks.simulate_device_activity',
        'schedule': 10.0  # every 10 seconds
    }
}
