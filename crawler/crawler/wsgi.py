import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crawler.settings")
application = get_wsgi_application()


from agency.models import AgencyPageStructure, CrawlReport

print(
    f"***** {AgencyPageStructure.objects.filter(lock=True).update(lock=False)} update: lock=False *****"
)
print(
    f"********* {CrawlReport.objects.filter(status='pending').update(status='failed')} update: status=failed *****"
)
