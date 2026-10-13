"""Verify FamCoins ledger recording, derived balances, and adjustment validation."""

from datetime import UTC, datetime

import pytest

from kidland.commands import (
    adjust_famcoins_balance,
    create_kid_profile,
    record_ledger_entry,
)
from kidland.models import KidProfile, LedgerEntry, LedgerSourceType
from kidland.queries import calculate_famcoins_balance, get_ledger_entries


def test_create_kid_profile_starts_without_stored_balance() -> None:
    """Verify new profiles have a zero derived balance without stored balance fields."""
    kid_profile = create_kid_profile("Alex")

    assert isinstance(kid_profile, KidProfile)
    assert kid_profile.display_name == "Alex"
    assert kid_profile.active is True
    assert not hasattr(kid_profile, "balance")
    assert not hasattr(kid_profile, "famcoins_balance")
    assert calculate_famcoins_balance(kid_profile) == 0


def test_record_positive_and_negative_ledger_entries(kid_profile: KidProfile) -> None:
    """Verify earnings and spending retain metadata and contribute to the balance."""
    earned_at = datetime(2026, 7, 7, 9, 0, tzinfo=UTC)
    spent_at = datetime(2026, 7, 7, 10, 0, tzinfo=UTC)

    earning = record_ledger_entry(
        kid_profile,
        amount=25,
        reason="Completed reading quest",
        source_type=LedgerSourceType.famquest_reward,
        created_at=earned_at,
    )
    spending = record_ledger_entry(
        kid_profile,
        amount=-10,
        reason="Bought YouTube time",
        source_type=LedgerSourceType.famstore_purchase,
        created_at=spent_at,
    )

    assert isinstance(earning, LedgerEntry)
    assert earning.kid_profile is kid_profile
    assert earning.amount == 25
    assert earning.reason == "Completed reading quest"
    assert str(earning.source_type) == "famquest_reward"
    assert earning.created_at == earned_at
    assert spending.amount == -10
    assert str(spending.source_type) == "famstore_purchase"
    assert get_ledger_entries(kid_profile) == [earning, spending]
    assert calculate_famcoins_balance(kid_profile) == 15


def test_balance_is_derived_per_kid_profile(kid_profile: KidProfile) -> None:
    """Verify each profile's balance includes only its own ledger entries."""
    other_profile = create_kid_profile("Riley")

    record_ledger_entry(
        kid_profile,
        20,
        "Quest",
        LedgerSourceType.famquest_reward,
    )
    record_ledger_entry(
        other_profile,
        100,
        "Quest",
        LedgerSourceType.famquest_reward,
    )
    record_ledger_entry(
        kid_profile,
        -5,
        "Purchase",
        LedgerSourceType.famstore_purchase,
    )

    assert calculate_famcoins_balance(kid_profile) == 15
    assert calculate_famcoins_balance(other_profile) == 100


def test_manual_adjustments_require_reason_and_create_ledger_entries(
    kid_profile: KidProfile,
) -> None:
    """Verify signed manual adjustments are recorded and blank reasons rejected."""
    positive_adjustment = adjust_famcoins_balance(
        kid_profile,
        amount=12,
        reason="Missed reward correction",
    )
    negative_adjustment = adjust_famcoins_balance(
        kid_profile,
        amount=-3,
        reason="Household rule correction",
    )

    assert str(positive_adjustment.source_type) == "manual_adjustment"
    assert str(negative_adjustment.source_type) == "manual_adjustment"
    assert calculate_famcoins_balance(kid_profile) == 9

    with pytest.raises(ValueError, match="reason"):
        adjust_famcoins_balance(
            kid_profile,
            amount=1,
            reason=" ",
        )

    assert calculate_famcoins_balance(kid_profile) == 9


def test_ledger_entries_reject_invalid_balance_changes(kid_profile: KidProfile) -> None:
    """Verify zero amounts and blank reasons leave the ledger unchanged."""
    with pytest.raises(ValueError, match="amount"):
        record_ledger_entry(
            kid_profile,
            0,
            "No change",
            LedgerSourceType.famquest_reward,
        )

    with pytest.raises(ValueError, match="reason"):
        record_ledger_entry(
            kid_profile,
            5,
            " ",
            LedgerSourceType.famquest_reward,
        )

    assert get_ledger_entries(kid_profile) == []


def test_inactive_kid_profile_cannot_receive_ledger_entries(kid_profile: KidProfile) -> None:
    """Verify inactive profiles cannot receive entries or change their balance."""
    kid_profile.active = False

    with pytest.raises(ValueError, match="active"):
        record_ledger_entry(
            kid_profile,
            5,
            "Quest",
            LedgerSourceType.famquest_reward,
        )

    assert calculate_famcoins_balance(kid_profile) == 0
