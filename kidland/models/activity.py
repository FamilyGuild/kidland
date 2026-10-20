"""Minimal structured KidLand purchase activity for parent follow-through."""

from dataclasses import dataclass
from datetime import datetime

import dbzero as db0

from kidland.models.store import FamStorePurchase


@db0.memo(id="/familyguild/kidland/ActivityEvent")
@dataclass
class ActivityEvent:
    """Record a purchase source for later localized parent activity rendering.

    Attributes:
        actor: Purchasing child's Core member UUID from the trusted actor.
        source_reference: Purchase providing structured data and multilingual
            title and price snapshots for later rendering.
        created_at: UTC timestamp when the activity was recorded.
        target_role: Intended audience role; defaults to parent rather than an
            individual recipient.
        event_type: Event rendering key; defaults to famstore_purchase.
        source_type: Referenced domain source kind; defaults to famstore_purchase.
        read: Minimal event-level read flag, initially False. It does not track
            delivery or individual parents' acknowledgements.
    """

    actor: str
    source_reference: FamStorePurchase
    created_at: datetime
    target_role: str = "parent"
    event_type: str = "famstore_purchase"
    source_type: str = "famstore_purchase"
    read: bool = False
