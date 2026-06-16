import pytest
from pathlib import Path
from haloheads.storage import LocalStorage


@pytest.fixture
def local_storage(tmp_path):
    return LocalStorage(str(tmp_path / "bucket"))


@pytest.fixture
def sqlite_store(tmp_path):
    from haloheads.store import SqliteStore
    return SqliteStore(str(tmp_path / "stats.db"))


@pytest.fixture
def sample_image_path():
    here = Path(__file__).parent.parent
    return str(here / "gameStatsImageFiles" / "testTeamResultData.jpeg")


@pytest.fixture
def sample_image_bytes(sample_image_path):
    return Path(sample_image_path).read_bytes()
