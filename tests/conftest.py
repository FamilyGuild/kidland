from types import ModuleType

import pytest

import kidland


@pytest.fixture
def kidland_package() -> ModuleType:
    return kidland
