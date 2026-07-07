from types import ModuleType


def test_package_is_importable(kidland_package: ModuleType) -> None:
    assert kidland_package.PACKAGE_NAME == "kidland"
    assert kidland_package.MODULE_KEY == "kidland"
