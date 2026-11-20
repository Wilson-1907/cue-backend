from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware

@database_sync_to_async
def _get_user(token: str):
    from rest_framework_simplejwt.tokens import AccessToken
    from django.contrib.auth import get_user_model
    try:
        payload = AccessToken(token)
        return get_user_model().objects.get(id=payload["user_id"], is_active=True)
    except Exception:
        return None

class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        qs = parse_qs(scope["query_string"].decode())
        token = (qs.get("token") or [None])[0]
        scope["user"] = (await _get_user(token)) if token else None
        return await super().__call__(scope, receive, send)