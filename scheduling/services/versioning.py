"""
Section 40/41/44/78: "Current" is a per-(section, semester) pointer
(TimetableVersion), not a property of a whole generation run. Activating a
generation advances that pointer for every section it successfully
covered. Restoring a historical version *only* flips the pointer back —
it must never call the generator or create new assignments.
"""

import logging

from django.db import transaction
from django.utils import timezone

from academics.models import Semester
from common.constants import GenerationStatus
from scheduling.models import TimetableChange, TimetableEntry, TimetableVersion
from scheduling.services.current import current_entries
from scheduling.services.occupancy import OccupancyMap
from scheduling.services.validation import ValidationResult

logger = logging.getLogger("scheduling")


def _target_semester_for_section(section, generation):
    return (
        Semester.objects.filter(
            year=section.year, academic_year=generation.academic_year, semester_type=generation.semester_type
        ).first()
    )


def activate_generation(generation):
    """Advance the Current pointer for every section this generation
    successfully covered. Called only after validate_generation_completeness
    has already confirmed full success (Section 10: never activate a
    partial result)."""
    activated = []
    for section in generation.sections.all():
        semester = _target_semester_for_section(section, generation)
        if semester is None:
            logger.warning(
                "Generation #%s: no Semester found for %s in %s — skipping activation for this section.",
                generation.pk, section, generation.academic_year,
            )
            continue

        with transaction.atomic():
            previous = TimetableVersion.objects.filter(
                section=section, semester=semester, status=GenerationStatus.CURRENT
            ).first()
            if previous:
                previous.status = GenerationStatus.HISTORICAL
                previous.save(update_fields=["status"])

            last_number = (
                TimetableVersion.objects.filter(section=section, semester=semester)
                .order_by("-version_number").values_list("version_number", flat=True).first()
            ) or 0

            version = TimetableVersion.objects.create(
                section=section, semester=semester, generation=generation,
                version_number=last_number + 1, status=GenerationStatus.CURRENT,
                activated_at=timezone.now(), created_by=generation.created_by,
            )
            TimetableChange.objects.create(
                version=version, source="GENERATOR",
                description=f"Generation #{generation.pk} activated as v{version.version_number} for {section}.",
                changed_by=generation.created_by,
            )
            activated.append(version)
    return activated


def restore_version(version: TimetableVersion, actor) -> ValidationResult:
    """
    Section 41/78: activate the EXACT saved entries of a historical
    version. Only re-validates that doing so is still safe against
    everyone else's current schedule — never regenerates, never
    reassigns.
    """
    entries = list(
        TimetableEntry.objects.filter(generation=version.generation, section=version.section)
    )

    occupancy = OccupancyMap()
    # Global occupancy from every OTHER section's current timetable
    # (excluding this section's own current version, which we're about to
    # replace anyway).
    other_current_entries = current_entries().exclude(
        section=version.section
    ).select_related("faculty", "classroom")
    for e in other_current_entries.iterator():
        if e.faculty_id:
            occupancy.faculty.add((e.faculty_id, e.day, e.period_label))
        if e.classroom_id:
            occupancy.classroom.add((e.classroom_id, e.day, e.period_label))

    violations = []
    for e in entries:
        if e.faculty_id and not occupancy.faculty_free(e.faculty_id, e.day, e.period_label):
            violations.append(
                f"Cannot restore: {e.faculty} is now booked elsewhere on "
                f"{e.get_day_display()} {e.period_label}."
            )
        if e.classroom_id and not occupancy.classroom_free(e.classroom_id, e.day, e.period_label):
            violations.append(
                f"Cannot restore: {e.classroom} is now booked elsewhere on "
                f"{e.get_day_display()} {e.period_label}."
            )

    result = ValidationResult(violations=violations)
    if not result.is_valid:
        return result

    with transaction.atomic():
        current = TimetableVersion.objects.filter(
            section=version.section, semester=version.semester, status=GenerationStatus.CURRENT
        ).exclude(pk=version.pk).first()
        if current:
            current.status = GenerationStatus.HISTORICAL
            current.save(update_fields=["status"])

        version.status = GenerationStatus.CURRENT
        version.activated_at = timezone.now()
        version.save(update_fields=["status", "activated_at"])

        TimetableChange.objects.create(
            version=version, source="RESTORE",
            description=f"Restored v{version.version_number} for {version.section} (no regeneration).",
            changed_by=actor,
        )
    return result
