import pytest

from rag.config import settings


@pytest.fixture(autouse=True)
def _ensure_dirs(tmp_path):
    settings.data_dir = tmp_path
    (tmp_path / "pdfs").mkdir()
    (tmp_path / "rag" / "sources").mkdir(parents=True)
