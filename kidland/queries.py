"""Read-only helpers for KidLand state."""

import dbzero as db0

from kidland.models import KidProfile, LedgerEntry


def resolve_kid_profile(member_uuid: str) -> KidProfile:
    """Resolve exactly one active profile linked to a trusted Core member."""
    profiles = [profile for profile in db0.find(
        KidProfile, f"kidland.member:{member_uuid}"
    ) if profile.active and profile.linked_member_uuid == member_uuid]
    if len(profiles) != 1:
        raise ValueError("member must map to exactly one active KidProfile")
    return profiles[0]


def get_ledger_entries(kid_profile: KidProfile) -> list[LedgerEntry]:
    """Return a child's FamCoins ledger history ordered by creation time."""

    return sorted(
        db0.find(LedgerEntry, db0.as_tag(kid_profile)),
        key=lambda ledger_entry: ledger_entry.created_at,
    )


def calculate_famcoins_balance(kid_profile: KidProfile) -> int:
    """Derive a child's FamCoins balance from auditable ledger entries."""

    return sum(ledger_entry.amount for ledger_entry in get_ledger_entries(kid_profile))
