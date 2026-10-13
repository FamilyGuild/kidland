"""Explicit commands that mutate KidLand state."""

from __future__ import annotations

from datetime import UTC, date, datetime

import dbzero as db0
from dbzero_modelkit import ML_String

from kidland.actors import TrustedActorContext, require_parent
from kidland.models import (
    AssignmentResponse,
    CompletionReviewStatus,
    FamQuest,
    FamQuestAssignment,
    FamQuestCompletion,
    FamQuestStatus,
    KidProfile,
    LedgerEntry,
    LedgerSourceType,
)
from kidland.queries import resolve_kid_profile


def create_kid_profile(
    display_name: str,
    active: bool = True,
    linked_member_uuid: str | None = None,
) -> KidProfile:
    """Create a KidLand child profile owned by the module.

    Args:
        display_name: Child-facing profile name or nickname.
        active: Whether the profile can receive ledger entries.

    Returns:
        The created `KidProfile`.
    """

    profile = KidProfile(
        display_name=display_name,
        active=active,
        linked_member_uuid=linked_member_uuid,
    )
    if linked_member_uuid is not None:
        db0.tags(profile).add(f"kidland.member:{linked_member_uuid}")
    return profile


def record_ledger_entry(
    kid_profile: KidProfile,
    amount: int,
    reason: str,
    source_type: LedgerSourceType,
    created_at: datetime | None = None,
    source_reference: FamQuestCompletion | None = None,
) -> LedgerEntry:
    """Record an auditable FamCoins change for a KidLand child profile.

    Args:
        kid_profile: Active KidLand profile whose balance is affected.
        amount: Positive earning amount or negative spending amount.
        reason: Human-readable reason for the ledger entry.
        source_type: Constrained source type for the balance change.
        created_at: Optional timestamp for deterministic callers or tests.

    Returns:
        The created `LedgerEntry`.

    Raises:
        ValueError: If the profile is inactive, amount is zero, or reason is blank.
    """

    if not kid_profile.active:
        raise ValueError("kid_profile must be active")
    if amount == 0:
        raise ValueError("amount must not be zero")
    if not reason.strip():
        raise ValueError("reason is required")

    ledger_entry = LedgerEntry(
        kid_profile=kid_profile,
        amount=amount,
        reason=reason,
        source_type=source_type,
        created_at=created_at or datetime.now(UTC),
        source_reference=source_reference,
    )
    db0.tags(ledger_entry).add(db0.as_tag(kid_profile), "kidland.ledger.entry")
    if source_reference is not None:
        db0.tags(ledger_entry).add(db0.as_tag(source_reference))

    return ledger_entry


def adjust_famcoins_balance(
    kid_profile: KidProfile,
    amount: int,
    reason: str,
    adjusted_at: datetime | None = None,
) -> LedgerEntry:
    """Record a parent manual FamCoins adjustment.

    Manual positive and negative adjustments are auditable ledger entries.
    """

    return record_ledger_entry(
        kid_profile=kid_profile,
        amount=amount,
        reason=reason,
        source_type=LedgerSourceType.manual_adjustment,
        created_at=adjusted_at,
    )


def _child_profile(actor: TrustedActorContext) -> KidProfile:
    """Return the trusted child's uniquely linked active profile.

    Raise ValueError for a non-child actor or a missing or ambiguous active
    profile mapping.
    """
    if actor.role != "child":
        raise ValueError("actor must be a child")
    return resolve_kid_profile(actor.member_uuid)


def _set_quest_status(quest: FamQuest, status: FamQuestStatus) -> None:
    """Replace the workflow tag together with the persisted state."""
    db0.tags(quest).remove(f"kidland.quest.{quest.status}")
    quest.status = status
    db0.tags(quest).add(f"kidland.quest.{status}")


def create_famquest(
    actor: TrustedActorContext,
    title: ML_String,
    description: ML_String,
    reward: int,
    occurrence_date: date,
    *,
    due_date: date | None = None,
    target_profile: KidProfile | None = None,
    eligible_profiles: list[KidProfile] | None = None,
) -> FamQuest:
    """Create a one-time parent offer or a directly pickable published quest."""
    require_parent(actor)
    if not title.value.strip() or reward <= 0:
        raise ValueError("title and positive reward are required")
    if target_profile is not None and eligible_profiles:
        raise ValueError("choose either a target or eligible profiles")
    if target_profile is None and not eligible_profiles:
        raise ValueError("published quests require eligible profiles")
    with db0.atomic():
        profiles = (
            [target_profile] if target_profile is not None else list(eligible_profiles or [])
        )
        if any(not profile.active for profile in profiles):
            raise ValueError("quest profiles must be active")
        status = (
            FamQuestStatus.awaiting_assignment
            if target_profile is not None else FamQuestStatus.available
        )
        quest = FamQuest(
            title, description, reward, occurrence_date, actor.member_uuid,
            status, due_date, list(eligible_profiles or []),
        )
        db0.tags(quest).add(f"kidland.quest.{status}")
        for profile in eligible_profiles or []:
            db0.tags(quest).add(db0.as_tag(profile))
        if target_profile is not None:
            _offer_famquest(actor, quest, target_profile)
        return quest


def _offer_famquest(
    actor: TrustedActorContext, quest: FamQuest, target_profile: KidProfile,
) -> FamQuestAssignment:
    """Create and return an offer for an active target within the caller's atomic block.

    Record the actor as issuer, preserve previous offers, and move the quest to
    awaiting acceptance. Raise ValueError if the quest cannot receive an offer
    or the target profile is inactive.
    """
    if (quest.status != FamQuestStatus.awaiting_assignment
            or quest.responsible_profile is not None
            or (quest.current_offer is not None and quest.current_offer.response_status
                == AssignmentResponse.awaiting_response)):
        raise ValueError("quest cannot receive a new offer")
    if not target_profile.active:
        raise ValueError("target profile must be active")
    assignment = FamQuestAssignment(
        quest, target_profile, actor.member_uuid, datetime.now(UTC),
    )
    db0.tags(assignment).add(
        db0.as_tag(quest), db0.as_tag(target_profile), "kidland.assignment.awaiting_response",
    )
    quest.current_offer = assignment
    _set_quest_status(quest, FamQuestStatus.awaiting_acceptance)
    return assignment


def offer_famquest(
    actor: TrustedActorContext, quest: FamQuest, target_profile: KidProfile,
) -> FamQuestAssignment:
    """Atomically create and return a parent's offer to the target profile.

    Require a trusted parent actor, preserve declined offers, and make the new
    assignment the quest's current offer. Raise ValueError if the quest cannot
    receive an offer or the target profile is inactive.
    """
    require_parent(actor)
    with db0.atomic():
        return _offer_famquest(actor, quest, target_profile)


def _respond_to_offer(
    actor: TrustedActorContext, assignment: FamQuestAssignment,
    response: AssignmentResponse, comment: str | None = None,
) -> None:
    """Atomically record a child's acceptance or decline of their current offer.

    Store the response, timestamp, and optional comment on the assignment.
    Acceptance assigns responsibility and marks the quest picked; decline
    makes it await assignment again. Raise ValueError if the offer is not
    current, pending, or addressed to the trusted child actor.
    """
    with db0.atomic():
        profile = _child_profile(actor)
        quest = assignment.quest
        if (assignment.target_profile != profile or quest.current_offer != assignment
                or assignment.response_status != AssignmentResponse.awaiting_response
                or quest.status != FamQuestStatus.awaiting_acceptance
                or quest.responsible_profile is not None):
            raise ValueError("offer is not current or does not belong to actor")
        assignment.response_status = response
        assignment.responded_at = datetime.now(UTC)
        assignment.child_comment = comment
        db0.tags(assignment).remove("kidland.assignment.awaiting_response")
        if response == AssignmentResponse.accepted:
            quest.responsible_profile = profile
            db0.tags(quest).add(db0.as_tag(profile))
            _set_quest_status(quest, FamQuestStatus.picked)
        else:
            _set_quest_status(quest, FamQuestStatus.awaiting_assignment)


def accept_famquest_offer(
    actor: TrustedActorContext, assignment: FamQuestAssignment,
) -> None:
    """Accept only the current offer addressed to the trusted child."""
    _respond_to_offer(actor, assignment, AssignmentResponse.accepted)


def decline_famquest_offer(
    actor: TrustedActorContext, assignment: FamQuestAssignment, comment: str | None = None,
) -> None:
    """Decline an offer without requiring a child explanation."""
    _respond_to_offer(actor, assignment, AssignmentResponse.declined, comment)


def pick_famquest(actor: TrustedActorContext, quest: FamQuest) -> None:
    """Atomically establish the sole responsible eligible child."""
    with db0.atomic():
        profile = _child_profile(actor)
        if (quest.status != FamQuestStatus.available
                or quest.responsible_profile is not None
                or profile not in quest.eligible_profiles):
            raise ValueError("quest is not available to actor")
        quest.responsible_profile = profile
        for eligible_profile in set(quest.eligible_profiles):
            if eligible_profile != profile:
                db0.tags(quest).remove(db0.as_tag(eligible_profile))
        _set_quest_status(quest, FamQuestStatus.picked)


def submit_famquest_completion(
    actor: TrustedActorContext, quest: FamQuest,
) -> FamQuestCompletion:
    """Create a fresh attempt from the responsible child's picked/returned quest."""
    with db0.atomic():
        profile = _child_profile(actor)
        if (quest.responsible_profile != profile
                or quest.status not in (FamQuestStatus.picked, FamQuestStatus.returned)):
            raise ValueError("only the responsible child can submit a picked or returned quest")
        completion = FamQuestCompletion(quest, profile, datetime.now(UTC))
        db0.tags(completion).add(
            db0.as_tag(quest), db0.as_tag(profile), "kidland.completion.pending_review",
        )
        quest.current_completion = completion
        _set_quest_status(quest, FamQuestStatus.submitted_for_approval)
        return completion


def _review_completion(
    actor: TrustedActorContext, completion: FamQuestCompletion,
    status: CompletionReviewStatus, note: str | None,
) -> None:
    """Record a review of the current pending attempt in the caller's atomic block.

    Store the review status, actor identity, timestamp, and optional note, then
    update workflow tags and mark the quest rewarded or returned. The caller
    authorizes the parent and records any reward. Raise ValueError if the
    attempt is no longer current, pending, or owned by the responsible child.
    """
    quest = completion.quest
    if (quest.current_completion != completion
            or completion.review_status != CompletionReviewStatus.pending
            or quest.status != FamQuestStatus.submitted_for_approval
            or completion.kid_profile != quest.responsible_profile):
        raise ValueError("completion is not the current pending attempt")
    completion.review_status = status
    completion.reviewed_by = actor.member_uuid
    completion.reviewed_at = datetime.now(UTC)
    completion.review_note = note
    db0.tags(completion).remove("kidland.completion.pending_review")
    _set_quest_status(
        quest,
        FamQuestStatus.rewarded if status == CompletionReviewStatus.approved
        else FamQuestStatus.returned,
    )


def approve_famquest_completion(
    actor: TrustedActorContext, completion: FamQuestCompletion, note: str | None = None,
) -> LedgerEntry:
    """Approve a current attempt and award one directly linked reward atomically."""
    require_parent(actor)
    with db0.atomic():
        _review_completion(actor, completion, CompletionReviewStatus.approved, note)
        return record_ledger_entry(
            completion.kid_profile, completion.quest.reward, "FamQuest completion approved",
            LedgerSourceType.famquest_reward, source_reference=completion,
        )


def reject_famquest_completion(
    actor: TrustedActorContext, completion: FamQuestCompletion, note: str,
) -> None:
    """Return the occurrence with a required explanation and no reward."""
    require_parent(actor)
    if not note.strip():
        raise ValueError("review note is required")
    with db0.atomic():
        _review_completion(actor, completion, CompletionReviewStatus.rejected, note)
