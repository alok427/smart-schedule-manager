"""
Generates college_timetable_excel_template.xlsx (Sections 50-53, 55):
three sheets (Faculty, Subject, Classroom) with the required headers,
light styling, a sample row, and an Instructions sheet. This is the file
served from the "Download Excel Template" button on the import page.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)


def _style_header(ws, ncols):
    for col in range(1, ncols + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.freeze_panes = "A2"


def _autosize(ws, ncols, width=20):
    for col in range(1, ncols + 1):
        ws.column_dimensions[get_column_letter(col)].width = width


class Command(BaseCommand):
    help = "Generate college_timetable_excel_template.xlsx with Faculty/Subject/Classroom sheets."

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            default=str(Path(settings.MEDIA_ROOT) / "templates" / "college_timetable_excel_template.xlsx"),
            help="Output path for the generated template.",
        )

    def handle(self, *args, **options):
        out_path = Path(options["out"])
        out_path.parent.mkdir(parents=True, exist_ok=True)

        wb = Workbook()

        # --- Instructions ---------------------------------------------------
        ws0 = wb.active
        ws0.title = "Instructions"
        ws0["A1"] = "Smart Schedule Manager — Excel Import Template"
        ws0["A1"].font = Font(bold=True, size=14)
        instructions = [
            "",
            "Fill in the Faculty, Subject and Classroom sheets below. Do not rename sheets or headers.",
            "Required sheets: Faculty, Subject, Classroom. All three must be present.",
            "Accepted file types on import: .xlsx, .xlsm",
            "",
            "Faculty sheet:",
            "  faculty_name, email, username, designation, short_code, max_lecture_per_day, max_lecture_per_week",
            "  If 'username' is left blank, it is derived from the email's local part where safe.",
            "",
            "Subject sheet:",
            "  sr.no, course type, subject code, subject name, lecture, tutorial, practical, credits",
            "",
            "Classroom sheet:",
            "  sr.no, branch name and section, classroom number, building name",
            "  (capacity, room type, lab/normal, core/additional, department mapping, section mapping are optional extra columns)",
            "",
            "Import is transactional: if required data is invalid, nothing from the affected sheet is imported.",
            "You will get a summary after import: rows imported, warnings and errors, per sheet.",
        ]
        for i, line in enumerate(instructions, start=2):
            ws0.cell(row=i, column=1, value=line)
        ws0.column_dimensions["A"].width = 110

        # --- Faculty ----------------------------------------------------------
        ws1 = wb.create_sheet("Faculty")
        faculty_headers = [
            "faculty_name", "email", "username", "designation",
            "short_code", "max_lecture_per_day", "max_lecture_per_week",
        ]
        ws1.append(faculty_headers)
        ws1.append(["Dr. Asha Rao", "asha.rao@college.edu", "", "Assistant Professor", "ARO", 6, 24])
        _style_header(ws1, len(faculty_headers))
        _autosize(ws1, len(faculty_headers))

        # --- Subject ------------------------------------------------------
        ws2 = wb.create_sheet("Subject")
        subject_headers = [
            "sr.no", "course type", "subject code", "subject name",
            "lecture", "tutorial", "practical", "credits",
        ]
        ws2.append(subject_headers)
        ws2.append([1, "CORE", "CS301", "Database Management Systems", 3, 0, 2, 4.5])
        _style_header(ws2, len(subject_headers))
        _autosize(ws2, len(subject_headers))

        # --- Classroom ------------------------------------------------------
        ws3 = wb.create_sheet("Classroom")
        classroom_headers = ["sr.no", "branch name and section", "classroom number", "building name"]
        ws3.append(classroom_headers)
        ws3.append([1, "CSE - A", "CR-201", "Main Block"])
        _style_header(ws3, len(classroom_headers))
        _autosize(ws3, len(classroom_headers))

        wb.save(out_path)
        self.stdout.write(self.style.SUCCESS(f"Template written to {out_path}"))
