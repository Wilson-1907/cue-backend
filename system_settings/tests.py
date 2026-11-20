import pytest
from system_settings.models import SystemSettings


@pytest.mark.django_db
def test_load_creates_singleton():
    a = SystemSettings.load()
    b = SystemSettings.load()
    assert a.pk == b.pk
    assert SystemSettings.objects.count() == 1