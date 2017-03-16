from django.conf.urls import url, include

import snappy2.main.urls
import snappy2.symbolicate.urls


urlpatterns = [
    url(
        r'^symbolicate/',
        include(snappy2.symbolicate.urls.urlpatterns, namespace='symbolicate')
    ),
    url(
        '',
        include(snappy2.main.urls.urlpatterns, namespace='main')
    ),

]
