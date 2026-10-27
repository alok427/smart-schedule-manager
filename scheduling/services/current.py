"""
Single source of truth for "which timetable rows are CURRENT".

"Current" is a per-(section, semester) pointer (TimetableVersion), not a
property of a whole generation run. The old pattern

    TimetableEntry.objects.filter(generation__versions__status="CURRENT")

joins through *every* version of the generation, so
  * a generation covering 5 sections returned every entry 5 times (duplicates), and
  * after re-generating just one section, that section's OLD entries still
    matched because the old generation kept CURRENT versions for other sections.

This helper only matches an entry when the CURRENT version for that same
(generation, section) exists, so each entry appears exactly once.
"""

from django.db.models import Exists, OuterRef

from common.constants import GenerationStatus
from scheduling.models import TimetableEntry, TimetableVersion


def current_entries():
    return TimetableEntry.objects.filter(
        Exists(
            TimetableVersion.objects.filter(
                generation=OuterRef("generation"),
                section=OuterRef("section"),
                status=GenerationStatus.CURRENT,
            )
        )
    )
