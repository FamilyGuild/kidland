"""FamStore domain models."""

from dataclasses import dataclass, field
from datetime import datetime

import dbzero as db0
from dbzero_modelkit import LanguageCode, ML_String

from kidland.models.profiles import KidProfile


@db0.enum(values=["purchased", "fulfilled", "cancelled"])
class PurchaseStatus:
    """Persisted purchase settlement states."""


@db0.memo(id="/familyguild/kidland/FamStoreItem")
@dataclass
class FamStoreItem:
    """Parent-managed multilingual offer with a separate limit for each child.

    Attributes:
        title: Nonblank multilingual offer title.
        description: Multilingual offer details; primary text may be empty.
        fulfillment_note: Multilingual instructions for parent fulfillment;
            primary text may be empty.
        cost: Positive integer FamCoins price for future purchases.
        item_type: Nonblank descriptive type key, not an automation rule.
        title_primary_language: Language identifying the title's primary value,
            used when creating independent purchase snapshots.
        purchase_limit_per_child: Total purchases allowed per child; None means
            unlimited, 1 means one-time. Purchased and fulfilled purchases count;
            cancelled purchases do not. Editing or repinning never resets usage.
        enabled: Parent-controlled availability, initially True. Buying also
            requires a child pin, remaining capacity and sufficient funds.
        pinned_profiles: Children whose stores include this offer, initially
            empty. Exhausted offers are hidden only for the affected child.
    """

    title: ML_String
    description: ML_String
    fulfillment_note: ML_String
    cost: int
    item_type: str
    title_primary_language: LanguageCode
    purchase_limit_per_child: int | None = None
    enabled: bool = True
    pinned_profiles: list[KidProfile] = field(default_factory=list)


@db0.memo(id="/familyguild/kidland/FamStorePurchase")
@dataclass
class FamStorePurchase:
    """Auditable purchase with independent title and price snapshots.

    Attributes:
        title_snapshot: Independent multilingual title captured at purchase;
            later offer edits do not change it.
        kid_profile: Child who bought the offer, resolved from the trusted actor.
        item: Direct reference to the original parent-managed offer.
        cost_snapshot: Original FamCoins price, used for the debit and any full
            cancellation refund regardless of subsequent price changes.
        purchased_at: UTC timestamp of purchase creation.
        status: Initially purchased; parent settlement changes it to fulfilled
            or cancelled. Both settlement states are terminal.
        parent_informed_at: Timestamp when parent activity was recorded, not
            delivered or read; None until recorded.
        fulfilled_by: Fulfilling parent's Core member UUID, or None before
            fulfillment.
        fulfilled_at: UTC fulfillment timestamp, or None before fulfillment.
        cancelled_by: Cancelling parent's Core member UUID, or None before
            cancellation.
        cancelled_at: UTC cancellation timestamp, or None before cancellation.
    """

    title_snapshot: ML_String
    kid_profile: KidProfile
    item: FamStoreItem
    cost_snapshot: int
    purchased_at: datetime
    status: PurchaseStatus = PurchaseStatus.purchased
    parent_informed_at: datetime | None = None
    fulfilled_by: str | None = None
    fulfilled_at: datetime | None = None
    cancelled_by: str | None = None
    cancelled_at: datetime | None = None
