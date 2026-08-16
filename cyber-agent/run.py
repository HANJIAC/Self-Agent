#!/usr/bin/env python3
"""Cyber Agent 启动入口 - 使用 conda rag 环境"""
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    app_path = Path(__file__).parent / "app.py"
    cmd = ["conda", "run", "-n", "rag", "streamlit", "run", str(app_path)]
    subprocess.run(cmd)
