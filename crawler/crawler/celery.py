from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab
from django.conf import settings

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crawler.settings")

crawler = Celery("crawler")
crawler.config_from_object("django.conf:settings")
crawler.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# if you want to purge works queue
crawler.control.purge()

MINUTE = 60

crawler.conf.beat_schedule = {
    "check-agencies-60-seconds": {
        "task": "check_agencies",
        "schedule": 10 * MINUTE,
    },
    "redis-exporter-300-seconds": {
        "task": "redis_exporter",
        "schedule": 5 * MINUTE,
    },
    "remove_obsolete_reports": {
        "task": "remove_obsolete_reports",
        "schedule": crontab(minute=0, hour=0),
    },
}
