"""Explicit commands that mutate KidLand state."""

from __future__ import annotations

from datetime import UTC, datetime

import dbzero as db0

from kidland.models import KidProfile, LedgerEntry, LedgerSourceType


def create_kid_profile(
    display_name: str,
    active: bool = True,
) -> KidProfile:
    """Create a KidLand child profile owned by the module.

    Args:
        display_name: Child-facing profile name or nickname.
        active: Whether the profile can receive ledger entries.

    Returns:
        The created `KidProfile`.
    """

    return KidProfile(
        display_name=display_name,
        active=active,
    )


def record_ledger_entry(
    kid_profile: KidProfile,
    amount: int,
    reason: str,
    source_type: LedgerSourceType,
    created_at: datetime | None = None,
) -> LedgerEntry:
    """Record an auditable FamCoins change for a KidLand child profile.

    Args:
        kid_profile: Active KidLand profile whose balance is affected.
        amount: Positive earning amount or negative spending amount.
        reason: Human-readable reason for the ledger entry.
        source_type: Constrained source type for the balance change.
        created_at: Optional timestamp for deterministic callers or tests.

    Returns:
        The created `LedgerEntry`.

    Raises:
        ValueError: If the profile is inactive, amount is zero, or reason is blank.
    """

    if not kid_profile.active:
        raise ValueError("kid_profile must be active")
    if amount == 0:
        raise ValueError("amount must not be zero")
    if not reason.strip():
        raise ValueError("reason is required")

    ledger_entry = LedgerEntry(
        kid_profile=kid_profile,
        amount=amount,
        reason=reason,
        source_type=source_type,
        created_at=created_at or datetime.now(UTC),
    )
    db0.tags(ledger_entry).add(db0.as_tag(kid_profile), "kidland.ledger.entry")

    return ledger_entry


def adjust_famcoins_balance(
    kid_profile: KidProfile,
    amount: int,
    reason: str,
    adjusted_at: datetime | None = None,
) -> LedgerEntry:
    """Record a parent manual FamCoins adjustment.

    Manual positive and negative adjustments are auditable ledger entries.
    """

    return record_ledger_entry(
        kid_profile=kid_profile,
        amount=amount,
        reason=reason,
        source_type=LedgerSourceType.manual_adjustment,
        created_at=adjusted_at,
    )
