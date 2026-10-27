from django.test import TestCase

from common.constants import FacultyType, GenerationStatus, SubjectCategory
from faculty.models import Faculty, FacultyAssignmentRule
from scheduling.models import TimetableEntry
from scheduling.services.generator import run_generation

from .factories import build_minimal_scope
from .test_generation import _create_generation


class FacultyAssignmentRuleTests(TestCase):
    def setUp(self):
        self.scope = build_minimal_scope()

    def test_supporting_faculty_without_rule_is_never_assigned(self):
        """Section 19/20: existing in the DB does not make a SUPPORTING
        faculty eligible for a subject with no rule granting it."""
        supporting = Faculty.objects.create(
            department=self.scope["department"], name="Dr. Support", email="support@test.edu",
            short_code="SUP", faculty_type=FacultyType.SUPPORTING,
        )
        generation = _create_generation(self.scope)
        run_generation(generation)
        generation.refresh_from_db()
        self.assertEqual(generation.status, GenerationStatus.CURRENT, generation.failure_summary)

        assigned_faculty_ids = set(
            TimetableEntry.objects.filter(generation=generation).values_list("faculty_id", flat=True)
        )
        self.assertNotIn(supporting.id, assigned_faculty_ids)

    def test_supporting_faculty_with_rule_can_be_assigned(self):
        supporting = Faculty.objects.create(
            department=self.scope["department"], name="Dr. Support", email="support2@test.edu",
            short_code="SU2", faculty_type=FacultyType.SUPPORTING,
        )
        os_subject = self.scope["subjects"][1]
        FacultyAssignmentRule.objects.create(
            faculty=supporting, subject=os_subject, is_generator_eligible=True, is_active=True,
        )
        # Make the supporting faculty preferred over the existing one for OS.
        offering_os = self.scope["offerings"][1]
        offering_os.faculty = None
        offering_os.save(update_fields=["faculty"])

        from faculty.models import FacultySubjectPreference
        FacultySubjectPreference.objects.create(faculty=supporting, subject=os_subject, priority=1)

        generation = _create_generation(self.scope)
        run_generation(generation)
        generation.refresh_from_db()
        self.assertEqual(generation.status, GenerationStatus.CURRENT, generation.failure_summary)

        os_entries = TimetableEntry.objects.filter(generation=generation, session__subject_offering=offering_os)
        self.assertTrue(os_entries.exists())
        self.assertTrue(all(e.faculty_id == supporting.id for e in os_entries))

    def test_fixed_day_and_slot_rule_is_honoured(self):
        """Section 20/21: a rule's fixed_day/fixed_slot_label must be
        exactly where that faculty's sessions for this subject land."""
        os_subject = self.scope["subjects"][1]
        offering_os = self.scope["offerings"][1]
        fac2 = self.scope["faculty"][1]
        offering_os.faculty = None
        offering_os.is_faculty_locked = False
        offering_os.save(update_fields=["faculty", "is_faculty_locked"])

        # Fix ONLY the lecture slot; give OS just 1 lecture hour so a single
        # fixed slot can cover the whole thing deterministically.
        os_subject.lecture_hours = 1
        os_subject.tutorial_hours = 0
        os_subject.save(update_fields=["lecture_hours", "tutorial_hours"])

        FacultyAssignmentRule.objects.create(
            faculty=fac2, subject=os_subject, is_generator_eligible=True, is_active=True,
            fixed_day=2, fixed_slot_label="P3",
        )
        from faculty.models import FacultySubjectPreference
        FacultySubjectPreference.objects.create(faculty=fac2, subject=os_subject, priority=1)

        generation = _create_generation(self.scope)
        run_generation(generation)
        generation.refresh_from_db()
        self.assertEqual(generation.status, GenerationStatus.CURRENT, generation.failure_summary)

        entries = TimetableEntry.objects.filter(generation=generation, session__subject_offering=offering_os)
        self.assertEqual(entries.count(), 1)
        entry = entries.first()
        self.assertEqual(entry.day, 2)
        self.assertEqual(entry.period_label, "P3")
        self.assertEqual(entry.faculty_id, fac2.id)

    def test_max_lectures_cap_excludes_faculty_who_cannot_cover_full_subject(self):
        """A rule capping a faculty below the subject's total required
        periods must exclude them as the (sole) faculty for it."""
        os_subject = self.scope["subjects"][1]  # 3 lecture + 1 tutorial = 4 periods total
        offering_os = self.scope["offerings"][1]
        offering_os.faculty = None
        offering_os.is_faculty_locked = False
        offering_os.save(update_fields=["faculty", "is_faculty_locked"])

        capped = Faculty.objects.create(
            department=self.scope["department"], name="Dr. Capped", email="capped@test.edu",
            short_code="CAP", faculty_type=FacultyType.SUPPORTING,
        )
        FacultyAssignmentRule.objects.create(
            faculty=capped, subject=os_subject, is_generator_eligible=True, is_active=True, max_lectures=2,
        )
        from faculty.models import FacultySubjectPreference
        FacultySubjectPreference.objects.create(faculty=capped, subject=os_subject, priority=1)

        generation = _create_generation(self.scope)
        run_generation(generation)
        generation.refresh_from_db()
        self.assertEqual(generation.status, GenerationStatus.CURRENT, generation.failure_summary)

        entries = TimetableEntry.objects.filter(generation=generation, session__subject_offering=offering_os)
        self.assertTrue(entries.exists())
        # The capped faculty (max 2) cannot cover all 4 required periods,
        # so the generator must have picked someone else instead.
        self.assertFalse(any(e.faculty_id == capped.id for e in entries))
