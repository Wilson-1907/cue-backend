from rest_framework.views import APIView
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from core.permissions import IsOperatorOrAdmin
from core.utils import created_response, error_response
from .models import Valve, ValveCommand
from .serializers import ValveSerializer, ValveCommandSerializer
from .services import request_command

class ValveListView(generics.ListAPIView):
    queryset = Valve.objects.all()
    serializer_class = ValveSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["current_status", "control_mode"]

class ValveOpenListView(generics.ListAPIView):
    queryset = Valve.objects.filter(current_status=Valve.Status.OPEN)
    serializer_class = ValveSerializer
    permission_classes = [IsAuthenticated]

class ValveClosedListView(generics.ListAPIView):
    queryset = Valve.objects.filter(current_status=Valve.Status.CLOSED)
    serializer_class = ValveSerializer
    permission_classes = [IsAuthenticated]

class ValveDetailView(generics.RetrieveAPIView):
    queryset = Valve.objects.all()
    serializer_class = ValveSerializer
    permission_classes = [IsAuthenticated]

class _ValveCommandAction(APIView):
    permission_classes = [IsAuthenticated, IsOperatorOrAdmin]
    command_type = None

    def post(self, request, pk):
        try:
            valve = Valve.objects.get(pk=pk)
        except Valve.DoesNotExist:
            return error_response(
                "Valve not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        cmd = request_command(valve, self.command_type, user=request.user)
        return created_response(
            ValveCommandSerializer(cmd).data,
            "Command submitted — awaiting hardware confirmation",
        )

class ValveOpenView(_ValveCommandAction):
    command_type = ValveCommand.CommandType.OPEN

class ValveCloseView(_ValveCommandAction):
    command_type = ValveCommand.CommandType.CLOSE

class ValveAutoView(_ValveCommandAction):
    command_type = ValveCommand.CommandType.SET_MODE_AUTO

class ValveManualView(_ValveCommandAction):
    command_type = ValveCommand.CommandType.SET_MODE_MANUAL

class ValveActivitiesView(generics.ListAPIView):
    serializer_class = ValveCommandSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ValveCommand.objects.select_related("valve", "requested_by")