from django.urls import path
from .consumers import AuthGroupConsumer

websocket_urlpatterns = [
    path("ws/stream/", AuthGroupConsumer.as_asgi()),
]