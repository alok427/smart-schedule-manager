"""
Section 43: manual modification, always validated immediately through the
SAME central validation service the generator uses (Section 39) — never a
separate, parallel set of conflict checks.

Every operation here either fully succeeds (and is logged as a
TimetableChange) or is fully rejected with a clear reason; nothing is ever
partially applied.
"""

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from classrooms.models import Classroom
from faculty.models import Faculty
from scheduling.models import TimetableChange, TimetableEntry, TimetableSession
from scheduling.services.current import current_entries
from scheduling.services.eligibility import faculty_available_at, is_faculty_eligible_for_offering
from scheduling.services.occupancy import OccupancyMap
from scheduling.services.slots import PERIOD_BY_LABEL
from scheduling.services.validation import ValidationResult


def build_live_occupancy(exclude_entry_ids=frozenset()):
    """Fresh occupancy snapshot of everything currently published, minus
    whatever the caller is about to move (so a slot isn't flagged as
    'conflicting with itself')."""
    om = OccupancyMap()
    entries = (
        current_entries()
        .exclude(id__in=exclude_entry_ids)
        .select_related("faculty", "classroom")
    )
    for e in entries.iterator():
        om.reserve(
            faculty_id=e.faculty_id, classroom_id=e.classroom_id,
            section_id=e.section_id, batch_id=e.batch_id, day=e.day, period_label=e.period_label,
        )
    return om


def move_session(session: TimetableSession, *, new_day: int, new_period_labels: list[str], actor) -> ValidationResult:
    """Move an entire session (1 period for lecture/tutorial, 2 for a lab
    block) to a new day/period-pair, keeping the same faculty and room."""
    entries = list(TimetableEntry.objects.filter(session=session).select_related("faculty", "classroom", "section"))
    if not entries:
        return ValidationResult(violations=["Session has no entries to move."])
    if any(e.is_fixed for e in entries):
        return ValidationResult(violations=["This session is fixed/locked and cannot be moved via manual edit."])
    if len(new_period_labels) != len(entries):
        return ValidationResult(violations=[
            f"This session needs {len(entries)} period(s); {len(new_period_labels)} were given."
        ])

    occupancy = build_live_occupancy(exclude_entry_ids={e.id for e in entries})
    violations = []
    for label in new_period_labels:
        if label not in PERIOD_BY_LABEL:
            violations.append(f"'{label}' is not a valid period label.")
            continue
        entry = entries[0]
        if not occupancy.section_free(entry.section_id, entry.batch_id, new_day, label):
            violations.append(f"Section clash: {entry.section} already has something at {label} on this day.")
        if entry.faculty_id:
            faculty = entry.faculty
            if not occupancy.faculty_free(faculty.id, new_day, label):
                violations.append(f"Faculty clash: {faculty} is already booked at {label} on this day.")
            if not faculty_available_at(faculty, new_day, label):
                violations.append(f"{faculty} is marked unavailable at {label} on this day.")
        if entry.classroom_id and not occupancy.classroom_free(entry.classroom_id, new_day, label):
            violations.append(f"Room clash: {entry.classroom} is already booked at {label} on this day.")

    result = ValidationResult(violations=violations)
    if not result.is_valid:
        return result

    with transaction.atomic():
        old_summary = f"{entries[0].get_day_display()} {'/'.join(e.period_label for e in entries)}"
        for entry, label in zip(entries, new_period_labels):
            p = PERIOD_BY_LABEL[label]
            entry.day = new_day
            entry.period_label = label
            entry.start_time = p["start"]
            entry.end_time = p["end"]
            entry.save(update_fields=["day", "period_label", "start_time", "end_time"])

        version = entries[0].generation.versions.filter(
            section=entries[0].section, status="CURRENT"
        ).first()
        new_summary = f"{entries[0].get_day_display()} {'/'.join(new_period_labels)}"
        TimetableChange.objects.create(
            version=version, entry=entries[0], source="MANUAL_EDIT",
            description=f"Moved {entries[0].session} from {old_summary} to {new_summary}.",
            old_data={"day": entries[0].day, "periods": [e.period_label for e in entries]},
            new_data={"day": new_day, "periods": new_period_labels},
            changed_by=actor,
        )
    return result


def change_classroom_for_session(session: TimetableSession, *, new_classroom: Classroom, actor) -> ValidationResult:
    entries = list(TimetableEntry.objects.filter(session=session).select_related("classroom", "section"))
    if not entries:
        return ValidationResult(violations=["Session has no entries."])
    if any(e.is_fixed for e in entries):
        return ValidationResult(violations=["This session is fixed/locked and cannot be changed via manual edit."])
    if not new_classroom.is_active:
        return ValidationResult(violations=[f"{new_classroom} is not active."])

    occupancy = build_live_occupancy(exclude_entry_ids={e.id for e in entries})
    violations = [
        f"Room clash: {new_classroom} is already booked at {e.period_label} on {e.get_day_display()}."
        for e in entries if not occupancy.classroom_free(new_classroom.id, e.day, e.period_label)
    ]
    result = ValidationResult(violations=violations)
    if not result.is_valid:
        return result

    with transaction.atomic():
        old_room = entries[0].classroom
        for e in entries:
            e.classroom = new_classroom
            e.save(update_fields=["classroom"])
        version = entries[0].generation.versions.filter(section=entries[0].section, status="CURRENT").first()
        TimetableChange.objects.create(
            version=version, entry=entries[0], source="ROOM_CHANGE",
            description=f"Room changed for {entries[0].session} from {old_room} to {new_classroom}.",
            old_data={"classroom_id": old_room.id if old_room else None},
            new_data={"classroom_id": new_classroom.id},
            changed_by=actor,
        )
    return result


def change_faculty_for_offering(offering, *, new_faculty: Faculty, actor) -> ValidationResult:
    """
    Section 33: changing faculty for a subject changes ALL its scheduled
    sessions in the currently-published timetable, atomically — or the
    whole change is rejected.
    """
    entries = list(
        current_entries().filter(
            session__subject_offering=offering,
        ).select_related("faculty")
    )
    if not entries:
        return ValidationResult(violations=["No published entries found for this subject offering."])
    if any(e.is_fixed for e in entries):
        return ValidationResult(violations=[
            "One or more sessions for this subject are fixed/locked; unlock them before changing faculty."
        ])

    if not is_faculty_eligible_for_offering(new_faculty, offering):
        return ValidationResult(violations=[f"{new_faculty} is not eligible to teach {offering.subject}."])

    occupancy = build_live_occupancy(exclude_entry_ids={e.id for e in entries})
    violations = []
    for e in entries:
        if not occupancy.faculty_free(new_faculty.id, e.day, e.period_label):
            violations.append(f"{new_faculty} is already booked on {e.get_day_display()} {e.period_label}.")
        if not faculty_available_at(new_faculty, e.day, e.period_label):
            violations.append(f"{new_faculty} is marked unavailable on {e.get_day_display()} {e.period_label}.")

    n = len(entries)
    per_day = {}
    for e in entries:
        per_day[e.day] = per_day.get(e.day, 0) + 1
    for day, count in per_day.items():
        if occupancy.faculty_periods_on_day(new_faculty.id, day) + count > new_faculty.max_lectures_per_day:
            violations.append(f"{new_faculty} would exceed their daily lecture limit.")
    if occupancy.faculty_periods_total(new_faculty.id) + n > new_faculty.max_lectures_per_week:
        violations.append(f"{new_faculty} would exceed their weekly lecture limit.")

    result = ValidationResult(violations=violations)
    if not result.is_valid:
        return result

    with transaction.atomic():
        old_faculty = entries[0].faculty
        for e in entries:
            e.faculty = new_faculty
            e.save(update_fields=["faculty"])
        offering.faculty = new_faculty
        offering.save(update_fields=["faculty"])

        version = entries[0].generation.versions.filter(section=offering.section, status="CURRENT").first()
        TimetableChange.objects.create(
            version=version, source="FACULTY_SWAP",
            description=f"Faculty for {offering} changed from {old_faculty} to {new_faculty} "
                        f"({len(entries)} session(s) updated).",
            old_data={"faculty_id": old_faculty.id if old_faculty else None},
            new_data={"faculty_id": new_faculty.id},
            changed_by=actor,
        )
    return result
