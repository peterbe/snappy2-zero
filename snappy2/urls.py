from django.conf.urls import url, include

import snappy2.symbolicate.urls


urlpatterns = [
    url(
        '',
        include(snappy2.symbolicate.urls.urlpatterns, namespace='main')
    ),
]
