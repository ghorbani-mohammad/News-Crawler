from django.contrib import admin
from django.urls import path, re_path, include
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    path("secret-admin/", admin.site.urls),
    re_path("api/(?P<version>(v1|v2))/", include("agency.urls")),
]

urlpatterns += staticfiles_urlpatterns()

admin.site.index_title = "Crawler"
admin.site.site_title = "Crawler Admin"
admin.site.site_header = "Crawler Administration Panel"
