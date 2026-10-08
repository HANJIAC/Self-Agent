from datetime import datetime
from unittest.mock import MagicMock

import pytest

from scheduler import service


@pytest.fixture
def fixed_clock(monkeypatch):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 8, 10, 0, 0)

    monkeypatch.setattr(service, "datetime", FixedDatetime)
    return FixedDatetime.now()


@pytest.fixture
def scheduler(monkeypatch, fixed_clock):
    backend = MagicMock()
    monkeypatch.setattr(service, "BackgroundScheduler", lambda **kwargs: backend)
    monkeypatch.setattr(service, "load_config", lambda: {"email": {}})
    # A test must never open a real SMTP connection.
    monkeypatch.setattr(service.smtplib, "SMTP", MagicMock())
    return service.SchedulerService()
