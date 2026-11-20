from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import RoleReadOnlyOrAdmin
from core.utils import success_response

from .models import Device, DeviceCommunicationLog
from .serializers import DeviceCommunicationLogSerializer, DeviceSerializer
from . import services


class DeviceListView(APIView):
    """Production inventory with live sensor/valve/heartbeat accuracy."""

    permission_classes = [IsAuthenticated, RoleReadOnlyOrAdmin]

    def get(self, request):
        services.sync_stale_devices()
        qs = Device.objects.all().prefetch_related("sensors", "valves").order_by("device_name")
        dtype = request.query_params.get("device_type")
        status = request.query_params.get("connection_status")
        search = (request.query_params.get("search") or "").strip()
        if dtype:
            qs = qs.filter(device_type=dtype)
        if status:
            qs = qs.filter(connection_status=status)
        if search:
            from django.db.models import Q

            qs = qs.filter(
                Q(device_name__icontains=search)
                | Q(device_identifier__icontains=search)
                | Q(location__icontains=search)
            )
        rows = [services.device_inventory_row(d) for d in qs]
        # Optional post-filter by effective connection
        eff = request.query_params.get("effective_status")
        if eff:
            rows = [r for r in rows if r["connection_status"] == eff]
        return success_response(
            {
                "devices": rows,
                "summary": services.inventory_summary(rows),
            }
        )

class ConnectedDeviceListView(generics.ListAPIView):
    queryset = Device.objects.filter(connection_status=Device.ConnectionStatus.CONNECTED)
    serializer_class = DeviceSerializer
    permission_classes = [IsAuthenticated]

class DisconnectedDeviceListView(generics.ListAPIView):
    queryset = Device.objects.filter(connection_status=Device.ConnectionStatus.DISCONNECTED)
    serializer_class = DeviceSerializer
    permission_classes = [IsAuthenticated]

class DeviceDetailView(generics.RetrieveAPIView):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    permission_classes = [IsAuthenticated]

class DeviceStatusView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        d = Device.objects.get(pk=pk)
        return success_response({
            "id": d.id, "device_identifier": d.device_identifier,
            "connection_status": d.connection_status,
            "last_communication": d.last_communication,
        })

class DeviceHealthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        services.sync_stale_devices()
        d = Device.objects.prefetch_related("sensors", "valves").get(pk=pk)
        row = services.device_inventory_row(d)
        row["healthy"] = row["health"] == "HEALTHY"
        row["device"] = d.device_identifier
        return success_response(row)

class DeviceCommunicationsView(generics.ListAPIView):
    serializer_class = DeviceCommunicationLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return DeviceCommunicationLog.objects.filter(device_id=self.kwargs["pk"])