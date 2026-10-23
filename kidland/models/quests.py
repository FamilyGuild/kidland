"""FamQuest domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

import dbzero as db0
from dbzero_modelkit import Calendar, LanguageCode, ML_String

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


@db0.enum(values=["daily", "weekly", "monthly"], type_id="/familyguild/kidland/RecurrenceCadence")
class RecurrenceCadence:
    """Supported calendar-anchored recurrence schedules."""


@db0.memo(id="/familyguild/kidland/FamQuestRecurrence")
@dataclass
class FamQuestRecurrence:
    """A parent-owned template and sparse calendar of independent occurrences.

    Attributes:
        title: Nonblank multilingual template title, copied into occurrences.
        description: Multilingual details; primary text may be empty.
        reward: Positive integer FamCoins reward copied into each occurrence.
        cadence: Daily, weekly from start weekday, or monthly from start day;
            shorter months clamp the day without changing the original anchor.
        start_date: Inclusive first due date and anchor for the schedule.
        end_date: Inclusive final permitted date, or None for an unbounded rule.
        created_by: UUID of the trusted parent who created the rule.
        calendar: Owned date-to-FamQuest storage in the rule's state prefix,
            with its base year set to the start year.
        primary_language: Primary language of both template strings, explicitly
            retained because modelkit does not expose their primary-language code.
        target_profile: Child receiving parent offers; None for published rules.
        eligible_profiles: Children allowed to pick published occurrences;
            empty when target_profile selects parent-offered delivery.
        active: Whether new occurrences may be created; initially True.
            Deactivation never changes previously generated occurrences.
    """

    title: ML_String
    description: ML_String
    reward: int
    cadence: RecurrenceCadence
    start_date: date
    end_date: date | None
    created_by: str
    calendar: Calendar
    primary_language: LanguageCode
    target_profile: KidProfile | None = None
    eligible_profiles: list[KidProfile] = field(default_factory=list)
    active: bool = True


@db0.memo(id="/familyguild/kidland/FamQuest")
@dataclass
class FamQuest:
    """One independently dated responsibility and its current attempts.

    Attributes:
        title: Nonblank multilingual occurrence title.
        description: Multilingual task details; primary text may be empty.
        reward: Positive FamCoins amount awarded on completion approval.
        occurrence_date: Calendar date identifying this occurrence.
        created_by: Creating parent's Core member UUID.
        status: Current occurrence workflow state, maintained with its state tag.
        due_date: Optional completion deadline; None means no explicit deadline.
        eligible_profiles: Children allowed to pick a published occurrence;
            initially empty for a directly offered occurrence.
        responsible_profile: Child responsible after acceptance or pickup;
            None until responsibility is established.
        current_offer: Latest parent assignment offer, or None for an occurrence
            without an offer. Earlier offers remain separate history objects.
        current_completion: Latest submitted attempt, or None before submission.
            Resubmission creates a new attempt rather than overwriting review.
        responsibility_source: Derived property: parent_assignment for an
            accepted offer, child_pickup otherwise, or None without a child.
        recurrence: Generating rule, or None for a standalone one-time quest.
    """

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
    recurrence: FamQuestRecurrence | None = None

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
    """A retained historical offer with one child response.

    Attributes:
        quest: Occurrence being offered; its current_offer identifies whether
            this offer is still current.
        target_profile: Child allowed to accept or decline this offer.
        offered_by: Offering parent's Core member UUID.
        offered_at: UTC timestamp when the offer was created.
        response_status: Initially awaiting_response, then accepted or declined.
        responded_at: UTC response timestamp, or None while awaiting response.
        child_comment: Optional explanation supplied on decline; otherwise None.
    """

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
    """One submitted attempt; resubmission never overwrites a review.

    Attributes:
        quest: Occurrence whose work was submitted.
        kid_profile: Responsible child who submitted this attempt.
        submitted_at: UTC timestamp when the attempt was submitted.
        review_status: Initially pending, then approved or rejected by a parent.
        reviewed_by: Reviewing parent's Core member UUID, or None before review.
        reviewed_at: UTC review timestamp, or None before review.
        review_note: Parent explanation; required and nonblank on rejection,
            optional on approval, and initially None.
    """

    quest: FamQuest
    kid_profile: KidProfile
    submitted_at: datetime
    review_status: CompletionReviewStatus = CompletionReviewStatus.pending
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
