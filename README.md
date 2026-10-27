# Smart Schedule Manager

A college timetable management system: academic data, faculty & classroom
configuration, a constraint-based generation engine, versioned history with
restore, manual editing (click *and* drag-and-drop), bulk admin operations,
Excel import, PDF/Excel/iCal export, notifications, and role-based portals —
Django + DRF + PostgreSQL + JWT + Bootstrap 5, containerized for deployment.

## Project status

**84 automated tests pass against a live PostgreSQL database**
(`python manage.py test`). The full user-facing flow has additionally been
walked through by hand with real data repeatedly across this build.

### This round's additions
- **`FacultyAssignmentRule` UI** (`/faculty-admin/`) — create rules scoped
  to a subject, category, or whole department, with an optional lecture
  cap and an optional fixed day+slot. Backed by a new
  `/api/faculty-assignment-rules/` CRUD endpoint.
- **Real drag-and-drop** on the Manage Timetable grid — drag any
  non-fixed cell to a new slot. A lab (2-period) session must be dropped
  on the first period of a valid pair (P1/P3/P5/P7); dropping mid-pair is
  rejected client-side with a clear message, and independently rejected
  server-side too (verified: the backend returns 409 with "needs 2
  period(s); 1 were given" even if the frontend check were bypassed).
  Click-to-select is still there for precise moves and room changes.
- **Bulk operations** on the Faculty, Subjects, and Classrooms admin
  pages — select multiple rows, then Activate / Deactivate / Delete in
  one action.
- **40 new automated tests** for the CRUD endpoints that previously only
  had manual verification: academics (Section/Subject, 8 tests), faculty
  (Faculty + FacultyAssignmentRule, 8 tests), classrooms (5 tests),
  academic_calendar (8 tests).

### Real bugs/gaps found and fixed while writing those new tests
- **`Subject.practical_hours` evenness was only checked by the model's
  `clean()` (never auto-called) and the frontend form** — a direct API
  call could create a subject with odd practical hours. Added
  `validate_practical_hours` to the serializer; API now rejects it (400)
  the same way the UI does.
- **`AcademicCalendarViewSet` had no department scoping at all** — any
  Dept Admin could read, edit, or delete *any* department's calendar
  (or the college-wide one), not just their own. Fixed: reads are now
  scoped to college-wide + own department, writes are scoped the same
  way, and creating a calendar always forces the department to the
  caller's own.
- One of my own new tests initially asserted the wrong status code
  (expected 403, got 404) for a Dept Admin trying to edit another
  department's faculty record — investigated rather than assumed a bug,
  and confirmed the 404 is correct, deliberate behavior:
  `DepartmentScopedQuerysetMixin` filters the queryset *before* the
  object lookup, so the response doesn't even reveal the record exists
  outside the requester's department. Fixed the test's expectation, not
  the code.

### On Docker verification
I installed Docker and started the daemon directly in this build
sandbox — it genuinely works (`docker build` runs, sends the build
context, starts resolving the base image). The actual base-image pull
(`python:3.12-slim` from Docker Hub) fails here because this sandbox's
network egress is allow-listed to a specific set of domains (PyPI, npm,
GitHub, Ubuntu's package archives, etc.) and `registry-1.docker.io` isn't
on it — a sandbox restriction, not a problem with the Dockerfile. So:
Docker itself is confirmed working, but a full `docker build`/
`docker compose up` still can't be run end-to-end here. Every piece it
depends on (gunicorn serving the app, WhiteNoise serving static files,
migrations, the entrypoint script) has been verified individually and
directly instead.

### On the generator algorithm
It's a **greedy constraint-satisfaction placer, not backtracking.**
Sessions are ordered once (labs/high-constraint first, then core, then
extras, with seeded RNG for deterministic tie-breaking); for each session
in that fixed order it commits the first faculty+day+period+room
combination that satisfies every hard constraint, and never revisits or
undoes an earlier placement to make room for a later one that failed.
True backtracking (unwind and retry earlier choices when a later one has
no valid placement) would sometimes succeed where this reports a session
as unplaceable, at real cost in complexity and worst-case runtime — it
hasn't been implemented.

### Real bugs found and fixed across this whole build (cumulative)
- Whole-section vs. batch-lab double-booking in the occupancy model
- `FacultyAssignmentRule`'s fields existing on the model but never being
  read by the generator (now enforced, Section 20/21)
- No test proving cross-section global conflict management (Section 9)
- Mobile sidebar had no way to open at all (rebuilt on Bootstrap's
  `offcanvas-lg`)
- Stored XSS in three admin tables built with unescaped `innerHTML`
- No brute-force protection on login (added throttling; also discovered
  and worked around a real DRF quirk where `override_settings` doesn't
  reliably change throttle rates, since they're bound at import time)
- `Subject.practical_hours` API-level validation gap (this round)
- `AcademicCalendarViewSet` missing department scoping entirely (this
  round)

### Backend
- 13 Django apps, 35+ migrated PostgreSQL tables
- Custom User model, JWT auth, role/department-scoped permissions enforced
  server-side
- **Generation engine** (`scheduling/services/`): fixed-lecture reservation,
  session building, batch-aware lab scheduling, faculty eligibility/ranking
  incl. `FacultyAssignmentRule` enforcement, global cross-section occupancy
  tracking, hard-constraint enforcement, soft "core-before-lunch" placement,
  one central validation service reused by generation and manual edits
- Versioning: Current/Historical per (section, semester); restore that only
  flips a pointer, never regenerates
- Manual editing: move session (click or drag), change classroom, change
  faculty — all through the same central validation service
- Full CRUD APIs, department-scoped: Faculty, FacultyAssignmentRule,
  Subjects, Sections, Classrooms, Academic Calendar, Fixed Lectures, Users
- Excel import (transactional), PDF/Excel/iCal export, a genuine **Print**
  view, notifications, dashboard stats + search, rate limiting
- Management commands: `bootstrap_superadmin`, `seed_demo_data`,
  `create_excel_template`

### Frontend — Bootstrap 5
Every page uses real Bootstrap components (cards, forms, tables, badges,
alerts, list-groups, offcanvas), themed with a navy/brass palette and
Fraunces/Inter type via Bootstrap's CSS variable theming API. No React —
vanilla JS talking to the real JSON API via a shared `SSM.request()`
helper.

| Page | Who | Highlights |
|---|---|---|
| `/login/` | everyone | |
| `/dashboard/` | Super/Dept Admin | stats, search, conflicts |
| `/manage-timetable/` | Super/Dept Admin | generate, real tabular grid, **drag-and-drop or click to move/re-room a cell**, history/restore, faculty reassignment, Print |
| `/faculty-admin/` | Super/Dept Admin | faculty CRUD + bulk ops, **assignment rules** |
| `/subjects/` | Super/Dept Admin | subject CRUD + bulk ops |
| `/classrooms/` | Super/Dept Admin | room/lab CRUD + bulk ops |
| `/academic-calendar/` | Super/Dept Admin | working days & holidays |
| `/fixed-lectures/` | Super/Dept Admin | lock a faculty/slot/room |
| `/excel-import/` | Super/Dept Admin | template download + upload |
| `/notifications/` | everyone | |
| `/faculty/` | Faculty | weekly grid, today, workload, Print |
| `/student/` | Student | section's weekly grid, today, Print |

### What's still genuinely open
- `docker compose up` unverified end-to-end (see above — environment
  restriction, not a code issue)
- No multi-day/multi-entry bulk operations on the timetable itself (bulk
  ops exist for Faculty/Subjects/Classrooms, not for timetable entries)
- No UI for `RoomAvailability`/`RoomBooking`/`FacultySubjectPreference`/
  `FacultyPreference`/`FacultyProfile` — models and admin-site access
  exist; no dedicated frontend page

## Setup (local, without Docker)

```bash
# 1. Database
sudo -u postgres psql -c "CREATE USER ssm_user WITH PASSWORD 'yourpassword';"
sudo -u postgres psql -c "CREATE DATABASE smart_schedule_manager OWNER ssm_user;"

# 2. Environment
cp .env.example .env   # edit SECRET_KEY, DB_PASSWORD, etc.

# 3. Install & migrate
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate

# 4. Admin account
python manage.py bootstrap_superadmin --username admin --email admin@yourcollege.edu --password 'ChangeMe123!'

# 5. (Optional) demo data
python manage.py seed_demo_data

# 6. Test suite
python manage.py test accounts scheduling data_import data_export dashboard notifications academics faculty classrooms academic_calendar

# 7. Run
python manage.py runserver
```
App: `http://localhost:8000/` · Admin: `/admin/` · API: `/api/`

`seed_demo_data` creates a college, 2 departments, a section with lab
batches, faculty, rooms, subjects, and 3 demo accounts — `dept_admin_cse`,
`faculty_arao` (linked to a real Faculty record), `student_demo` (linked to
the seeded section) — password `Demo@12345` for all three.

## Setup (Docker)

```bash
cp .env.example .env   # edit SECRET_KEY, DB_PASSWORD, etc.
docker compose up --build
```
See "On Docker verification" above for the honest caveat on this.

## API surface

```
POST   /api/accounts/auth/login/ | /refresh/ | GET /auth/me/ | POST /auth/change-password/
/api/accounts/users/

/api/academics/{academic-years,departments,years,semesters,sections,subjects,subject-offerings}/
GET    /api/academics/student/me/timetable/
/api/faculty/  ·  /api/faculty-assignment-rules/  ·  GET /api/faculty/me/timetable/
/api/classrooms/
/api/academic-calendar/{calendars,working-days,holidays,special-working-days,events}/

POST   /api/scheduling/generate/
GET    /api/scheduling/generations/<id>/
GET    /api/scheduling/timetable/?section=&semester=
GET    /api/scheduling/history/?section=&semester=
POST   /api/scheduling/versions/<id>/restore/
POST   /api/scheduling/edit/{move-session,change-classroom,change-faculty}/
/api/scheduling/fixed-lectures/

GET    /api/data-import/template/  ·  POST /api/data-import/import/  ·  GET /api/data-import/batches/
GET    /api/data-export/{pdf,excel,ical}/?section=&semester=
GET    /api/dashboard/stats/  ·  /search/?q=
GET    /api/notifications/mine/  ·  POST /api/notifications/<id>/read/  ·  POST /api/notifications/mark-all-read/
```

## Project layout

```
config/                 settings, root urls (API + page routes)
common/                 shared constants, abstract base models (not a Django app)
templates/, static/     Django templates + Bootstrap 5 theme + vanilla JS frontend
Dockerfile, docker-compose.yml, entrypoint.sh, .github/workflows/ci.yml
accounts/                users, roles, JWT, permissions, login throttling
academics/               college/year/department/section/subject/offering + CRUD API
    tests/                  Section/Subject CRUD, department scoping, API-level validation
faculty/                 faculty, availability, preferences, assignment rules, load
    tests/                  Faculty + FacultyAssignmentRule CRUD
classrooms/               rooms/labs, availability, bookings
    tests/                  Classroom CRUD, server-derived college field
academic_calendar/       calendar, holidays, working days, events
    tests/                  Calendar/WorkingDay/Holiday CRUD, department scoping
activities/               activities, coordinator/additional load
scheduling/               generation engine, versions, fixed lectures, manual edits
    services/               slots · occupancy · eligibility (incl. rule enforcement)
                            session_builder · fixed_resources · rooms · validation
                            generator · versioning · manual_edit
    tests/                  generator, versioning, manual-edit, assignment-rule,
                            global-occupancy tests
notifications/            single Notification model + service + API
data_import/               real Excel parsing + ImportBatch history
data_export/                real PDF/Excel/iCal generation
dashboard/                  stats + global search
```

## Design notes worth knowing

- **"Current" is per (section, semester)**, not per generation run.
- **Restore never regenerates.**
- **Central validation** is reused by the generator, manual edits, and
  both the drag-and-drop and click-to-select frontend paths.
- **Occupancy is batch-aware and global across sections.**
- **Never trust user-editable text into `innerHTML`.**
- **Never trust a client-supplied value for an authorization-relevant
  field** (`college` on Classroom, `department` on generated users/rooms/
  calendars) — always re-derive it server-side from something the
  request is actually authorized for.
