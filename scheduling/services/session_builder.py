"""
Builds the set of TimetableSession rows that still need to be placed,
after fixed lectures have already claimed some of the required hours
(Section 15, 37 step 14).
"""

from common.constants import SessionType
from scheduling.models import TimetableSession


def build_sessions_for_offering(generation, offering, already_fixed_counts):
    """
    already_fixed_counts: dict like {"LECTURE": 1, "TUTORIAL": 0,
    "PRACTICAL_BLOCKS": 0} — periods already satisfied by active,
    successfully-reserved FixedLecture rows for this offering.
    """
    subject = offering.subject
    created = []

    remaining_lecture = max(0, subject.lecture_hours - already_fixed_counts.get("LECTURE", 0))
    remaining_tutorial = max(0, subject.tutorial_hours - already_fixed_counts.get("TUTORIAL", 0))
    remaining_lab_blocks = max(0, subject.required_lab_blocks - already_fixed_counts.get("PRACTICAL_BLOCKS", 0))

    seq = 1
    for _ in range(remaining_lecture):
        created.append(TimetableSession(
            generation=generation, subject_offering=offering, session_type=SessionType.LECTURE,
            sequence_number=seq, duration_periods=1,
        ))
        seq += 1

    seq = 1
    for _ in range(remaining_tutorial):
        created.append(TimetableSession(
            generation=generation, subject_offering=offering, session_type=SessionType.TUTORIAL,
            sequence_number=seq, duration_periods=1,
        ))
        seq += 1

    # Section 14: lab batches. If the subject has batches, each batch needs
    # its own lab session (so two batches can be in two different labs at
    # the same time); otherwise one session per required block.
    if subject.has_batches and subject.num_batches > 1:
        batches = list(offering.section.batches.all()[: subject.num_batches])
        if not batches:
            batches = [None]  # fall back gracefully if batches aren't configured yet
    else:
        batches = [None]

    for batch in batches:
        seq = 1
        for _ in range(remaining_lab_blocks):
            created.append(TimetableSession(
                generation=generation, subject_offering=offering, session_type=SessionType.PRACTICAL,
                sequence_number=seq, duration_periods=2, batch=batch,
            ))
            seq += 1

    TimetableSession.objects.bulk_create(created)
    return created
