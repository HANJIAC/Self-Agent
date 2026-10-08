from datetime import datetime
from email import message_from_string
from email.header import decode_header, make_header
from unittest.mock import MagicMock

from scheduler import service


def test_add_reminder(scheduler):
    rid, error = scheduler.add_reminder("开会", "明天10点", "to@example.com", "fixed-id")
    assert (rid, error) == ("fixed-id", None)
    assert scheduler.get_reminders() == [{
        "id": "fixed-id", "task": "开会", "time": "明天10点", "recipient": "to@example.com",
    }]
    job = scheduler._scheduler.add_job.call_args.kwargs
    scheduler._scheduler.add_job.assert_called_once()
    scheduler._scheduler.start.assert_not_called()
    assert job["func"] == scheduler._fire_reminder
    assert job["id"] == "reminder_fixed-id"
    assert job["args"] == ["fixed-id"]
    assert job["trigger"].run_date.replace(tzinfo=None) == datetime(2026, 10, 9, 10)
    assert scheduler.pop_triggered() == []


def test_invalid_time_does_not_create_job(scheduler):
    rid, error = scheduler.add_reminder("开会", "某个时间")
    assert rid is None and error
    assert scheduler.get_reminders() == []
    scheduler._scheduler.add_job.assert_not_called()
    assert scheduler.pop_triggered() == []


def test_remove(scheduler):
    scheduler.add_reminder("开会", "明天10点", reminder_id="r1")
    scheduler.remove_reminder("r1")
    assert scheduler.get_reminders() == []
    scheduler._scheduler.remove_job.assert_called_once_with("reminder_r1")
    scheduler._fire_reminder("r1")
    assert scheduler.pop_triggered() == []


def test_remove_missing_job_is_safe(scheduler):
    scheduler._scheduler.remove_job.side_effect = LookupError("missing")
    scheduler.remove_reminder("missing")
    assert scheduler.get_reminders() == []


def test_fire_once_and_drain_notifications(scheduler):
    scheduler.add_reminder("开会", "明天10点", reminder_id="r1")
    scheduler._fire_reminder("r1")
    scheduler._fire_reminder("r1")
    assert scheduler.get_reminders() == []
    assert scheduler.pop_triggered() == [{"id": "r1", "task": "开会", "time": "明天10点"}]
    assert scheduler.pop_triggered() == []
    service.smtplib.SMTP.assert_not_called()


def test_returned_reminders_do_not_mutate_storage(scheduler):
    scheduler.add_reminder("开会", "明天10点", reminder_id="r1")
    scheduler.get_reminders()[0]["task"] = "changed"
    assert scheduler.get_reminders()[0]["task"] == "开会"


def test_fire_sends_to_default_recipient(scheduler, monkeypatch):
    monkeypatch.setattr(service, "load_config", lambda: {"email": {
        "smtp_server": "smtp.example.com", "username": "from@example.com",
        "password": "fake", "default_recipient": "default@example.com",
    }})
    smtp = MagicMock()
    monkeypatch.setattr(service.smtplib, "SMTP", smtp)
    scheduler.add_reminder("开会", "明天10点", reminder_id="r1")
    scheduler._fire_reminder("r1")
    connection = smtp.return_value.__enter__.return_value
    smtp.assert_called_once_with("smtp.example.com", 587)
    connection.starttls.assert_called_once_with()
    connection.login.assert_called_once_with("from@example.com", "fake")
    connection.sendmail.assert_called_once()
    assert connection.sendmail.call_args.args[:2] == ("from@example.com", ["default@example.com"])
    message = message_from_string(connection.sendmail.call_args.args[2])
    assert message["From"] == "from@example.com"
    assert message["To"] == "default@example.com"
    assert str(make_header(decode_header(message["Subject"]))) == "⏰ 提醒：开会"
    assert message.get_payload(decode=True).decode("utf-8") == "⏰ 提醒：开会"
    assert scheduler.get_reminders() == []
    assert scheduler.pop_triggered() == [{"id": "r1", "task": "开会", "time": "明天10点"}]
    smtp.return_value.__exit__.assert_called_once_with(None, None, None)


def test_fire_email_failure_keeps_notification(scheduler, monkeypatch):
    monkeypatch.setattr(service, "load_config", lambda: {"email": {
        "smtp_server": "smtp.example.com", "username": "from@example.com",
        "password": "fake", "default_recipient": "default@example.com",
    }})
    smtp = MagicMock(side_effect=RuntimeError("offline"))
    monkeypatch.setattr(service.smtplib, "SMTP", smtp)
    scheduler.add_reminder("开会", "明天10点", reminder_id="r1")
    scheduler._fire_reminder("r1")
    smtp.assert_called_once()
    assert scheduler.get_reminders() == []
    assert scheduler.pop_triggered() == [{"id": "r1", "task": "开会", "time": "明天10点"}]
    assert scheduler.pop_triggered() == []


def test_removing_one_reminder_preserves_another(scheduler):
    scheduler.add_reminder("取消的提醒", "明天10点", reminder_id="r1")
    scheduler.add_reminder("保留的提醒", "后天11点", reminder_id="r2")
    scheduler.remove_reminder("r1")
    assert scheduler.get_reminders() == [{
        "id": "r2", "task": "保留的提醒", "time": "后天11点", "recipient": "",
    }]
    scheduler._scheduler.remove_job.assert_called_once_with("reminder_r1")
    scheduler._fire_reminder("r2")
    assert scheduler.pop_triggered() == [{"id": "r2", "task": "保留的提醒", "time": "后天11点"}]
    assert scheduler.get_reminders() == []
