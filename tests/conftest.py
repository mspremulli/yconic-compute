import pytest
import pytest_asyncio
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d)


@pytest.fixture
def mock_db_path(temp_dir):
    return str(temp_dir / "test_swarm.db")


@pytest.fixture
def mock_chroma_path(temp_dir):
    return str(temp_dir / "test_chroma_db")
