"""Shared fixtures for isolated KidLand state and common test objects."""

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
    """Initialize isolated dbzero state, yield its parent path, and close afterward."""
    db0.init(str(tmp_path / "db0"), prefix="kidland")
    yield tmp_path
    db0.close()


@pytest.fixture
def kidland_package() -> ModuleType:
    """Return the imported KidLand package for package-contract checks."""
    return kidland


@pytest.fixture
def kid_profile() -> KidProfile:
    """Create and return an active child profile in the isolated test state."""
    return create_kid_profile("Alex")
