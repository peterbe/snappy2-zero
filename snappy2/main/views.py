import logging

from django import http

from snappy2.symbolicate.views import symbolicate_json

logger = logging.getLogger('main')


def home(request):
    # Ideally people should...
    # `HTTP -X POST -d JSON http://hostname/symbolicate/`
    # But if they do it directly on the root it should still work,
    # for legacy reasons.
    if request.method == 'POST' and request.body:
        return symbolicate_json(request)

    return http.HttpResponse('No home page yet. See README\n')
