import threading
import uuid
import re as _re
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from models.llm import load_config


class SchedulerService:
    """后台定时提醒服务，在 Streamlit 进程内以守护线程运行"""

    def __init__(self):
        self._scheduler = BackgroundScheduler(daemon=True)
        self._reminders: dict[str, dict] = {}
        self._triggered: list[dict] = []
        self._lock = threading.Lock()

    def start(self):
        self._scheduler.start()

    def shutdown(self):
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    # ---- 供 UI 调用的接口 ----

    def add_reminder(self, task: str, time_desc: str,
                     recipient: str = "", reminder_id: str = "") -> tuple:
        """添加一个定时提醒，返回 (reminder_id, error)"""
        rid = reminder_id or str(uuid.uuid4())[:8]

        scheduled_dt = self._parse_time(time_desc)
        if scheduled_dt is None:
            return None, "无法解析时间描述，请用更具体的方式描述时间"

        info = {
            "id": rid,
            "task": task,
            "time": time_desc,
            "scheduled_dt": scheduled_dt,
            "recipient": recipient,
        }

        with self._lock:
            self._reminders[rid] = info

        self._scheduler.add_job(
            func=self._fire_reminder,
            trigger=DateTrigger(run_date=scheduled_dt),
            args=[rid],
            id=f"reminder_{rid}",
        )

        return rid, None

    def get_reminders(self) -> list[dict]:
        with self._lock:
            return [
                {"id": r["id"], "task": r["task"], "time": r["time"],
                 "recipient": r.get("recipient", "")}
                for r in self._reminders.values()
            ]

    def remove_reminder(self, rid: str):
        with self._lock:
            self._reminders.pop(rid, None)
        try:
            self._scheduler.remove_job(f"reminder_{rid}")
        except Exception:
            pass

    def pop_triggered(self) -> list[dict]:
        """取出并清空最近触发的提醒列表（供 UI 展示）"""
        with self._lock:
            result = list(self._triggered)
            self._triggered.clear()
        return result

    # ---- 内部方法 ----

    def _fire_reminder(self, rid: str):
        with self._lock:
            info = self._reminders.get(rid)
            if info is None:
                return
            self._reminders.pop(rid, None)
            self._triggered.append({
                "id": rid,
                "task": info["task"],
                "time": info["time"],
            })

        config = load_config()
        email_cfg = config.get("email", {})
        recipient = info.get("recipient") or email_cfg.get("default_recipient", "")

        if recipient and email_cfg.get("username") and email_cfg.get("password"):
            try:
                msg = MIMEText(f"⏰ 提醒：{info['task']}", "plain", "utf-8")
                msg["Subject"] = f"⏰ 提醒：{info['task']}"
                msg["From"] = email_cfg["username"]
                msg["To"] = recipient

                port = email_cfg.get("smtp_port", 587)
                with smtplib.SMTP(email_cfg["smtp_server"], port) as server:
                    server.starttls()
                    server.login(email_cfg["username"], email_cfg["password"])
                    server.sendmail(email_cfg["username"], [recipient], msg.as_string())
            except Exception:
                pass

    @staticmethod
    def _parse_time(desc: str) -> Optional[datetime]:
        """尝试解析自然语言时间描述，返回 datetime 或 None"""
        now = datetime.now()
        desc = desc.strip()

        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S",
                    "%H:%M", "%H:%M:%S"):
            try:
                dt = datetime.strptime(desc, fmt)
                if fmt in ("%H:%M", "%H:%M:%S"):
                    dt = dt.replace(year=now.year, month=now.month, day=now.day)
                    if dt < now:
                        dt += timedelta(days=1)
                return dt
            except ValueError:
                continue

        base = now
        if "明天" in desc:
            base = now + timedelta(days=1)
        elif "后天" in desc:
            base = now + timedelta(days=2)

        hm = _re.search(r'(\d{1,2})[点时:：](\d{2})?(?:分)?', desc)
        if hm:
            hour, minute = int(hm.group(1)), int(hm.group(2) or 0)
            dt = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if dt < now:
                dt += timedelta(days=1)
            return dt

        return None


# 模块级单例
_instance: Optional[SchedulerService] = None


def get_scheduler() -> SchedulerService:
    global _instance
    if _instance is None:
        _instance = SchedulerService()
        _instance.start()
    return _instance
