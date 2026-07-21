"""FamCoins ledger models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import dbzero as db0

from kidland.models.profiles import KidProfile


@db0.enum(values=["famquest_reward", "famstore_purchase", "manual_adjustment"])
class LedgerSourceType:
    """Constrained persisted source types for FamCoins ledger entries."""


@db0.memo(id="/familyguild/kidland/LedgerEntry")
@dataclass
class LedgerEntry:
    """Auditable FamCoins change for one KidLand child profile."""

    kid_profile: KidProfile
    amount: int
    reason: str
    source_type: LedgerSourceType
    created_at: datetime
