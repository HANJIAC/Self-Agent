from email import message_from_string
from email.header import decode_header, make_header
from unittest.mock import MagicMock, call

import pytest

from agent import tools


@pytest.fixture
def email_setup(monkeypatch):
    config = {"email": {
        "smtp_server": "smtp.example.com", "smtp_port": 587,
        "username": "sender@example.com", "password": "fake-password",
        "default_recipient": "default@example.com",
    }}
    smtp = MagicMock()
    monkeypatch.setattr(tools, "load_config", lambda: config)
    monkeypatch.setattr(tools.smtplib, "SMTP", smtp)
    return config, smtp


@pytest.mark.parametrize("recipient, expected", [
    ("", "default@example.com"), ("explicit@example.com", "explicit@example.com"),
])
def test_send_email(email_setup, recipient, expected):
    _, smtp = email_setup
    result = tools.send_email.invoke({"subject": "测试", "body": "邮件内容", "recipient": recipient})
    assert expected in result and "成功" in result
    smtp.assert_called_once_with("smtp.example.com", 587)
    connection = smtp.return_value.__enter__.return_value
    connection.starttls.assert_called_once()
    connection.login.assert_called_once_with("sender@example.com", "fake-password")
    connection.sendmail.assert_called_once()
    assert [entry[0] for entry in connection.method_calls] == ["starttls", "login", "sendmail"]
    sender, recipients, raw = connection.sendmail.call_args.args
    assert sender == "sender@example.com" and recipients == [expected]
    message = message_from_string(raw)
    assert message["To"] == expected
    assert message["From"] == "sender@example.com"
    assert str(make_header(decode_header(message["Subject"]))) == "测试"
    assert message.get_content_type() == "text/plain"
    assert message.get_content_charset() == "utf-8"
    assert message.get_payload(decode=True).decode("utf-8") == "邮件内容"
    smtp.return_value.__exit__.assert_called_once_with(None, None, None)


@pytest.mark.parametrize("key", ["smtp_server", "username", "password", "default_recipient"])
def test_missing_config(email_setup, key):
    config, smtp = email_setup
    config["email"][key] = ""
    assert "配置不完整" in tools.send_email.invoke({"subject": "test", "body": "body"})
    smtp.assert_not_called()


def test_send_failure(email_setup):
    _, smtp = email_setup
    smtp.return_value.__enter__.return_value.sendmail.side_effect = RuntimeError("SMTP failed")
    result = tools.send_email.invoke({"subject": "test", "body": "body"})
    assert result == "邮件发送失败: SMTP failed"
    smtp.return_value.__enter__.return_value.sendmail.assert_called_once()
    assert smtp.return_value.__exit__.call_count == 1


def test_login_failure_does_not_send(email_setup):
    _, smtp = email_setup
    connection = smtp.return_value.__enter__.return_value
    connection.login.side_effect = RuntimeError("authentication failed")
    result = tools.send_email.invoke({"subject": "test", "body": "body"})
    assert result == "邮件发送失败: authentication failed"
    assert connection.method_calls == [
        call.starttls(), call.login("sender@example.com", "fake-password"),
    ]
    connection.sendmail.assert_not_called()
    smtp.return_value.__exit__.assert_called_once()
