from django.http import HttpResponse
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from core.utils import error_response, success_response

from .services import chat
from .voice import msingi_configured, synthesize_speech


class MsingiChatView(APIView):
    """POST {message, history?} → {reply, source, lang} (Kiswahili)."""

    permission_classes = [AllowAny]
    authentication_classes = []  # public widget on marketing + app pages

    def post(self, request):
        message = (request.data.get("message") or "").strip()
        if not message:
            return error_response("Tafadhali tuma ujumbe (message).", status_code=400)
        history = request.data.get("history") or []
        if not isinstance(history, list):
            history = []
        result = chat(message, history=history[:12])
        result["tts"] = msingi_configured()
        return success_response(result, message="CUE Assistance amejibu")


class MsingiSpeakView(APIView):
    """POST {text} → audio/wav via MsingiAI TTS (key stays on server)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        text = (request.data.get("text") or "").strip()
        if not text:
            return error_response("Tafadhali tuma text.", status_code=400)
        if not msingi_configured():
            return error_response("Msingi TTS haijasanidiwa (MSINGI_API_KEY).", status_code=503)
        audio = synthesize_speech(text, voice_id=request.data.get("voice_id"))
        if not audio:
            return error_response("Imeshindikana kutengeneza sauti.", status_code=502)
        return HttpResponse(audio, content_type="audio/wav")


class MsingiHealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return success_response(
            {
                "name": "CUE Assistance",
                "lang": "sw",
                "voice": True,
                "text": True,
                "msingi_tts": msingi_configured(),
                "contact_icons": True,
            }
        )
