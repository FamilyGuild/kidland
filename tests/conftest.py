from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import dbzero as db0
import pytest

import kidland
from kidland.commands import create_kid_profile
from kidland.models import KidProfile


@pytest.fixture(autouse=True)
def dbzero_state(tmp_path: Path) -> Iterator[Path]:
    db0.init(str(tmp_path / "db0"), prefix="kidland")
    yield tmp_path
    db0.close()


@pytest.fixture
def kidland_package() -> ModuleType:
    return kidland


@pytest.fixture
def kid_profile() -> KidProfile:
    return create_kid_profile("Alex")
