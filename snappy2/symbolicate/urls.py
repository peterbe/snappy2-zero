from django.conf.urls import url

from . import views

urlpatterns = [
    url(
        r'__hit_ratio__',
        views.hit_ratio,
        name='hit_ratio'
    ),

    # must be last
    url(
        r'',
        views.symbolicate_json,
        name='symbolicate_json'
    ),

]
