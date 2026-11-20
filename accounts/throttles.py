from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Limit brute-force attempts on the login endpoint."""

    scope = "login"
