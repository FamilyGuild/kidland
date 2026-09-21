"""FamQuest domain models."""

from dataclasses import dataclass

import dbzero as db0
from dbzero_modelkit import ML_String


@db0.memo(id="/familyguild/kidland/FamQuest")
@dataclass
class FamQuest:
    """Persisted multilingual text foundation for a FamQuest occurrence."""

    title: ML_String
    description: ML_String
