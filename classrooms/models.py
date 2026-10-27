from django.db import models

from common.constants import Day, RoomType
from common.models import TimeStampedModel


class Classroom(TimeStampedModel):
    college = models.ForeignKey("academics.College", on_delete=models.CASCADE, related_name="classrooms")
    department = models.ForeignKey(
        "academics.Department",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="classrooms",
        help_text="Null means shared/common room, not owned by one department.",
    )
    room_number = models.CharField(max_length=20)
    building = models.CharField(max_length=100, blank=True)
    room_type = models.CharField(max_length=10, choices=RoomType.choices, default=RoomType.CLASSROOM)
    capacity = models.PositiveIntegerField(default=60)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["college", "room_number"], name="uniq_room_number_per_college"),
        ]
        indexes = [models.Index(fields=["room_type"])]
        ordering = ["building", "room_number"]

    def __str__(self):
        return f"{self.room_number} ({self.get_room_type_display()})"

    @property
    def is_lab(self):
        return self.room_type == RoomType.LAB


class RoomAvailability(TimeStampedModel):
    """Recurring weekly unavailability window for a room (maintenance,
    reserved for another institutional use, etc). The generator must treat
    these slots as occupied."""

    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name="unavailability_windows")
    day = models.IntegerField(choices=Day.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["classroom_id", "day", "start_time"]

    def __str__(self):
        return f"{self.classroom} unavailable {self.get_day_display()} {self.start_time}-{self.end_time}"


class RoomBooking(TimeStampedModel):
    """Pre-booked / one-off room reservation (Section 32): presentations,
    department events, institutional requirements, etc. The generator must
    preserve these and never double-book over them."""

    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name="bookings")
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    reason = models.CharField(max_length=255)
    booked_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="room_bookings"
    )

    class Meta:
        indexes = [models.Index(fields=["classroom", "date"])]
        ordering = ["date", "start_time"]

    def __str__(self):
        return f"{self.classroom} on {self.date} {self.start_time}-{self.end_time}: {self.reason}"
