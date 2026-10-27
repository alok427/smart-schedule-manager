"""
Section 39: ONE central validation mechanism. The generator uses it while
placing sessions; manual editing, faculty swaps, room changes and restore
endpoints must call into the same functions rather than re-implementing
conflict checks.
"""

from dataclasses import dataclass, field

from scheduling.services.eligibility import faculty_available_at
from scheduling.services.slots import is_before_lunch  # noqa: F401 (re-exported for callers)


@dataclass
class ValidationResult:
    violations: list = field(default_factory=list)

    @property
    def is_valid(self):
        return not self.violations


def validate_placement(occupancy, *, day, period_labels, section_id, batch_id=None,
                        faculty=None, classroom=None) -> ValidationResult:
    """
    Hard-constraint check for placing something into `period_labels` on
    `day`. Pass real Faculty/Classroom model instances (not just ids) so
    availability windows and capacity limits can be checked too.
    """
    violations = []

    for label in period_labels:
        if not occupancy.section_free(section_id, batch_id, day, label):
            violations.append(f"Section clash: this class/section already has something at {label} on this day.")
        if faculty is not None and not occupancy.faculty_free(faculty.id, day, label):
            violations.append(f"Faculty clash: {faculty} is already teaching at {label} on this day.")
        if classroom is not None and not occupancy.classroom_free(classroom.id, day, label):
            violations.append(f"Room clash: {classroom} is already booked at {label} on this day.")

    if faculty is not None:
        for label in period_labels:
            if not faculty_available_at(faculty, day, label):
                violations.append(f"Faculty unavailability: {faculty} is marked unavailable at {label} on this day.")

        n = len(period_labels)
        if occupancy.faculty_periods_on_day(faculty.id, day) + n > faculty.max_lectures_per_day:
            violations.append(
                f"Daily limit exceeded: {faculty} would exceed max {faculty.max_lectures_per_day} lectures/day."
            )
        if occupancy.faculty_periods_total(faculty.id) + n > faculty.max_lectures_per_week:
            violations.append(
                f"Weekly limit exceeded: {faculty} would exceed max {faculty.max_lectures_per_week} lectures/week."
            )

    if classroom is not None:
        if not classroom.is_active:
            violations.append(f"Room inactive: {classroom} is not currently active.")

    return ValidationResult(violations=violations)


def validate_generation_completeness(generation) -> ValidationResult:
    """Final validation pass (Section 37 step 21/23): every required
    session must actually be scheduled, and no ERROR-severity issues may
    remain — otherwise this generation must never become Current."""
    from scheduling.models import GenerationIssue, TimetableSession

    violations = []
    unscheduled = TimetableSession.objects.filter(generation=generation, is_scheduled=False)
    for s in unscheduled.select_related("subject_offering__subject", "subject_offering__section")[:200]:
        violations.append(
            f"{s.subject_offering.subject.code} ({s.subject_offering.section}) — "
            f"{s.get_session_type_display()} session #{s.sequence_number} was not scheduled."
        )

    error_issues = GenerationIssue.objects.filter(generation=generation, severity="ERROR")
    for issue in error_issues:
        violations.append(issue.message)

    return ValidationResult(violations=violations)
