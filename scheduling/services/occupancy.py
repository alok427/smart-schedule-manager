"""
In-memory global occupancy maps (Section 70: avoid repeated queries during
generation; Section 9: global conflict-aware scheduling).

Section-level occupancy needs a bit more care than faculty/classroom:
a whole-section session (batch=None) involves EVERY student in the
section, so it conflicts with ANY batch-specific session at the same
slot (a student can't be in a lecture and a lab at once) as well as with
another whole-section session. Two DIFFERENT batches' sessions at the
same slot do NOT conflict with each other — that's the normal case of
two lab batches running in parallel (Section 14).
"""

from collections import defaultdict

from scheduling.models import TimetableEntry
from scheduling.services.current import current_entries


class OccupancyMap:
    def __init__(self):
        self.faculty = set()          # (faculty_id, day, period_label)
        self.classroom = set()        # (classroom_id, day, period_label)
        self.section_whole = set()    # (section_id, day, period_label) -- batch=None bookings
        self.section_batch = set()    # (section_id, batch_id, day, period_label) -- batch-specific bookings
        self._faculty_day_count = defaultdict(int)          # (faculty_id, day) -> count
        self._faculty_week_count = defaultdict(int)         # faculty_id -> count
        self._section_any_batch_busy = defaultdict(int)     # (section_id, day, period_label) -> count of batches busy

    # --- loading -------------------------------------------------------
    def load_external_current_occupancy(self, generation):
        """
        Load occupancy from OTHER sections' currently-published timetables
        (Section 9: a selected-section regeneration must never clash with
        the rest of the college's live schedule). Sections that ARE in
        this generation's own scope are excluded here — this generation
        owns rebuilding their slots from scratch.
        """
        in_scope_section_ids = set(generation.sections.values_list("id", flat=True))
        external_entries = current_entries().exclude(
            section_id__in=in_scope_section_ids
        ).select_related("faculty", "classroom", "section")

        for entry in external_entries.iterator():
            if entry.faculty_id:
                self.faculty.add((entry.faculty_id, entry.day, entry.period_label))
                self._faculty_day_count[(entry.faculty_id, entry.day)] += 1
                self._faculty_week_count[entry.faculty_id] += 1
            if entry.classroom_id:
                self.classroom.add((entry.classroom_id, entry.day, entry.period_label))
            self._reserve_section(entry.section_id, entry.batch_id, entry.day, entry.period_label)

    # --- internal section helpers ---------------------------------------
    def _reserve_section(self, section_id, batch_id, day, period_label):
        if batch_id is None:
            self.section_whole.add((section_id, day, period_label))
        else:
            self.section_batch.add((section_id, batch_id, day, period_label))
            self._section_any_batch_busy[(section_id, day, period_label)] += 1

    def _release_section(self, section_id, batch_id, day, period_label):
        if batch_id is None:
            self.section_whole.discard((section_id, day, period_label))
        else:
            self.section_batch.discard((section_id, batch_id, day, period_label))
            key = (section_id, day, period_label)
            if self._section_any_batch_busy.get(key, 0) > 0:
                self._section_any_batch_busy[key] -= 1

    # --- queries ---------------------------------------------------------
    def faculty_free(self, faculty_id, day, period_label):
        return (faculty_id, day, period_label) not in self.faculty

    def classroom_free(self, classroom_id, day, period_label):
        return (classroom_id, day, period_label) not in self.classroom

    def section_free(self, section_id, batch_id, day, period_label):
        """
        batch_id=None (whole-section session): free only if no whole-
        section booking AND no batch of this section is busy either.
        batch_id=<id> (batch-specific session): free if that batch has
        nothing booked AND there's no whole-section booking blocking
        everyone. Other batches being busy is irrelevant.
        """
        if (section_id, day, period_label) in self.section_whole:
            return False
        if batch_id is None:
            return self._section_any_batch_busy.get((section_id, day, period_label), 0) == 0
        return (section_id, batch_id, day, period_label) not in self.section_batch

    # --- mutation ----------------------------------------------------------
    def reserve(self, *, faculty_id=None, classroom_id=None, section_id, batch_id, day, period_label):
        if faculty_id:
            self.faculty.add((faculty_id, day, period_label))
            self._faculty_day_count[(faculty_id, day)] += 1
            self._faculty_week_count[faculty_id] += 1
        if classroom_id:
            self.classroom.add((classroom_id, day, period_label))
        self._reserve_section(section_id, batch_id, day, period_label)

    def release(self, *, faculty_id=None, classroom_id=None, section_id, batch_id, day, period_label):
        if faculty_id and (faculty_id, day, period_label) in self.faculty:
            self.faculty.discard((faculty_id, day, period_label))
            self._faculty_day_count[(faculty_id, day)] -= 1
            self._faculty_week_count[faculty_id] -= 1
        if classroom_id:
            self.classroom.discard((classroom_id, day, period_label))
        self._release_section(section_id, batch_id, day, period_label)

    # --- counting (for capacity checks) -------------------------------
    def faculty_periods_on_day(self, faculty_id, day):
        return self._faculty_day_count.get((faculty_id, day), 0)

    def faculty_periods_total(self, faculty_id):
        return self._faculty_week_count.get(faculty_id, 0)
