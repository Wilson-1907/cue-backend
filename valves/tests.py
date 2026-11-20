import pytest
from devices.models import Device
from monitoring.models import Pipeline
from valves.models import Valve, ValveCommand
from valves.services import request_command, acknowledge_command, execute_command


@pytest.mark.django_db
def test_valve_command_lifecycle_updates_status_on_execute():
    d = Device.objects.create(device_name="D", device_identifier="D-1")
    p = Pipeline.objects.create(pipeline_name="P", pipeline_code="PC-1")
    v = Valve.objects.create(valve_name="V", valve_identifier="V-1", device=d, pipeline=p)

    cmd = request_command(v, ValveCommand.CommandType.OPEN)
    assert cmd.execution_status == ValveCommand.ExecutionStatus.PENDING

    acknowledge_command(cmd)
    cmd.refresh_from_db()
    assert cmd.execution_status == ValveCommand.ExecutionStatus.RECEIVED

    execute_command(cmd, success=True)
    cmd.refresh_from_db()
    v.refresh_from_db()
    assert cmd.execution_status == ValveCommand.ExecutionStatus.EXECUTED
    assert v.current_status == Valve.Status.OPEN