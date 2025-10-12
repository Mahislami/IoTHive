# iothive/celery.py

from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'iothive.settings')

app = Celery('iothive')

app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))

# -------------------------------------------------------------------
# Define periodic task schedule
# -------------------------------------------------------------------
app.conf.beat_schedule = {
    # Run the new ticker every 10s (only thermostat + actuator update)
    'tick-dynamic-every-10s': {
        'task': 'devices.tasks.tick_dynamic_devices',
        'schedule': 10.0,
    },

    # Optional: re-run initialization once a day at midnight (if you want).
    # Comment out if you prefer to trigger manually.
    'initialize-daily': {
        'task': 'devices.tasks.initialize_device_state',
        'schedule': crontab(hour=0, minute=0),
    },

    "evaluate-alarms-every-10s": {
    "task": "devices.evaluate_alarms_task",
    "schedule": 10.0,  # seconds; can also use timedelta(seconds=10)
    },
}
