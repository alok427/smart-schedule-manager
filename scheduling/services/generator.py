"""
Orchestrates one generation run, following the Section 37 pipeline:

    load scope -> load calendar -> load fixed resources -> reserve them
    -> build required sessions -> schedule labs/high-constraint first
    -> schedule remaining -> validate -> activate (or fail safely).

Atomic per Section 10: a generation only ever becomes Current after full
success. On failure, everything stays attached to this (now FAILED)
generation for debugging, and the previously-Current TimetableVersion for
every affected section is left completely untouched.
"""

import logging
import random
from collections import defaultdict
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone

from academics.models import SubjectOffering
from common.constants import GenerationStatus, SessionType, SubjectCategory
from faculty.models import Faculty, FacultyLoad
from scheduling.models import GenerationIssue, TimetableEntry, TimetableSession
from scheduling.services import rooms as room_service
from scheduling.services import versioning
from scheduling.services.calendar_helper import working_days_for
from scheduling.services.eligibility import faculty_available_at, rank_candidates_for_offering
from scheduling.services.fixed_resources import load_and_reserve_fixed_lectures
from scheduling.services.occupancy import OccupancyMap
from scheduling.services.session_builder import build_sessions_for_offering
from scheduling.services.slots import LAB_PAIR_LABELS, PERIOD_BY_LABEL, PERIODS, is_before_lunch
from scheduling.services.validation import validate_generation_completeness
from common.constants import RoomType

logger = logging.getLogger("scheduling")


def _subject_total_periods(subject):
    return subject.lecture_hours + subject.tutorial_hours + subject.required_lab_blocks * 2


def _offering_queryset(generation):
    return (
        SubjectOffering.objects.filter(
            section__in=generation.sections.all(),
            semester__academic_year=generation.academic_year,
            semester__semester_type=generation.semester_type,
            is_active=True,
        )
        .select_related("subject", "section", "section__department", "semester", "faculty")
    )


def _day_load_key(section_id, batch_id, day):
    return (section_id, batch_id, day)


class _DayLoadTracker:
    """Tracks how many periods each section already has on each day, purely
    to support the Section 36 soft goal of spreading classes evenly."""

    def __init__(self):
        self.counts = defaultdict(int)
        self.type_counts = defaultdict(int)

    def count(self, section_id, batch_id, day):
        return self.counts[_day_load_key(section_id, batch_id, day)]

    def bump(self, section_id, batch_id, day, n=1):
        self.counts[_day_load_key(section_id, batch_id, day)] += n

    # One-session-type-per-subject-per-day rule. Counts PERIODS already used on
    # a day by one kind of session (lecture / tutorial / lab) of one subject in
    # one section. Labs are tracked per batch, since batches run in parallel.
    @staticmethod
    def _type_key(offering_id, session_type, batch_id, day):
        return (offering_id, session_type, batch_id if session_type == SessionType.PRACTICAL else None, day)

    def type_periods_on_day(self, offering_id, session_type, batch_id, day):
        return self.type_counts[self._type_key(offering_id, session_type, batch_id, day)]

    def mark_type(self, offering_id, session_type, batch_id, day, n=1):
        self.type_counts[self._type_key(offering_id, session_type, batch_id, day)] += n


class _CommittedView:
    """
    occupancy ke upar ek patla wrapper: real placed periods + woh periods jo
    pre-assign ho chuke hain (committed). Sirf faculty pre-assignment phase
    mein use hota hai, taaki ek hi faculty ko overbook na kiya ja sake.
    """

    def __init__(self, occupancy, committed):
        self._occupancy = occupancy
        self._committed = committed

    def faculty_periods_total(self, faculty_id):
        return self._occupancy.faculty_periods_total(faculty_id) + self._committed.get(faculty_id, 0)

    def __getattr__(self, name):
        return getattr(self._occupancy, name)


def _pick_best_fit(candidates, view):
    """
    Best-fit: pehle best priority tier (rank // 1000), us tier mein woh faculty
    jiske paas fit hone ke baad sabse KAM capacity bachti hai. Isse bade
    holes bade subjects ke liye bache rehte hain aur 4-hour ke tukde
    fragment nahi hote.
    """
    best_tier = min(c.priority_rank // 1000 for c in candidates)
    tier = [c for c in candidates if c.priority_rank // 1000 == best_tier]
    return min(tier, key=lambda c: c.faculty.max_lectures_per_week - view.faculty_periods_total(c.faculty.id))


def _preassign_faculty(generation, offerings, all_sessions, occupancy, faculty_cache, rule_cache):
    """
    Placement shuru hone se PEHLE har offering ke liye faculty chun lo:
      - bade load wale offerings pehle (first-fit decreasing),
      - chunte hi faculty ka load 'committed' ho jaata hai, taaki agla
        offering usi capacity ko dobara na ginne.
    allow_multiple_faculty wale subjects ko chhod dete hain (unka purana
    per-session flow chalta rahega).
    """
    remaining = defaultdict(int)
    for s in all_sessions:
        remaining[s.subject_offering_id] += s.duration_periods

    committed = defaultdict(int)
    view = _CommittedView(occupancy, committed)

    todo = [o for o in offerings if remaining.get(o.id) and not o.subject.allow_multiple_faculty]
    todo.sort(key=lambda o: (-remaining[o.id], o.id))

    for offering in todo:
        need = remaining[offering.id]
        candidates = rank_candidates_for_offering(offering, view, required_periods=need)
        if not candidates:
            GenerationIssue.objects.create(
                generation=generation,
                severity="ERROR",
                section=offering.section,
                subject=offering.subject,
                message=(
                    f"{offering.section} — {offering.subject.name} ({offering.subject.code}): "
                    f"koi eligible faculty nahi mila jiske paas {need} free weekly periods bache hon "
                    f"(faculty capacity khatam / max-per-week kam)."
                ),
            )
            continue
        chosen = _pick_best_fit(candidates, view)
        faculty_cache[offering.id] = chosen.faculty
        rule_cache[offering.id] = chosen.rule
        committed[chosen.faculty.id] += need


def run_generation(generation) -> None:
    generation.status = GenerationStatus.RUNNING
    generation.started_at = timezone.now()
    generation.save(update_fields=["status", "started_at"])
    logger.info("Generation #%s started (scope_type=%s)", generation.pk, generation.scope_type)

    rng = random.Random(generation.seed or generation.pk)

    with transaction.atomic():
        occupancy = OccupancyMap()
        occupancy.load_external_current_occupancy(generation)

        fixed_counts = load_and_reserve_fixed_lectures(generation, occupancy)

        offerings = list(_offering_queryset(generation))
        all_sessions = []
        for offering in offerings:
            counts = fixed_counts.get(offering.id, {})
            all_sessions.extend(build_sessions_for_offering(generation, offering, counts))

        # Section 37 steps 15-19: labs/high-constraint sessions first, then
        # core subjects, then everything else. Deterministic tie-break via
        # the seeded RNG so re-runs with the same seed are reproducible
        # (Section 71).
        def priority(session):
            subject = session.subject_offering.subject
            if session.session_type == SessionType.PRACTICAL:
                return 0
            if subject.category == SubjectCategory.CORE:
                return 1
            return 2

        buckets = defaultdict(list)
        for s in all_sessions:
            buckets[priority(s)].append(s)
        for bucket in buckets.values():
            rng.shuffle(bucket)
        ordered_sessions = buckets[0] + buckets[1] + buckets[2]

        day_load = _DayLoadTracker()
        # Seed the day-load tracker with what fixed lectures already placed.
        for e in TimetableEntry.objects.filter(generation=generation, is_fixed=True).select_related("session"):
            day_load.bump(e.section_id, e.batch_id, e.day)
            day_load.mark_type(e.session.subject_offering_id, e.session.session_type, e.batch_id, e.day)

        offering_faculty_cache = {}
        offering_rule_cache = {}
        working_days = {}  # department_id -> [Day,...]

        # Patch: placement se pehle faculty reserve karo (capacity overbooking + fragmentation fix).
        _preassign_faculty(generation, offerings, all_sessions, occupancy, offering_faculty_cache, offering_rule_cache)

        for session in ordered_sessions:
            offering = session.subject_offering
            dept_id = offering.section.department_id
            if dept_id not in working_days:
                working_days[dept_id] = working_days_for(generation.academic_year, offering.section.department)
            days_for_dept = working_days[dept_id]

            placed = _place_session(
                session, offering, occupancy, day_load, days_for_dept, offering_faculty_cache, rng, generation,
                offering_rule_cache,
            )
            if not placed:
                _log_unplaceable(generation, session, offering)

        # Persist faculty choices back onto SubjectOffering (Section 33/34:
        # preserve where possible; only overwritten if it actually changed
        # and wasn't locked).
        to_update = []
        for offering in offerings:
            chosen = offering_faculty_cache.get(offering.id)
            if chosen and offering.faculty_id != chosen.id and not offering.is_faculty_locked:
                offering.faculty = chosen
                to_update.append(offering)
        if to_update:
            SubjectOffering.objects.bulk_update(to_update, ["faculty"])

        result = validate_generation_completeness(generation)
        generation.completed_at = timezone.now()

        if result.is_valid:
            if generation.scope_type == "DRAFT":
                generation.status = GenerationStatus.DRAFT
                generation.save(update_fields=["status", "completed_at"])
            else:
                generation.status = GenerationStatus.CURRENT
                generation.save(update_fields=["status", "completed_at"])
                versioning.activate_generation(generation)
            _recompute_faculty_loads(generation)
            logger.info("Generation #%s completed successfully.", generation.pk)
            _notify_completion(generation, success=True)
        else:
            generation.status = GenerationStatus.FAILED
            generation.failure_summary = "\n".join(result.violations[:20])
            generation.save(update_fields=["status", "failure_summary", "completed_at"])
            logger.warning("Generation #%s FAILED: %s", generation.pk, generation.failure_summary[:500])
            # Section 42: failure must not touch Current. Since nothing was
            # activated above, the previous TimetableVersion rows for every
            # affected section are untouched by construction.
            _notify_completion(generation, success=False)


def _notify_completion(generation, success):
    try:
        from notifications.models import NotificationCategory
        from notifications.services import notify_department, notify_super_admins

        depts = generation.departments.all() or [s.department for s in generation.sections.all()]
        seen = set()
        for dept in depts:
            if dept is None or dept.id in seen:
                continue
            seen.add(dept.id)
            if success:
                notify_department(
                    dept, NotificationCategory.TIMETABLE_PUBLISHED,
                    title=f"Timetable published for {dept.code}",
                    body=f"Generation #{generation.pk} is now Current for the affected sections.",
                )
            else:
                notify_department(
                    dept, NotificationCategory.GENERATION_FAILED,
                    title=f"Timetable generation failed for {dept.code}",
                    body=(generation.failure_summary or "")[:500],
                )
        if not success:
            notify_super_admins(
                "GENERATION_FAILED", title=f"Generation #{generation.pk} failed",
                body=(generation.failure_summary or "")[:500],
            )
    except Exception:  # noqa: BLE001 — notifications must never break generation
        logger.exception("Notification delivery failed for generation #%s", generation.pk)


def _log_unplaceable(generation, session, offering):
    reason = {
        SessionType.PRACTICAL: "no suitable lab is available in any valid two-period slot",
        SessionType.LECTURE: "no eligible faculty + room + slot combination is available",
        SessionType.TUTORIAL: "no eligible faculty + room + slot combination is available",
    }.get(session.session_type, "no valid placement could be found")

    detail = ""
    fail_reasons = getattr(session, "_fail_reasons", None)
    if fail_reasons:
        detail = f" [faculty={getattr(session, '_fail_faculty', [])}; blocked_by={fail_reasons}]"

    GenerationIssue.objects.create(
        generation=generation,
        severity="ERROR",
        section=offering.section,
        subject=offering.subject,
        message=(
            f"{offering.section} — {offering.subject.name} ({offering.subject.code}) "
            f"{session.get_session_type_display()} could not be scheduled because {reason}.{detail}"
        ),
    )


def _place_session(session, offering, occupancy, day_load, days_for_dept, offering_faculty_cache, rng, generation,
                    offering_rule_cache):
    section = offering.section
    subject = offering.subject
    is_lab = session.session_type == SessionType.PRACTICAL
    total_needed = _subject_total_periods(subject)

    # --- pick faculty (Section 18: one faculty per subject unless allowed otherwise) ---
    cache_key = offering.id if not subject.allow_multiple_faculty else (offering.id, session.session_type, session.batch_id)
    faculty = offering_faculty_cache.get(cache_key)
    if faculty is None:
        candidates = rank_candidates_for_offering(offering, occupancy, required_periods=total_needed)
        if not candidates:
            session._fail_reasons = {"no_candidate_faculty": 1}
            return False
    else:
        candidates = [SimpleNamespace(faculty=faculty, rule=offering_rule_cache.get(cache_key))]

    room_type = RoomType.LAB if is_lab else RoomType.CLASSROOM
    capacity_needed = (session.batch.strength if session.batch else section.strength) or 1
    suitable_rooms = room_service.candidate_rooms(section, room_type, capacity_needed)
    if not suitable_rooms:
        session._fail_reasons = {"no_suitable_room_type_or_capacity": 1}
        return False

    reasons = defaultdict(int)
    tried_faculty = []

    default_day_order = sorted(days_for_dept, key=lambda d: day_load.count(section.id, session.batch_id, d))

    # Rule: in a section, the same subject gets at most ONE lecture, ONE
    # tutorial and ONE lab block (2 periods) per day. If a subject has more
    # sessions of a kind than working days, the cap is raised just enough
    # (e.g. 8 lectures over 5 days -> 2 per day) so the rule can never make
    # the timetable impossible.
    n_days = max(1, len(days_for_dept))
    if session.session_type == SessionType.LECTURE:
        type_cap = max(1, -(-subject.lecture_hours // n_days))
    elif session.session_type == SessionType.TUTORIAL:
        type_cap = max(1, -(-subject.tutorial_hours // n_days))
    else:  # PRACTICAL: a lab block is 2 consecutive periods
        type_cap = 2 * max(1, -(-subject.required_lab_blocks // n_days))

    for candidate in candidates:
        fac = candidate.faculty
        tried_faculty.append(getattr(fac, "name", None) or str(fac))
        rule = getattr(candidate, "rule", None)
        default_period_groups = (
            [list(pair) for pair in LAB_PAIR_LABELS] if is_lab
            else _lecture_period_order(subject.category)
        )

        day_order, period_label_groups_base, strict = _apply_rule_ordering(
            default_day_order, default_period_groups, rule, is_lab, days_for_dept,
        )

        for day in day_order:
            if strict and rule.fixed_day is not None and day != rule.fixed_day:
                continue
            if day_load.type_periods_on_day(offering.id, session.session_type, session.batch_id, day) >= type_cap:
                reasons["subject_already_has_this_session_type_today"] += 1
                continue
            period_label_groups = period_label_groups_base
            for period_labels in period_label_groups:
                if not all(occupancy.section_free(section.id, session.batch_id, day, lbl) for lbl in period_labels):
                    reasons["section_busy"] += 1
                    continue
                if not all(occupancy.faculty_free(fac.id, day, lbl) for lbl in period_labels):
                    reasons["faculty_busy"] += 1
                    continue
                if not all(faculty_available_at(fac, day, lbl) for lbl in period_labels):
                    reasons["faculty_unavailable_window"] += 1
                    continue
                n = len(period_labels)
                if occupancy.faculty_periods_on_day(fac.id, day) + n > fac.max_lectures_per_day:
                    reasons["faculty_day_cap"] += 1
                    continue
                if occupancy.faculty_periods_total(fac.id) + n > fac.max_lectures_per_week:
                    reasons["faculty_week_cap"] += 1
                    continue

                room = room_service.find_free_room(suitable_rooms, occupancy, day, period_labels)
                if room is None:
                    reasons["no_free_room"] += 1
                    continue

                # All hard constraints satisfied — commit the placement.
                for lbl in period_labels:
                    p = PERIOD_BY_LABEL[lbl]
                    TimetableEntry.objects.create(
                        generation=generation, session=session, section=section, batch=session.batch,
                        faculty=fac, classroom=room, day=day, period_label=lbl,
                        start_time=p["start"], end_time=p["end"],
                    )
                    occupancy.reserve(
                        faculty_id=fac.id, classroom_id=room.id, section_id=section.id,
                        batch_id=session.batch_id, day=day, period_label=lbl,
                    )
                day_load.bump(section.id, session.batch_id, day, n)
                day_load.mark_type(offering.id, session.session_type, session.batch_id, day, n)
                session.is_scheduled = True
                session.save(update_fields=["is_scheduled"])
                offering_faculty_cache[cache_key] = fac
                offering_rule_cache[cache_key] = rule
                return True

    session._fail_reasons = dict(reasons)
    session._fail_faculty = tried_faculty
    return False


def _apply_rule_ordering(default_day_order, default_period_groups, rule, is_lab, days_for_dept):
    """
    Section 20/21: a FacultyAssignmentRule may FIX a day/slot (hard — the
    placement search below is only allowed to use it) or merely PREFER one
    (soft — tried first, falls back to the normal order otherwise).
    """
    if rule is None:
        return default_day_order, default_period_groups, False

    if rule.fixed_day is not None and rule.fixed_slot_label:
        if is_lab:
            pair = next((p for p in LAB_PAIR_LABELS if p[0] == rule.fixed_slot_label), None)
            groups = [list(pair)] if pair else default_period_groups
        else:
            groups = [[rule.fixed_slot_label]] if rule.fixed_slot_label in PERIOD_BY_LABEL else default_period_groups
        days = [rule.fixed_day] if rule.fixed_day in days_for_dept else default_day_order
        return days, groups, True

    day_order = list(default_day_order)
    if rule.preferred_day is not None and rule.preferred_day in day_order:
        day_order.remove(rule.preferred_day)
        day_order.insert(0, rule.preferred_day)

    period_groups = list(default_period_groups)
    if rule.preferred_slot_label:
        preferred = [g for g in period_groups if rule.preferred_slot_label in g]
        rest = [g for g in period_groups if rule.preferred_slot_label not in g]
        period_groups = preferred + rest

    return day_order, period_groups, False


def _lecture_period_order(category):
    """Section 16 soft constraint: core subjects preferably before lunch.
    Returns a list of single-period-label lists, pre-lunch periods first
    for CORE subjects."""
    pre = [[p["label"]] for p in PERIODS if is_before_lunch(p["label"])]
    post = [[p["label"]] for p in PERIODS if not is_before_lunch(p["label"])]
    if category == SubjectCategory.CORE:
        return pre + post
    return post + pre


def _recompute_faculty_loads(generation):
    """Section 22: recompute workload snapshots after every successful
    generation."""
    semester_ids = set(
        SubjectOffering.objects.filter(section__in=generation.sections.all())
        .values_list("semester_id", flat=True)
    )
    entries = TimetableEntry.objects.filter(generation=generation).select_related("session")
    tally = defaultdict(lambda: defaultdict(int))
    for e in entries:
        if not e.faculty_id:
            continue
        st = e.session.session_type
        if st == SessionType.PRACTICAL:
            tally[e.faculty_id]["practical_periods"] += 1
        elif st == SessionType.LECTURE:
            tally[e.faculty_id]["lecture_count"] += 1
        elif st == SessionType.TUTORIAL:
            tally[e.faculty_id]["tutorial_count"] += 1

    for semester_id in semester_ids:
        for faculty_id, counts in tally.items():
            FacultyLoad.objects.update_or_create(
                faculty_id=faculty_id, generation=generation, semester_id=semester_id,
                defaults={
                    "lecture_count": counts.get("lecture_count", 0),
                    "tutorial_count": counts.get("tutorial_count", 0),
                    "practical_periods": counts.get("practical_periods", 0),
                },
            )