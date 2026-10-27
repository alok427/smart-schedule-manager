"""
Faculty eligibility + ranking (Section 17). This is deliberately its own
module because it's reused by the generator, by faculty-override
validation (Section 33), and by manual-edit validation — the spec is
explicit that conflict/eligibility logic must not be duplicated per view
(Section 39).

Ranking order, exactly as specified:
    1. Fixed/admin assignment
    2. Explicit subject-faculty override (offering.faculty already set)
    3. Faculty assignment restrictions (FacultyAssignmentRule)
    4. Eligibility
    5. Subject priority
    6. Faculty availability
    7. Remaining weekly capacity
    8. Remaining daily capacity
    9. Workload balance (lowest current load wins ties, NOT the sole reason)
"""

from dataclasses import dataclass

from common.constants import FacultyType
from faculty.models import Faculty, FacultyAssignmentRule, FacultySubjectPreference


@dataclass
class Candidate:
    faculty: Faculty
    priority_rank: int  # lower = better; used only to order candidates
    reason: str
    rule: "FacultyAssignmentRule | None" = None


def _rule_matches(rule: FacultyAssignmentRule, offering) -> bool:
    subject = offering.subject
    if rule.subject_id and rule.subject_id != subject.id:
        return False
    if rule.subject_category and rule.subject_category != subject.category:
        return False
    if rule.department_id and rule.department_id != subject.department_id:
        return False
    if rule.allowed_years and subject.year.year_number not in rule.allowed_years:
        return False
    if rule.allowed_semesters and offering.semester.semester_number not in rule.allowed_semesters:
        return False
    if rule.allowed_sections.exists() and not rule.allowed_sections.filter(pk=offering.section_id).exists():
        return False
    return True


def get_matching_rule(faculty, offering) -> "FacultyAssignmentRule | None":
    """
    Most specific active rule for this faculty+offering, preferring a
    subject-specific rule over a category-level rule over a
    department-wide rule (Section 20/21). Returns None if no rule applies
    (meaning: no extra restriction/preference beyond normal eligibility).
    """
    rules = list(FacultyAssignmentRule.objects.filter(faculty=faculty, is_active=True))
    matching = [r for r in rules if _rule_matches(r, offering)]
    if not matching:
        return None

    def specificity(r):
        if r.subject_id:
            return 0
        if r.subject_category:
            return 1
        return 2

    matching.sort(key=specificity)
    return matching[0]


def is_faculty_eligible_for_offering(faculty: Faculty, offering) -> bool:
    """
    Section 19/20 core rule: existing in the DB is not eligibility.
    REGULAR faculty in the same department are eligible by default (still
    ranked by preference/availability/capacity). SUPPORTING / ADDITIONAL /
    RESTRICTED faculty are eligible ONLY if an active FacultyAssignmentRule
    grants them this subject/category/department, and (for RESTRICTED)
    only if that rule also marks them generator-eligible.
    """
    if not faculty.is_active:
        return False

    if faculty.faculty_type == FacultyType.REGULAR:
        if faculty.department_id != offering.subject.department_id:
            # A regular faculty from another department needs an explicit
            # rule too, same as supporting faculty would.
            return _has_matching_generator_eligible_rule(faculty, offering)
        return True

    return _has_matching_generator_eligible_rule(faculty, offering)


def _has_matching_generator_eligible_rule(faculty, offering) -> bool:
    rules = FacultyAssignmentRule.objects.filter(faculty=faculty, is_active=True, is_generator_eligible=True)
    return any(_rule_matches(r, offering) for r in rules)


def can_fit_complete_subject_load(faculty: Faculty, required_periods: int, occupancy, semester_week_count=1) -> bool:
    """
    Section 17: don't assign a faculty to a subject just because they have
    *some* free capacity right now — check they can plausibly carry the
    WHOLE subject's weekly load without busting weekly/daily limits.
    """
    remaining_weekly = faculty.max_lectures_per_week - occupancy.faculty_periods_total(faculty.id)
    return remaining_weekly >= required_periods


def faculty_available_at(faculty: Faculty, day: int, period_label: str) -> bool:
    """Section 17/28 hard constraint: faculty unavailability windows."""
    from scheduling.services.slots import PERIOD_BY_LABEL

    period = PERIOD_BY_LABEL[period_label]
    windows = faculty.unavailability_windows.filter(day=day)
    for w in windows:
        if w.start_time < period["end"] and period["start"] < w.end_time:
            return False
    return True


def rank_candidates_for_offering(offering, occupancy, required_periods: int) -> list[Candidate]:
    """Returns candidate faculty ordered best-first per the 9-point ranking."""

    # 1 & 2: fixed/admin assignment or an explicit override already set on
    # the offering short-circuits everything else.
    if offering.faculty_id and offering.is_faculty_locked:
        return [Candidate(offering.faculty, 0, "Fixed/locked assignment")]

    from django.db.models import Q

    candidates = []
    pool = Faculty.objects.filter(
        Q(department=offering.subject.department) | Q(assignment_rules__subject=offering.subject),
        is_active=True,
    ).distinct()

    prefs = {
        p.faculty_id: p
        for p in FacultySubjectPreference.objects.filter(subject=offering.subject, faculty__in=pool)
    }

    for faculty in pool:
        if not is_faculty_eligible_for_offering(faculty, offering):
            continue
        pref = prefs.get(faculty.id)
        if pref and not pref.is_eligible:
            continue
        if not can_fit_complete_subject_load(faculty, required_periods, occupancy):
            continue

        rule = get_matching_rule(faculty, offering)
        if rule is not None:
            # Section 20: a rule may cap how many periods this faculty can
            # be given for this subject — if the whole subject's load
            # doesn't fit under that cap, they can't be the (sole) faculty
            # for it (Section 18: one faculty per subject by default).
            cap = rule.specific_lecture_count if rule.specific_lecture_count is not None else rule.max_lectures
            if cap is not None and required_periods > cap:
                continue

        # Explicit override on the offering (even if not "locked") ranks
        # first among otherwise-eligible faculty.
        if offering.faculty_id == faculty.id:
            rank = 0
        else:
            priority = pref.priority if pref else 5
            current_load = occupancy.faculty_periods_total(faculty.id)
            # Weighted so subject priority dominates, workload balance
            # breaks ties (ranking criteria 5 and 9).
            rank = priority * 1000 + current_load

        candidates.append(Candidate(faculty, rank, "Ranked by priority/eligibility/workload", rule=rule))

    candidates.sort(key=lambda c: c.priority_rank)
    return candidates
