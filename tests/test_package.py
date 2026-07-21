from types import ModuleType

from kidland.models import KidProfile, LedgerEntry, LedgerSourceType


def test_package_is_importable(kidland_package: ModuleType) -> None:
    assert kidland_package.PACKAGE_NAME == "kidland"
    assert kidland_package.MODULE_KEY == "kidland"


def test_documented_model_package_exports_kidland_models() -> None:
    assert KidProfile.__module__ == "kidland.models.profiles"
    assert LedgerEntry.__module__ == "kidland.models.ledger"


def test_ledger_source_type_is_constrained_dbzero_enum() -> None:
    assert str(LedgerSourceType.famquest_reward) == "famquest_reward"
    assert str(LedgerSourceType.famstore_purchase) == "famstore_purchase"
    assert str(LedgerSourceType.manual_adjustment) == "manual_adjustment"
    assert LedgerSourceType["manual_adjustment"] == LedgerSourceType.manual_adjustment
