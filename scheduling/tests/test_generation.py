"""
Section 68 philosophy: don't just check a timetable exists — check the
actual constraints hold. Every test here inspects real TimetableEntry rows
produced by the real generator against a real (test) PostgreSQL database.
"""

from django.test import TestCase

from academics.models import SubjectOffering
from common.constants import GenerationScopeType, GenerationStatus
from faculty.models import FacultyAvailability
from scheduling.models import FixedLecture, TimetableEntry, TimetableGeneration, TimetableVersion
from scheduling.services.generator import run_generation
from scheduling.services.slots import LAB_PAIR_LABELS, PERIOD_BY_LABEL

from .factories import build_minimal_scope


def _create_generation(scope, scope_type=GenerationScopeType.COMPLETE, sections=None):
    generation = TimetableGeneration.objects.create(
        academic_year=scope["academic_year"], semester_type="EVEN", scope_type=scope_type,
    )
    generation.sections.set(sections if sections is not None else [scope["section"]])
    generation.departments.set([scope["department"]])
    generation.years.set([scope["year"]])
    return generation


class GenerationHardConstraintTests(TestCase):
    def setUp(self):
        self.scope = build_minimal_scope()

    def test_complete_generation_succeeds(self):
        generation = _create_generation(self.scope)
        run_generation(generation)
        generation.refresh_from_db()
        self.assertEqual(generation.status, GenerationStatus.CURRENT, generation.failure_summary)

        version = TimetableVersion.objects.filter(section=self.scope["section"], status=GenerationStatus.CURRENT).first()
        self.assertIsNotNone(version)
        self.assertEqual(version.version_number, 1)

    def test_no_faculty_double_booking(self):
        generation = _create_generation(self.scope)
        run_generation(generation)
        entries = TimetableEntry.objects.filter(generation=generation, faculty__isnull=False)
        seen = set()
        for e in entries:
            key = (e.faculty_id, e.day, e.period_label)
            self.assertNotIn(key, seen, f"Faculty double-booked at {key}")
            seen.add(key)

    def test_no_classroom_double_booking(self):
        generation = _create_generation(self.scope)
        run_generation(generation)
        entries = TimetableEntry.objects.filter(generation=generation, classroom__isnull=False)
        seen = set()
        for e in entries:
            key = (e.classroom_id, e.day, e.period_label)
            self.assertNotIn(key, seen, f"Classroom double-booked at {key}")
            seen.add(key)

    def test_whole_section_never_overlaps_a_batch_session(self):
        """Regression test for the double-booking bug found during manual
        testing: a whole-section (batch=None) session must never coincide
        with a batch-specific session for the same section."""
        generation = _create_generation(self.scope)
        run_generation(generation)
        entries = list(TimetableEntry.objects.filter(generation=generation))
        whole = {(e.section_id, e.day, e.period_label) for e in entries if e.batch_id is None}
        batch = {(e.section_id, e.day, e.period_label) for e in entries if e.batch_id is not None}
        overlap = whole & batch
        self.assertEqual(overlap, set(), f"Whole-section session overlaps a batch session at {overlap}")

    def test_lab_occupies_exactly_two_valid_consecutive_periods(self):
        generation = _create_generation(self.scope)
        run_generation(generation)
        from common.constants import SessionType

        sessions = {}
        for e in TimetableEntry.objects.filter(generation=generation, session__session_type=SessionType.PRACTICAL):
            sessions.setdefault(e.session_id, []).append(e)

        valid_pairs = set(LAB_PAIR_LABELS)
        for session_id, rows in sessions.items():
            self.assertEqual(len(rows), 2, f"Lab session {session_id} should occupy exactly 2 periods")
            labels = tuple(sorted((rows[0].period_label, rows[1].period_label),
                                   key=lambda l: PERIOD_BY_LABEL[l]["order"]))
            self.assertIn(labels, valid_pairs, f"Lab session {session_id} used an invalid period pair {labels}")
            self.assertEqual(rows[0].day, rows[1].day)

    def test_lab_batches_use_different_rooms_when_simultaneous(self):
        generation = _create_generation(self.scope)
        run_generation(generation)
        from common.constants import SessionType

        entries = TimetableEntry.objects.filter(generation=generation, session__session_type=SessionType.PRACTICAL)
        by_slot = {}
        for e in entries:
            by_slot.setdefault((e.day, e.period_label), []).append(e)
        for slot, rows in by_slot.items():
            batches_here = {r.batch_id for r in rows}
            if len(batches_here) > 1:
                rooms_here = [r.classroom_id for r in rows]
                self.assertEqual(len(rooms_here), len(set(rooms_here)),
                                  f"Two batches share a lab room at the same slot {slot}")

    def test_required_hours_are_fully_scheduled(self):
        generation = _create_generation(self.scope)
        run_generation(generation)
        generation.refresh_from_db()
        self.assertEqual(generation.status, GenerationStatus.CURRENT)

        for offering in SubjectOffering.objects.filter(section=self.scope["section"]):
            subject = offering.subject
            entries = TimetableEntry.objects.filter(generation=generation, session__subject_offering=offering)
            lecture_periods = entries.filter(session__session_type="LECTURE").count()
            tutorial_periods = entries.filter(session__session_type="TUTORIAL").count()
            practical_periods = entries.filter(session__session_type="PRACTICAL").count()
            self.assertEqual(lecture_periods, subject.lecture_hours)
            self.assertEqual(tutorial_periods, subject.tutorial_hours)
            if subject.has_batches:
                # each batch independently needs the full practical hours
                self.assertEqual(practical_periods, subject.practical_hours * subject.num_batches)
            else:
                self.assertEqual(practical_periods, subject.practical_hours)

    def test_faculty_daily_and_weekly_limits_never_exceeded(self):
        fac = self.scope["faculty"][1]
        fac.max_lectures_per_day = 2
        fac.max_lectures_per_week = 4
        fac.save()

        generation = _create_generation(self.scope)
        run_generation(generation)

        from collections import defaultdict
        day_counts = defaultdict(int)
        total = 0
        for e in TimetableEntry.objects.filter(generation=generation, faculty=fac):
            day_counts[e.day] += 1
            total += 1
        for day, count in day_counts.items():
            self.assertLessEqual(count, fac.max_lectures_per_day)
        self.assertLessEqual(total, fac.max_lectures_per_week)

    def test_faculty_unavailability_window_is_respected(self):
        fac = self.scope["faculty"][1]
        p1 = PERIOD_BY_LABEL["P1"]
        FacultyAvailability.objects.create(faculty=fac, day=0, start_time=p1["start"], end_time=p1["end"])

        generation = _create_generation(self.scope)
        run_generation(generation)

        clash = TimetableEntry.objects.filter(generation=generation, faculty=fac, day=0, period_label="P1")
        self.assertFalse(clash.exists(), "Faculty was scheduled during their declared unavailability window")

    def test_fixed_lecture_is_reserved_and_not_overwritten(self):
        offering_os = self.scope["offerings"][1]
        fac2 = self.scope["faculty"][1]
        room1 = self.scope["rooms"][0]

        FixedLecture.objects.create(
            academic_year=self.scope["academic_year"], subject_offering=offering_os,
            session_type="LECTURE", faculty=fac2, classroom=room1, day=0, period_label="P1",
        )

        generation = _create_generation(self.scope)
        run_generation(generation)
        generation.refresh_from_db()
        self.assertEqual(generation.status, GenerationStatus.CURRENT, generation.failure_summary)

        fixed_entry = TimetableEntry.objects.get(
            generation=generation, section=self.scope["section"], day=0, period_label="P1", is_fixed=True,
        )
        self.assertEqual(fixed_entry.faculty_id, fac2.id)
        self.assertEqual(fixed_entry.classroom_id, room1.id)
        self.assertEqual(fixed_entry.session.subject_offering_id, offering_os.id)

    def test_generation_fails_safely_and_never_touches_current(self):
        # First, a successful baseline generation.
        gen1 = _create_generation(self.scope)
        run_generation(gen1)
        gen1.refresh_from_db()
        self.assertEqual(gen1.status, GenerationStatus.CURRENT)

        version_before = TimetableVersion.objects.get(section=self.scope["section"], status=GenerationStatus.CURRENT)
        self.assertEqual(version_before.generation_id, gen1.id)

        # Now make the scope impossible: remove every lab so DBMS practicals
        # can never be placed, and force a SECTION regeneration.
        for lab in self.scope["labs"]:
            lab.is_active = False
            lab.save()

        gen2 = _create_generation(self.scope, scope_type=GenerationScopeType.SECTION)
        run_generation(gen2)
        gen2.refresh_from_db()

        self.assertEqual(gen2.status, GenerationStatus.FAILED)
        self.assertTrue(gen2.failure_summary)
        self.assertTrue(gen2.issues.filter(severity="ERROR").exists())

        # Current must still point at the ORIGINAL successful generation.
        version_after = TimetableVersion.objects.get(section=self.scope["section"], status=GenerationStatus.CURRENT)
        self.assertEqual(version_after.id, version_before.id)
        self.assertEqual(version_after.generation_id, gen1.id)
