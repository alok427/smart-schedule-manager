"""
Section 56: PDF/Excel/iCal exports of a section's Current timetable. All
three build from the exact same query — one grid of {day: {period: entry}}
— so the three formats can never disagree with each other or with what
the API returns for on-screen viewing.
"""

import io
from datetime import datetime, timedelta

from common.constants import Day, TIME_SLOTS
from scheduling.models import TimetableEntry
from scheduling.services.slots import PERIOD_LABELS_IN_ORDER


def build_grid(version):
    """Returns (grid, subtitle_context). grid[day][period_label] = list of
    entries (a list because parallel lab batches share a slot)."""
    entries = (
        TimetableEntry.objects.filter(generation=version.generation, section=version.section)
        .select_related("session__subject_offering__subject", "faculty", "classroom", "batch")
        .order_by("day", "start_time")
    )
    grid = {d: {label: [] for label in PERIOD_LABELS_IN_ORDER} for d in range(6)}
    for e in entries:
        grid[e.day][e.period_label].append(e)
    return grid


def _cell_text(entries_in_cell):
    if not entries_in_cell:
        return ""
    lines = []
    for e in entries_in_cell:
        subject = e.session.subject_offering.subject
        parts = [subject.name, subject.code]
        if e.faculty:
            parts.append(e.faculty.short_code)
        if e.classroom:
            parts.append(e.classroom.room_number)
        if e.batch:
            parts.append(f"({e.batch.name})")
        lines.append(" / ".join(parts))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Excel export (openpyxl)
# --------------------------------------------------------------------------
def export_excel(version, *, college_name="", footer_text="") -> io.BytesIO:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Timetable"

    section = version.section
    header_lines = [
        college_name or "Timetable",
        f"{section.department.name} — {section} — Semester {version.semester.semester_number} "
        f"({version.semester.get_semester_type_display()})",
        f"Academic Year: {version.semester.academic_year.label}    Version: v{version.version_number}",
    ]
    for i, line in enumerate(header_lines, start=1):
        ws.cell(row=i, column=1, value=line).font = Font(bold=(i == 1), size=14 if i == 1 else 10)
    start_row = len(header_lines) + 2

    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)

    ws.cell(row=start_row, column=1, value="Day").fill = header_fill
    ws.cell(row=start_row, column=1).font = header_font
    for c, label in enumerate(PERIOD_LABELS_IN_ORDER, start=2):
        slot = next(s for s in TIME_SLOTS if s[3] == label)
        cell = ws.cell(row=start_row, column=c, value=f"{label}\n{slot[0]}-{slot[1]}")
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

    grid = build_grid(version)
    for r, day in enumerate(range(6), start=start_row + 1):
        ws.cell(row=r, column=1, value=Day(day).label).font = Font(bold=True)
        for c, label in enumerate(PERIOD_LABELS_IN_ORDER, start=2):
            text = _cell_text(grid[day][label])
            cell = ws.cell(row=r, column=c, value=text)
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    ws.column_dimensions["A"].width = 14
    for c in range(2, 2 + len(PERIOD_LABELS_IN_ORDER)):
        ws.column_dimensions[get_column_letter(c)].width = 22

    if footer_text:
        ws.cell(row=start_row + 8, column=1, value=footer_text)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# --------------------------------------------------------------------------
# PDF export (reportlab)
# --------------------------------------------------------------------------
def export_pdf(version, *, college_name="", footer_text="") -> io.BytesIO:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    section = version.section
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1 * cm, rightMargin=1 * cm,
                             topMargin=1 * cm, bottomMargin=1 * cm)

    elements = [
        Paragraph(college_name or "Timetable", styles["Title"]),
        Paragraph(
            f"{section.department.name} — {section} — Semester {version.semester.semester_number} "
            f"({version.semester.get_semester_type_display()}) — {version.semester.academic_year.label} "
            f"— v{version.version_number}",
            styles["Normal"],
        ),
        Spacer(1, 0.4 * cm),
    ]

    header_row = ["Day"] + [
        f"{label}\n{next(s for s in TIME_SLOTS if s[3] == label)[0]}-{next(s for s in TIME_SLOTS if s[3] == label)[1]}"
        for label in PERIOD_LABELS_IN_ORDER
    ]
    grid = build_grid(version)
    data = [header_row]
    for day in range(6):
        row = [Day(day).label]
        for label in PERIOD_LABELS_IN_ORDER:
            row.append(_cell_text(grid[day][label]))
        data.append(row)

    col_widths = [2.2 * cm] + [3.2 * cm] * len(PERIOD_LABELS_IN_ORDER)
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6FA")]),
    ]))
    elements.append(table)

    if footer_text:
        elements.append(Spacer(1, 1 * cm))
        elements.append(Paragraph(footer_text, styles["Normal"]))
    elements.append(Spacer(1, 1.5 * cm))
    elements.append(Paragraph("Signature (HOD): ______________________"
                               "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                               "Signature (Principal): ______________________", styles["Normal"]))

    doc.build(elements)
    buf.seek(0)
    return buf


# --------------------------------------------------------------------------
# iCal export (icalendar)
# --------------------------------------------------------------------------
def export_ical(version) -> io.BytesIO:
    from icalendar import Calendar, Event as ICalEvent

    cal = Calendar()
    cal.add("prodid", "-//Smart Schedule Manager//timetable//")
    cal.add("version", "2.0")

    semester = version.semester
    calendar_start = semester.start_date or semester.academic_year.start_date
    entries = (
        TimetableEntry.objects.filter(generation=version.generation, section=version.section)
        .select_related("session__subject_offering__subject", "faculty", "classroom")
    )

    # Find the Monday on/after calendar_start to anchor day-of-week -> date.
    anchor = calendar_start
    anchor += timedelta(days=(7 - anchor.weekday()) % 7) if anchor.weekday() != 0 else timedelta(0)

    for e in entries:
        event_date = anchor + timedelta(days=e.day)
        subject = e.session.subject_offering.subject
        ev = ICalEvent()
        ev.add("summary", f"{subject.code} {subject.name}")
        ev.add("dtstart", datetime.combine(event_date, e.start_time))
        ev.add("dtend", datetime.combine(event_date, e.end_time))
        ev.add("location", e.classroom.room_number if e.classroom else "")
        description = f"Faculty: {e.faculty.name if e.faculty else '-'}\nSection: {version.section}"
        ev.add("description", description)
        semester_end = semester.end_date or semester.academic_year.end_date
        if semester_end:
            ev.add("rrule", {"freq": "weekly", "until": semester_end})
        cal.add_component(ev)

    buf = io.BytesIO(cal.to_ical())
    buf.seek(0)
    return buf
