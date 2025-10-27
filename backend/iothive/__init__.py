# backend/iothive/__init__.py

try:
    from .celery import app as celery_app
except ModuleNotFoundError:
    # Allow Django commands to run in lightweight environments where Celery
    # dependencies have not been installed yet (e.g., local code review).
    celery_app = None

__all__ = ('celery_app',)
