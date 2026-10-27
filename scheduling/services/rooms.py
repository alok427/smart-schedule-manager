"""
Classroom/lab selection (Sections 29-31). Fixed-classroom configuration on
a Section is honoured consistently; otherwise the generator picks any
free, suitably-typed, sufficiently-large room.
"""

from classrooms.models import Classroom
from common.constants import RoomType


def candidate_rooms(section, room_type, required_capacity):
    qs = Classroom.objects.filter(room_type=room_type, is_active=True, capacity__gte=required_capacity)

    ordered = list(qs)
    if room_type == RoomType.CLASSROOM and section.fixed_classroom_id:
        fixed = section.fixed_classroom
        if fixed in ordered:
            ordered.remove(fixed)
            ordered.insert(0, fixed)  # Section 31: prefer the section's fixed room first.
    # Soft preference: same-department rooms first.
    ordered.sort(key=lambda r: 0 if r.department_id == section.department_id else 1)
    return ordered


def find_free_room(rooms, occupancy, day, period_labels, exclude_ids=frozenset()):
    for room in rooms:
        if room.id in exclude_ids:
            continue
        if all(occupancy.classroom_free(room.id, day, label) for label in period_labels):
            return room
    return None
