from django.test import TestCase

from academics.models import Section, SubjectOffering
from common.constants import GenerationScopeType, GenerationStatus
from faculty.models import Faculty
from scheduling.models import TimetableEntry, TimetableVersion
from scheduling.services.generator import run_generation

from .factories import build_minimal_scope
from .test_generation import _create_generation


class GlobalOccupancyTests(TestCase):
    """Section 9: 'A faculty member occupied in one section cannot
    simultaneously teach another section' — must hold across independently
    generated sections, not just within a single generation run."""

    def setUp(self):
        self.scope = build_minimal_scope()

        # A second section in the SAME department, sharing the same
        # faculty pool and rooms — the realistic scenario where clashes
        # would occur if global occupancy weren't respected.
        self.section_b = Section.objects.create(
            department=self.scope["department"], year=self.scope["year"],
            academic_year=self.scope["academic_year"], name="B", strength=55,
        )
        os_subject = self.scope["subjects"][1]
        self.offering_b = SubjectOffering.objects.create(
            subject=os_subject, section=self.section_b, semester=self.scope["semester"],
            faculty=self.scope["faculty"][1],  # same faculty (fac2) teaches OS in both sections
        )

    def test_two_independently_generated_sections_never_clash(self):
        gen_a = _create_generation(self.scope, sections=[self.scope["section"]])
        run_generation(gen_a)
        gen_a.refresh_from_db()
        self.assertEqual(gen_a.status, GenerationStatus.CURRENT, gen_a.failure_summary)

        gen_b = _create_generation(self.scope, sections=[self.section_b])
        run_generation(gen_b)
        gen_b.refresh_from_db()
        self.assertEqual(gen_b.status, GenerationStatus.CURRENT, gen_b.failure_summary)

        entries_a = list(TimetableEntry.objects.filter(generation=gen_a, faculty_id=self.scope["faculty"][1].id))
        entries_b = list(TimetableEntry.objects.filter(generation=gen_b, faculty_id=self.scope["faculty"][1].id))
        self.assertTrue(entries_a and entries_b, "Both sections should have scheduled the shared faculty.")

        slots_a = {(e.day, e.period_label) for e in entries_a}
        slots_b = {(e.day, e.period_label) for e in entries_b}
        self.assertEqual(slots_a & slots_b, set(), "Shared faculty was double-booked across two sections.")

        rooms_a = {(e.day, e.period_label, e.classroom_id) for e in TimetableEntry.objects.filter(generation=gen_a)}
        rooms_b = {(e.day, e.period_label, e.classroom_id) for e in TimetableEntry.objects.filter(generation=gen_b)}
        room_clashes = {(d, p) for (d, p, r) in rooms_a for (d2, p2, r2) in rooms_b if d == d2 and p == p2 and r == r2}
        self.assertEqual(room_clashes, set(), "A classroom was double-booked across two sections.")

    def test_selected_section_regeneration_respects_other_sections_current(self):
        """Generate A, then generate ONLY B (SECTION scope) — B must be
        built around A's already-published schedule, not clash with it."""
        gen_a = _create_generation(self.scope, sections=[self.scope["section"]])
        run_generation(gen_a)
        gen_a.refresh_from_db()
        self.assertEqual(gen_a.status, GenerationStatus.CURRENT)
        version_a_before = TimetableVersion.objects.get(section=self.scope["section"], status=GenerationStatus.CURRENT)

        gen_b = _create_generation(self.scope, scope_type=GenerationScopeType.SECTION, sections=[self.section_b])
        run_generation(gen_b)
        gen_b.refresh_from_db()
        self.assertEqual(gen_b.status, GenerationStatus.CURRENT, gen_b.failure_summary)

        # Section A's published version must be completely untouched.
        version_a_after = TimetableVersion.objects.get(section=self.scope["section"], status=GenerationStatus.CURRENT)
        self.assertEqual(version_a_before.id, version_a_after.id)
        self.assertEqual(version_a_before.generation_id, gen_a.id)

        entries_a = list(TimetableEntry.objects.filter(generation=gen_a, faculty_id=self.scope["faculty"][1].id))
        entries_b = list(TimetableEntry.objects.filter(generation=gen_b, faculty_id=self.scope["faculty"][1].id))
        slots_a = {(e.day, e.period_label) for e in entries_a}
        slots_b = {(e.day, e.period_label) for e in entries_b}
        self.assertEqual(slots_a & slots_b, set(), "Regenerated section B clashed with section A's live schedule.")
