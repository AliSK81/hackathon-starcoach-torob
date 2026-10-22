from pathlib import Path

import pytest

from starcoach.build import build

MINI = Path(__file__).resolve().parent / "fixtures" / "mini"


@pytest.fixture(scope="session")
def mini_db(tmp_path_factory) -> Path:
    """A DB built from the real-sample mini dataset (offline)."""
    out = tmp_path_factory.mktemp("db")
    db = out / "mini.db"
    build(MINI, db, out / "logs")
    return db
