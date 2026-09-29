"""Portable runtime discovery for local integration fixtures."""

from pathlib import Path
import os
import shutil
import subprocess
import sys


def mysql_binary():
    configured = os.environ.get("TAMASYA_MYSQL_BIN")
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return str(path)
        raise RuntimeError(f"TAMASYA_MYSQL_BIN does not point to a file: {path}")
    located = shutil.which("mysql")
    if located:
        return located
    windows = Path(r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe")
    if windows.is_file():
        return str(windows)
    raise RuntimeError("MySQL client not found; install it or set TAMASYA_MYSQL_BIN.")


def mysql_datadir(default):
    return Path(os.environ.get("TAMASYA_MYSQL_DATADIR", default)).expanduser().resolve()


def mysqldump_binary():
    configured = os.environ.get("TAMASYA_MYSQLDUMP_BIN")
    located = configured or shutil.which("mysqldump")
    if located:
        return located
    return str(Path(mysql_binary()).with_name("mysqldump.exe" if os.name == "nt" else "mysqldump"))


def background_process_options():
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {"start_new_session": True}


def python_command():
    return sys.executable
