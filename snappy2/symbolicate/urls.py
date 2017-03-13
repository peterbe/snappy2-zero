from django.conf.urls import url

from . import views

urlpatterns = [
    url(
        r'',
        views.symbolicate_json,
        name='symbolicate_json'
    ),
]
