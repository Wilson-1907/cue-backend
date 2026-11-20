class SimpleRequestLoggingMiddleware:
    """Optional lightweight request logger (method, path, status, duration)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import time
        import logging
        logger = logging.getLogger("request")
        started = time.monotonic()
        response = self.get_response(request)
        duration_ms = (time.monotonic() - started) * 1000
        logger.info("%s %s -> %s in %.1fms", request.method, request.path,
                    response.status_code, duration_ms)
        return response