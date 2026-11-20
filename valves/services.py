from django.utils import timezone
from django.db import transaction
from .models import Valve, ValveCommand
from activity_logs.services import log_action
from notifications.services import create_notification

@transaction.atomic
def request_command(valve: Valve, command_type: str, user=None,
                    idempotency_key: str = "") -> ValveCommand:
    if idempotency_key:
        existing = ValveCommand.objects.filter(valve=valve,
                                               idempotency_key=idempotency_key).first()
        if existing:
            return existing
    cmd = ValveCommand.objects.create(
        valve=valve, command_type=command_type, requested_by=user,
        idempotency_key=idempotency_key,
    )
    log_action(user=user, action=f"VALVE_{command_type}_REQUESTED",
               description=f"Requested {command_type} on valve {valve.valve_name}",
               category="VALVE")
    return cmd

@transaction.atomic
def acknowledge_command(cmd: ValveCommand):
    if cmd.execution_status != ValveCommand.ExecutionStatus.PENDING:
        return cmd
    cmd.execution_status = ValveCommand.ExecutionStatus.RECEIVED
    cmd.acknowledged_at = timezone.now()
    cmd.save(update_fields=["execution_status", "acknowledged_at", "updated_at"])
    return cmd

@transaction.atomic
def execute_command(cmd: ValveCommand, success: bool, message: str = ""):
    cmd.execution_status = (ValveCommand.ExecutionStatus.EXECUTED
                            if success else ValveCommand.ExecutionStatus.FAILED)
    cmd.executed_at = timezone.now()
    cmd.response_message = message or ("Executed successfully" if success else "Execution failed")
    cmd.save(update_fields=["execution_status", "executed_at", "response_message", "updated_at"])
    if success:
        valve = cmd.valve
        if cmd.command_type == ValveCommand.CommandType.OPEN:
            valve.current_status = Valve.Status.OPEN
        elif cmd.command_type == ValveCommand.CommandType.CLOSE:
            valve.current_status = Valve.Status.CLOSED
        elif cmd.command_type == ValveCommand.CommandType.SET_MODE_AUTO:
            valve.control_mode = Valve.ControlMode.AUTOMATIC
        elif cmd.command_type == ValveCommand.CommandType.SET_MODE_MANUAL:
            valve.control_mode = Valve.ControlMode.MANUAL
        valve.save()
        create_notification(
            title=f"Valve {cmd.command_type.title()} executed",
            message=f"Valve {valve.valve_name} confirmed {cmd.command_type.lower()}.",
            notification_type="VALVE_STATUS_CHANGED",
            severity="INFO",
        )
    return cmd