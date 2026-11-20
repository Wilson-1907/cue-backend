from django.views.decorators.http import require_GET
from django.http import HttpResponse


@require_GET
def favicon(_request):
    # Empty 204 — browser treats it as "no favicon", no repeated requests
    return HttpResponse(status=204)