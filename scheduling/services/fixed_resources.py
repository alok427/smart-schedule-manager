"""
Section 27/28: fixed lectures are loaded and reserved FIRST, before any
other scheduling happens. If a fixed lecture conflicts with another
(already-reserved) fixed lecture or with existing global occupancy, it is
NEVER auto-modified — it's reported as a GenerationIssue and left out of
this generation's schedule so the admin can fix the source data.
"""

from collections import defaultdict

from common.constants import Day, SessionType
from scheduling.models import FixedLecture, GenerationIssue, TimetableEntry, TimetableSession
from scheduling.services.slots import PERIOD_BY_LABEL, is_before_lunch, periods_for_pair


def _period_labels_for(fixed: FixedLecture):
    if fixed.session_type == SessionType.PRACTICAL:
        from scheduling.services.slots import LAB_PAIR_LABELS
        for pair in LAB_PAIR_LABELS:
            if pair[0] == fixed.period_label:
                return list(pair)
        return None  # not a valid lab-pair start — caught by validation below
    return [fixed.period_label]


def load_and_reserve_fixed_lectures(generation, occupancy):
    """
    Returns `fixed_counts`: {offering_id: {"LECTURE": n, "TUTORIAL": n,
    "PRACTICAL_BLOCKS": n}} for sessions the session builder should treat
    as already satisfied.
    """
    fixed_counts = defaultdict(lambda: defaultdict(int))

    qs = FixedLecture.objects.filter(
        is_active=True,
        subject_offering__section__in=generation.sections.all(),
    ).select_related("subject_offering", "faculty", "classroom", "subject_offering__section")

    for fixed in qs:
        offering = fixed.subject_offering
        period_labels = _period_labels_for(fixed)
        if not period_labels:
            GenerationIssue.objects.create(
                generation=generation, severity="ERROR", section=offering.section, subject=offering.subject,
                message=(
                    f"Fixed lecture for {offering.subject.code} ({offering.section}) has an invalid lab "
                    f"period_label '{fixed.period_label}' — it is not the start of a valid two-period lab pair."
                ),
            )
            continue

        # Check every period the fixed lecture needs is actually free.
        conflict = None
        for label in period_labels:
            if fixed.faculty_id and not occupancy.faculty_free(fixed.faculty_id, fixed.day, label):
                conflict = f"faculty {fixed.faculty} is already booked on {Day(fixed.day).label} {label}"
                break
            if fixed.classroom_id and not occupancy.classroom_free(fixed.classroom_id, fixed.day, label):
                conflict = f"room {fixed.classroom} is already booked on {Day(fixed.day).label} {label}"
                break
            if not occupancy.section_free(offering.section_id, fixed.batch_id, fixed.day, label):
                conflict = f"{offering.section} already has a class on {Day(fixed.day).label} {label}"
                break

        if conflict:
            GenerationIssue.objects.create(
                generation=generation, severity="ERROR", section=offering.section, subject=offering.subject,
                message=(
                    f"Fixed lecture for {offering.subject.code} ({offering.section}) on "
                    f"{Day(fixed.day).label} {fixed.period_label} could not be reserved because {conflict}. "
                    f"Fixed entries are never auto-modified — please correct the conflicting configuration."
                ),
            )
            continue

        # Reserve + materialise the session + entries.
        session = TimetableSession.objects.create(
            generation=generation, subject_offering=offering, session_type=fixed.session_type,
            sequence_number=0, duration_periods=len(period_labels), batch=fixed.batch, is_scheduled=True,
        )
        for label in period_labels:
            p = PERIOD_BY_LABEL[label]
            TimetableEntry.objects.create(
                generation=generation, session=session, section=offering.section, batch=fixed.batch,
                faculty=fixed.faculty, classroom=fixed.classroom, day=fixed.day, period_label=label,
                start_time=p["start"], end_time=p["end"], is_fixed=True, fixed_lecture=fixed,
            )
            occupancy.reserve(
                faculty_id=fixed.faculty_id, classroom_id=fixed.classroom_id,
                section_id=offering.section_id, batch_id=fixed.batch_id, day=fixed.day, period_label=label,
            )

        if fixed.session_type == SessionType.PRACTICAL:
            fixed_counts[offering.id]["PRACTICAL_BLOCKS"] += 1
        else:
            fixed_counts[offering.id][fixed.session_type] += 1

    return fixed_counts
