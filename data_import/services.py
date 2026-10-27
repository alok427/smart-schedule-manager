"""
Section 54: Excel import. Whole-file transactional — if any REQUIRED sheet
has a critical error, nothing from the file is committed. Warnings (e.g. a
row that's fine but slightly odd) don't block the import; hard errors
(missing required value, wrong type, duplicate within the file) do.
"""

import re
from dataclasses import dataclass, field

from django.db import transaction
from openpyxl import load_workbook

from academics.models import Department, Subject, Year
from classrooms.models import Classroom
from common.constants import RoomType, SubjectCategory
from faculty.models import Faculty

REQUIRED_SHEETS = ["Faculty", "Subject", "Classroom"]

FACULTY_HEADERS = ["faculty_name", "email", "username", "designation", "short_code",
                   "max_lecture_per_day", "max_lecture_per_week"]
SUBJECT_HEADERS = ["sr.no", "course type", "subject code", "subject name",
                    "lecture", "tutorial", "practical", "credits"]
CLASSROOM_HEADERS = ["sr.no", "branch name and section", "classroom number", "building name"]

ALLOWED_EXTENSIONS = (".xlsx", ".xlsm")


@dataclass
class ImportOutcome:
    faculty_imported: int = 0
    subjects_imported: int = 0
    classrooms_imported: int = 0
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    @property
    def status(self):
        if self.errors:
            return "FAILED"
        if self.warnings:
            return "PARTIAL"
        return "SUCCESS"


class ImportRejected(Exception):
    """Raised internally to trigger a full rollback of the import transaction."""


def _normalize_header(value):
    return (str(value).strip().lower() if value is not None else "")


def _read_sheet_rows(ws, expected_headers):
    header_row = [_normalize_header(c.value) for c in next(ws.iter_rows(min_row=1, max_row=1))]
    missing = [h for h in expected_headers if h not in header_row]
    if missing:
        return None, missing
    col_index = {h: header_row.index(h) for h in expected_headers}
    rows = []
    for row in ws.iter_rows(min_row=2):
        values = [c.value for c in row]
        if all(v in (None, "") for v in values):
            continue
        rows.append({h: values[idx] if idx < len(values) else None for h, idx in col_index.items()})
    return rows, []


def _derive_username(email):
    local = email.split("@")[0]
    return re.sub(r"[^a-zA-Z0-9_.\-]", "", local).lower()


def validate_file(uploaded_file):
    name = uploaded_file.name.lower()
    if not name.endswith(ALLOWED_EXTENSIONS):
        raise ImportRejected(f"Unsupported file type '{name}'. Only .xlsx and .xlsm are accepted.")


@transaction.atomic
def run_import(uploaded_file, *, department: Department, year: Year | None, uploaded_by) -> ImportOutcome:
    from data_import.models import ImportBatch

    outcome = ImportOutcome()
    sp = transaction.savepoint()

    try:
        validate_file(uploaded_file)
        wb = load_workbook(uploaded_file, data_only=True, read_only=True)

        missing_sheets = [s for s in REQUIRED_SHEETS if s not in wb.sheetnames]
        if missing_sheets:
            raise ImportRejected(f"Missing required sheet(s): {', '.join(missing_sheets)}.")

        _import_faculty(wb["Faculty"], department, outcome)
        _import_subjects(wb["Subject"], department, year, outcome)
        _import_classrooms(wb["Classroom"], department, outcome)

        if outcome.errors:
            raise ImportRejected("Critical errors found — see `errors` for details. Nothing was imported.")

    except ImportRejected as exc:
        transaction.savepoint_rollback(sp)
        if str(exc) not in outcome.errors:
            outcome.errors.insert(0, str(exc))
        outcome.faculty_imported = outcome.subjects_imported = outcome.classrooms_imported = 0
    else:
        transaction.savepoint_commit(sp)

    batch = ImportBatch.objects.create(
        uploaded_by=uploaded_by, department=department,
        original_filename=getattr(uploaded_file, "name", "upload.xlsx"),
        status=outcome.status,
        faculty_imported=outcome.faculty_imported, subjects_imported=outcome.subjects_imported,
        classrooms_imported=outcome.classrooms_imported,
        warning_count=len(outcome.warnings), error_count=len(outcome.errors),
        warnings=outcome.warnings, errors=outcome.errors,
    )
    return batch


def _import_faculty(ws, department, outcome: ImportOutcome):
    rows, missing_headers = _read_sheet_rows(ws, FACULTY_HEADERS)
    if missing_headers:
        outcome.errors.append(f"Faculty sheet is missing header(s): {', '.join(missing_headers)}.")
        return

    seen_emails, seen_codes = set(), set()
    count = 0
    for i, row in enumerate(rows, start=2):
        name = row["faculty_name"]
        email = row["email"]
        short_code = row["short_code"]

        if not name or not email or not short_code:
            outcome.errors.append(f"Faculty row {i}: faculty_name, email and short_code are all required.")
            continue
        email = str(email).strip().lower()
        short_code = str(short_code).strip().upper()

        if email in seen_emails or short_code in seen_codes:
            outcome.errors.append(f"Faculty row {i}: duplicate email/short_code within this file ({email}/{short_code}).")
            continue
        seen_emails.add(email)
        seen_codes.add(short_code)

        if Faculty.objects.filter(email=email).exclude(department=department).exists():
            outcome.errors.append(f"Faculty row {i}: email {email} already belongs to a faculty in another department.")
            continue

        username = row.get("username") or _derive_username(email)
        max_day = row.get("max_lecture_per_day") or 6
        max_week = row.get("max_lecture_per_week") or 24
        try:
            max_day, max_week = int(max_day), int(max_week)
        except (TypeError, ValueError):
            outcome.errors.append(f"Faculty row {i}: max_lecture_per_day/week must be numbers.")
            continue

        Faculty.objects.update_or_create(
            email=email,
            defaults=dict(
                department=department, name=str(name).strip(), short_code=short_code,
                designation=str(row.get("designation") or "").strip(),
                max_lectures_per_day=max_day, max_lectures_per_week=max_week,
            ),
        )
        count += 1
        if not row.get("username"):
            outcome.warnings.append(f"Faculty row {i}: username was blank, derived as '{username}'.")

    outcome.faculty_imported = count


def _import_subjects(ws, department, year, outcome: ImportOutcome):
    rows, missing_headers = _read_sheet_rows(ws, SUBJECT_HEADERS)
    if missing_headers:
        outcome.errors.append(f"Subject sheet is missing header(s): {', '.join(missing_headers)}.")
        return
    if year is None:
        outcome.errors.append("Subject import requires a target Year to be specified.")
        return

    seen_codes = set()
    count = 0
    for i, row in enumerate(rows, start=2):
        code = row["subject code"]
        name = row["subject name"]
        if not code or not name:
            outcome.errors.append(f"Subject row {i}: subject code and subject name are required.")
            continue
        code = str(code).strip().upper()
        if code in seen_codes:
            outcome.errors.append(f"Subject row {i}: duplicate subject code within this file ({code}).")
            continue
        seen_codes.add(code)

        try:
            lecture = int(row.get("lecture") or 0)
            tutorial = int(row.get("tutorial") or 0)
            practical = int(row.get("practical") or 0)
            credits = float(row.get("credits") or 0)
        except (TypeError, ValueError):
            outcome.errors.append(f"Subject row {i}: lecture/tutorial/practical/credits must be numeric.")
            continue
        if practical % 2 != 0:
            outcome.errors.append(f"Subject row {i}: practical hours ({practical}) must be even (2-period lab blocks).")
            continue

        course_type = str(row.get("course type") or "").strip().upper()
        category = SubjectCategory.EXTRA if course_type in ("EXTRA", "ADDITIONAL") else SubjectCategory.CORE

        Subject.objects.update_or_create(
            department=department, code=code,
            defaults=dict(
                year=year, name=str(name).strip(), lecture_hours=lecture, tutorial_hours=tutorial,
                practical_hours=practical, credits=credits, category=category,
            ),
        )
        count += 1

    outcome.subjects_imported = count


def _import_classrooms(ws, department, outcome: ImportOutcome):
    rows, missing_headers = _read_sheet_rows(ws, CLASSROOM_HEADERS)
    if missing_headers:
        outcome.errors.append(f"Classroom sheet is missing header(s): {', '.join(missing_headers)}.")
        return

    seen_numbers = set()
    count = 0
    for i, row in enumerate(rows, start=2):
        number = row["classroom number"]
        if not number:
            outcome.errors.append(f"Classroom row {i}: classroom number is required.")
            continue
        number = str(number).strip().upper()
        if number in seen_numbers:
            outcome.errors.append(f"Classroom row {i}: duplicate classroom number within this file ({number}).")
            continue
        seen_numbers.add(number)

        room_type = RoomType.LAB if "lab" in number.lower() else RoomType.CLASSROOM

        Classroom.objects.update_or_create(
            college=department.college, room_number=number,
            defaults=dict(
                department=department, building=str(row.get("building name") or "").strip(),
                room_type=room_type,
            ),
        )
        count += 1
        if not row.get("branch name and section"):
            outcome.warnings.append(f"Classroom row {i}: no branch/section association given for {number}.")

    outcome.classrooms_imported = count
