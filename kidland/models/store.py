"""FamStore domain models."""

from dataclasses import dataclass

import dbzero as db0
from dbzero_modelkit import ML_String


@db0.memo(id="/familyguild/kidland/FamStoreItem")
@dataclass
class FamStoreItem:
    """Persisted multilingual text foundation for a FamStore item."""

    title: ML_String
    description: ML_String
    fulfillment_note: ML_String


@db0.memo(id="/familyguild/kidland/FamStorePurchase")
@dataclass
class FamStorePurchase:
    """Persisted multilingual title snapshot for a future purchase workflow."""

    title_snapshot: ML_String
