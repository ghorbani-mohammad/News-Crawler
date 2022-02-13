import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
application = get_wsgi_application()


from agency.models import AgencyPageStructure, CrawlReport

print(
    '********* {} update: lock=False *****'.format(
        AgencyPageStructure.objects.filter(lock=True).update(lock=False)
    )
)
print(
    '********* {} update: status=faild *****'.format(
        CrawlReport.objects.filter(status='pending').update(status='failed')
    )
)
