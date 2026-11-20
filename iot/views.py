from django.db import transaction, IntegrityError
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework import status
from core.utils import success_response, created_response, error_response
from devices.models import Device, DeviceCommunicationLog
from monitoring.models import Sensor, FlowReading
from valves.models import Valve, ValveCommand
from valves.services import acknowledge_command, execute_command
from notifications.services import create_notification
from activity_logs.services import log_action
from .permissions import IsDevice
from .serializers import (ReadingIngestSerializer, BulkReadingsSerializer,
                          HeartbeatSerializer, DeviceRegisterSerializer,
                          DeviceStatusSerializer, DeviceWarningSerializer,
                          ValveStatusReportSerializer)

def _principal(request):
    return getattr(request.user, "device", None)

def _ensure_sensor(device: Device, sensor_identifier: str) -> Sensor | None:
    return Sensor.objects.filter(device=device, sensor_identifier=sensor_identifier).first()

def _persist_reading(device: Device, payload: dict) -> FlowReading:
    sensor = _ensure_sensor(device, payload["sensor_id"])
    if not sensor:
        raise ValueError(f"Unknown sensor {payload['sensor_id']} for this device")
    try:
        with transaction.atomic():
            reading = FlowReading.objects.create(
                sensor=sensor, device=device,
                flow_rate=payload["flow_rate"],
                volume=payload["volume"],
                pulse_count=payload.get("pulse_count", 0),
                reading_timestamp=payload["timestamp"],
            )
    except IntegrityError:
        # Duplicate - idempotent return
        return FlowReading.objects.filter(
            sensor=sensor,
            reading_timestamp=payload["timestamp"],
            pulse_count=payload.get("pulse_count", 0),
        ).first()
    # broadcast & leak eval
    try:
        from config.broadcast import broadcast_flow_reading
        broadcast_flow_reading(reading)
    except Exception:
        pass
    if sensor.pipeline_id:
        try:
            from leak_detection.services import evaluate_pipeline
            evaluate_pipeline(sensor.pipeline)
        except Exception:
            pass
    return reading

class ReadingIngestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "iot"

    def post(self, request):
        from iot.authentication import DeviceAuthentication
        principal = None
        try:
            auth = DeviceAuthentication()
            principal = auth.authenticate(request)
        except Exception:
            return error_response("Device authentication failed", status_code=status.HTTP_401_UNAUTHORIZED)
        if not principal:
            return error_response("Device credentials required", status_code=status.HTTP_401_UNAUTHORIZED)
        device = principal[0].device

        serializer = ReadingIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        if payload["device_id"] != device.device_identifier:
            return error_response("Device identifier mismatch")
        try:
            reading = _persist_reading(device, payload)
        except ValueError as ve:
            return error_response(str(ve), {"sensor_id": [str(ve)]})
        device.mark_connected()
        DeviceCommunicationLog.objects.create(device=device, kind="READING",
                                              payload={"sensor": payload["sensor_id"]})
        return created_response({"id": reading.id if reading else None}, "Reading recorded")

class BulkReadingsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        from iot.authentication import DeviceAuthentication
        auth = DeviceAuthentication()
        principal = auth.authenticate(request)
        if not principal:
            return error_response("Device credentials required", status_code=status.HTTP_401_UNAUTHORIZED)
        device = principal[0].device
        serializer = BulkReadingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        accepted = 0
        errors = []
        for item in serializer.validated_data["readings"]:
            if item["device_id"] != device.device_identifier:
                errors.append({"sensor_id": item["sensor_id"], "error": "device mismatch"})
                continue
            try:
                _persist_reading(device, item)
                accepted += 1
            except ValueError as ve:
                errors.append({"sensor_id": item["sensor_id"], "error": str(ve)})
        device.mark_connected()
        return created_response({"accepted": accepted, "errors": errors}, "Bulk ingested")

class SensorReadingView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, pk):
        from iot.authentication import DeviceAuthentication
        auth = DeviceAuthentication()
        principal = auth.authenticate(request)
        if not principal:
            return error_response("Device credentials required", status_code=status.HTTP_401_UNAUTHORIZED)
        device = principal[0].device
        sensor = Sensor.objects.filter(pk=pk, device=device).first()
        if not sensor:
            return error_response("Sensor not found for this device", status_code=status.HTTP_404_NOT_FOUND)
        payload = {
            "device_id": device.device_identifier,
            "sensor_id": sensor.sensor_identifier,
            "flow_rate": request.data.get("flow_rate"),
            "volume": request.data.get("volume"),
            "pulse_count": request.data.get("pulse_count", 0),
            "timestamp": request.data.get("timestamp"),
        }
        serializer = ReadingIngestSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        reading = _persist_reading(device, serializer.validated_data)
        return created_response({"id": reading.id if reading else None}, "Reading recorded")

class SensorConfigView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, pk):
        from iot.authentication import DeviceAuthentication
        auth = DeviceAuthentication()
        principal = auth.authenticate(request)
        if not principal:
            return error_response("Device credentials required", status_code=status.HTTP_401_UNAUTHORIZED)
        sensor = Sensor.objects.filter(pk=pk, device=principal[0].device).first()
        if not sensor:
            return error_response("Sensor not found", status_code=status.HTTP_404_NOT_FOUND)
        return success_response({
            "sensor_identifier": sensor.sensor_identifier,
            "calibration_factor": sensor.calibration_factor,
            "sensor_position": sensor.sensor_position,
        })

class HeartbeatView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        from iot.authentication import DeviceAuthentication
        auth = DeviceAuthentication()
        principal = auth.authenticate(request)
        if not principal:
            return error_response("Device credentials required", status_code=status.HTTP_401_UNAUTHORIZED)
        device = principal[0].device
        serializer = HeartbeatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data["device_id"] != device.device_identifier:
            return error_response("Device identifier mismatch")
        device.mark_connected()
        if serializer.validated_data.get("firmware_version"):
            device.firmware_version = serializer.validated_data["firmware_version"]
            device.save(update_fields=["firmware_version"])
        DeviceCommunicationLog.objects.create(device=device, kind="HEARTBEAT",
                                              payload=serializer.validated_data)
        return success_response({"server_time": __import__("django.utils.timezone", fromlist=["now"]).now()},
                                "Heartbeat accepted")

class DeviceRegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = DeviceRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        device, created = Device.objects.get_or_create(
            device_identifier=data["device_identifier"],
            defaults={
                "device_name": data["device_name"],
                "device_type": data["device_type"],
                "location": data.get("location", ""),
                "firmware_version": data.get("firmware_version", ""),
                "connection_status": Device.ConnectionStatus.DISCONNECTED,
            }
        )
        if created:
            raw = Device.generate_api_key()
            device.set_api_key(raw)
            return created_response({
                "device_id": device.id,
                "device_identifier": device.device_identifier,
                "api_key": raw,
            }, "Device registered. Store api_key securely.")
        return error_response("Device already registered",
                              status_code=status.HTTP_409_CONFLICT)

class DeviceStatusReportView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        from iot.authentication import DeviceAuthentication
        auth = DeviceAuthentication()
        principal = auth.authenticate(request)
        if not principal:
            return error_response("Device credentials required", status_code=status.HTTP_401_UNAUTHORIZED)
        device = principal[0].device
        serializer = DeviceStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device.mark_connected()
        DeviceCommunicationLog.objects.create(device=device, kind="STATUS",
                                              payload=serializer.validated_data)
        return success_response({"acknowledged": True})

class DeviceWarningView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        from iot.authentication import DeviceAuthentication
        auth = DeviceAuthentication()
        principal = auth.authenticate(request)
        if not principal:
            return error_response("Device credentials required", status_code=status.HTTP_401_UNAUTHORIZED)
        device = principal[0].device
        serializer = DeviceWarningSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        create_notification(
            title=serializer.validated_data["title"],
            message=f"[{device.device_name}] {serializer.validated_data['message']}",
            notification_type="HARDWARE_WARNING",
            severity=serializer.validated_data.get("severity", "WARNING"),
        )
        log_action(device=device, action="HARDWARE_WARNING",
                   description=serializer.validated_data["title"], category="DEVICE")
        return success_response({"acknowledged": True})

class DeviceConfigView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, pk):
        from iot.authentication import DeviceAuthentication
        auth = DeviceAuthentication()
        principal = auth.authenticate(request)
        if not principal:
            return error_response("Device credentials required", status_code=status.HTTP_401_UNAUTHORIZED)
        device = principal[0].device
        if device.id != int(pk):
            return error_response("Forbidden", status_code=status.HTTP_403_FORBIDDEN)
        return success_response({
            "device_identifier": device.device_identifier,
            "heartbeat_interval_seconds": 30,
            "sensors": list(device.sensors.values("id", "sensor_identifier",
                                                  "sensor_position", "calibration_factor")),
        })

class PendingCommandsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        from iot.authentication import DeviceAuthentication
        auth = DeviceAuthentication()
        principal = auth.authenticate(request)
        if not principal:
            return error_response("Device credentials required", status_code=status.HTTP_401_UNAUTHORIZED)
        device = principal[0].device
        cmds = ValveCommand.objects.filter(valve__device=device,
                                           execution_status=ValveCommand.ExecutionStatus.PENDING)
        data = [{
            "id": c.id,
            "valve_id": c.valve_id,
            "valve_identifier": c.valve.valve_identifier,
            "command_type": c.command_type,
            "requested_at": c.requested_at,
        } for c in cmds]
        return success_response({"commands": data})

class AcknowledgeCommandView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, pk):
        from iot.authentication import DeviceAuthentication
        auth = DeviceAuthentication()
        principal = auth.authenticate(request)
        if not principal:
            return error_response("Device credentials required", status_code=status.HTTP_401_UNAUTHORIZED)
        cmd = ValveCommand.objects.filter(pk=pk, valve__device=principal[0].device).first()
        if not cmd:
            return error_response("Command not found", status_code=status.HTTP_404_NOT_FOUND)
        acknowledge_command(cmd)
        return success_response({"status": cmd.execution_status})

class ExecuteCommandView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, pk):
        from iot.authentication import DeviceAuthentication
        auth = DeviceAuthentication()
        principal = auth.authenticate(request)
        if not principal:
            return error_response("Device credentials required", status_code=status.HTTP_401_UNAUTHORIZED)
        cmd = ValveCommand.objects.filter(pk=pk, valve__device=principal[0].device).first()
        if not cmd:
            return error_response("Command not found", status_code=status.HTTP_404_NOT_FOUND)
        success = bool(request.data.get("success", True))
        message = request.data.get("message", "")
        execute_command(cmd, success, message)
        return success_response({"status": cmd.execution_status})

class ValveStatusReportView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, pk):
        from iot.authentication import DeviceAuthentication
        auth = DeviceAuthentication()
        principal = auth.authenticate(request)
        if not principal:
            return error_response("Device credentials required", status_code=status.HTTP_401_UNAUTHORIZED)
        valve = Valve.objects.filter(pk=pk, device=principal[0].device).first()
        if not valve:
            return error_response("Valve not found", status_code=status.HTTP_404_NOT_FOUND)
        serializer = ValveStatusReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valve.current_status = serializer.validated_data["status"]
        valve.save(update_fields=["current_status", "updated_at"])
        create_notification(
            title="Valve state confirmed by hardware",
            message=f"Valve {valve.valve_name} reported {valve.current_status}.",
            notification_type="VALVE_STATUS_CHANGED",
            severity="INFO",
        )
        return success_response({"current_status": valve.current_status})