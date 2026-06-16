import os
import subprocess
import sys
from pathlib import Path

from haloheads.storage import LocalStorage
from haloheads.store import SqliteStore

REPO = Path(__file__).resolve().parents[1]


def test_analyze_runs_as_script_from_other_cwd(tmp_path, sample_image_bytes):
    bucket = tmp_path / "bucket"
    db = tmp_path / "stats.db"
    LocalStorage(str(bucket)).save_upload(sample_image_bytes, "image/jpeg", {})

    env = {
        **os.environ,
        "STORAGE_BACKEND": "local",
        "STORAGE_DIR": str(bucket),
        "STORE_BACKEND": "sqlite",
        "SQLITE_PATH": str(db),
        "HALOHEADS_FAKE_EXTRACT": "1",
    }
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "analyze.py")],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert len(SqliteStore(str(db)).all_player_stats()) == 8
