"""The retired entry point must refuse safely without loading database config."""
import os
from pathlib import Path
import subprocess
import sys


def test_legacy_reset_command_cannot_connect_or_drop_tables(tmp_path):
    script = Path(__file__).resolve().parents[2] / "app/db/init_db.py"
    result = subprocess.run([sys.executable, str(script)], cwd=tmp_path,
        env={**os.environ, "DATABASE_URL": "forbidden-driver://must-not-connect"},
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 2
    assert "No database connection was opened" in result.stderr
    assert "alembic upgrade head" in result.stderr
    assert "Traceback" not in result.stderr
