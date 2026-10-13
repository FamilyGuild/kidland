"""FamQuest domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

import dbzero as db0
from dbzero_modelkit import ML_String

from kidland.models.profiles import KidProfile


@db0.enum(values=[
    "awaiting_acceptance", "awaiting_assignment", "available", "picked",
    "submitted_for_approval", "returned", "rewarded", "cancelled",
])
class FamQuestStatus:
    """Persisted occurrence workflow states."""


@db0.enum(values=["awaiting_response", "accepted", "declined"])
class AssignmentResponse:
    """Child responses to parent offers."""


@db0.enum(values=["pending", "approved", "rejected"])
class CompletionReviewStatus:
    """Parent review decisions."""


@db0.memo(id="/familyguild/kidland/FamQuest")
@dataclass
class FamQuest:
    """One independently dated responsibility and its current attempts."""

    title: ML_String
    description: ML_String
    reward: int
    occurrence_date: date
    created_by: str
    status: FamQuestStatus
    due_date: date | None = None
    eligible_profiles: list[KidProfile] = field(default_factory=list)
    responsible_profile: KidProfile | None = None
    current_offer: FamQuestAssignment | None = None
    current_completion: FamQuestCompletion | None = None

    @property
    def responsibility_source(self) -> Literal["parent_assignment", "child_pickup"] | None:
        """Derive responsibility from the accepted offer instead of duplicate state."""
        if self.responsible_profile is None:
            return None
        if (
            self.current_offer is not None
            and self.current_offer.response_status == AssignmentResponse.accepted
        ):
            return "parent_assignment"
        return "child_pickup"


@db0.memo(id="/familyguild/kidland/FamQuestAssignment")
@dataclass
class FamQuestAssignment:
    """An immutable-in-history offer with one child response."""

    quest: FamQuest
    target_profile: KidProfile
    offered_by: str
    offered_at: datetime
    response_status: AssignmentResponse = AssignmentResponse.awaiting_response
    responded_at: datetime | None = None
    child_comment: str | None = None


@db0.memo(id="/familyguild/kidland/FamQuestCompletion")
@dataclass
class FamQuestCompletion:
    """One submitted attempt; resubmission never overwrites a review."""

    quest: FamQuest
    kid_profile: KidProfile
    submitted_at: datetime
    review_status: CompletionReviewStatus = CompletionReviewStatus.pending
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
