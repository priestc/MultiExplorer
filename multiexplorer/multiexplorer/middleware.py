from multiexplorer.models import IPTracker
from django.http import HttpResponse
from django.conf import settings

class IPLimiterMiddleware(object):
    interval = "%s %s" % (
        list(settings.IP_FILTER_INTERVAL.values())[0],
        list(settings.IP_FILTER_INTERVAL.keys())[0],
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = request.META['REMOTE_ADDR']

        if not request.path.startswith("/api/") or IPTracker.allow(ip):
            response = self.get_response(request)
            return response

        return HttpResponse(
            '{"error": "Too many requests. The limit is %s requests per %s"}' % (
                settings.IP_FILTER_HITS, self.interval
            ),
            content_type="application/json",
            status=429
        )
