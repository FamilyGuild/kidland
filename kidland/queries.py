"""Read-only helpers for KidLand state."""

import dbzero as db0

from kidland.models import KidProfile, LedgerEntry


def get_ledger_entries(kid_profile: KidProfile) -> list[LedgerEntry]:
    """Return a child's FamCoins ledger history ordered by creation time."""

    return sorted(
        db0.find(LedgerEntry, db0.as_tag(kid_profile)),
        key=lambda ledger_entry: ledger_entry.created_at,
    )


def calculate_famcoins_balance(kid_profile: KidProfile) -> int:
    """Derive a child's FamCoins balance from auditable ledger entries."""

    return sum(ledger_entry.amount for ledger_entry in get_ledger_entries(kid_profile))
