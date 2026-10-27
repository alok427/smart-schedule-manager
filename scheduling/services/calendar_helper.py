from academic_calendar.models import AcademicCalendar
from common.constants import Day


def working_days_for(academic_year, department=None):
    """
    Returns a sorted list of Day ints that are working days, per the
    department's calendar if one exists, else the college-wide calendar,
    else a safe default (Mon-Sat) so generation never silently stalls for
    lack of calendar configuration.
    """
    calendar = None
    if department is not None:
        calendar = AcademicCalendar.objects.filter(academic_year=academic_year, department=department).first()
    if calendar is None:
        calendar = AcademicCalendar.objects.filter(academic_year=academic_year, department=None).first()

    if calendar is None:
        return [d.value for d in Day]

    working = list(calendar.working_days.filter(is_working=True).values_list("day", flat=True))
    if not working:
        return [d.value for d in Day]
    return sorted(working)
