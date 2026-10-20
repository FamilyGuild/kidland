"""FamCoins ledger models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import dbzero as db0

from kidland.models.profiles import KidProfile
from kidland.models.quests import FamQuestCompletion
from kidland.models.store import FamStorePurchase


@db0.enum(values=["famquest_reward", "famstore_purchase", "manual_adjustment", "famstore_refund"])
class LedgerSourceType:
    """Constrained persisted source types for FamCoins ledger entries."""


@db0.memo(id="/familyguild/kidland/LedgerEntry")
@dataclass
class LedgerEntry:
    """Auditable FamCoins change for one KidLand child profile.

    Attributes:
        kid_profile: Child whose derived balance includes this entry.
        amount: Nonzero signed FamCoins change; positive credits the child,
            negative debits the child. Refunds preserve the original debit.
        reason: Nonblank human-readable explanation of the change.
        source_type: Kind of effect: quest reward, store purchase, manual
            adjustment or store refund.
        created_at: Timestamp of the effect; commands default to current UTC.
        source_reference: Direct reference to the completion or purchase that
            caused the effect; None for adjustments without a concrete source.
    """

    kid_profile: KidProfile
    amount: int
    reason: str
    source_type: LedgerSourceType
    created_at: datetime
    source_reference: FamQuestCompletion | FamStorePurchase | None = None
