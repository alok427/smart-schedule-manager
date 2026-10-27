from django.test import TestCase

from common.constants import GenerationScopeType, GenerationStatus
from scheduling.models import TimetableEntry, TimetableGeneration, TimetableVersion
from scheduling.services.generator import run_generation
from scheduling.services.versioning import restore_version

from .factories import build_minimal_scope
from .test_generation import _create_generation


class RestoreTests(TestCase):
    def setUp(self):
        self.scope = build_minimal_scope()

    def test_restore_flips_pointer_without_calling_generator(self):
        gen1 = _create_generation(self.scope)
        run_generation(gen1)
        gen1.refresh_from_db()
        self.assertEqual(gen1.status, GenerationStatus.CURRENT)

        v1 = TimetableVersion.objects.get(section=self.scope["section"], status=GenerationStatus.CURRENT)
        entries_v1_count = TimetableEntry.objects.filter(generation=gen1).count()

        gen2 = _create_generation(self.scope)
        run_generation(gen2)
        gen2.refresh_from_db()
        self.assertEqual(gen2.status, GenerationStatus.CURRENT)

        v1.refresh_from_db()
        self.assertEqual(v1.status, GenerationStatus.HISTORICAL)
        v2 = TimetableVersion.objects.get(section=self.scope["section"], status=GenerationStatus.CURRENT)
        self.assertNotEqual(v2.id, v1.id)

        generation_count_before_restore = TimetableGeneration.objects.count()

        result = restore_version(v1, actor=None)
        self.assertTrue(result.is_valid, result.violations)

        v1.refresh_from_db()
        v2.refresh_from_db()
        self.assertEqual(v1.status, GenerationStatus.CURRENT)
        self.assertEqual(v2.status, GenerationStatus.HISTORICAL)

        # No new generation was created, and v1's underlying entries are untouched.
        self.assertEqual(TimetableGeneration.objects.count(), generation_count_before_restore)
        self.assertEqual(TimetableEntry.objects.filter(generation=gen1).count(), entries_v1_count)
        self.assertEqual(v1.generation_id, gen1.id)

    def test_history_preserves_all_versions(self):
        for _ in range(3):
            gen = _create_generation(self.scope)
            run_generation(gen)

        versions = TimetableVersion.objects.filter(section=self.scope["section"]).order_by("version_number")
        self.assertEqual(list(versions.values_list("version_number", flat=True)), [1, 2, 3])
        self.assertEqual(versions.filter(status=GenerationStatus.CURRENT).count(), 1)
        self.assertEqual(versions.last().version_number, 3)
        self.assertEqual(versions.last().status, GenerationStatus.CURRENT)
