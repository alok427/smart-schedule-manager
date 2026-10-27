"""
Helpers built on top of common.constants.TIME_SLOTS / LAB_PAIRS (Sections
11 and 13). Centralising this here means the generator, validators and
exports all agree on exactly what a "period" is.
"""

from datetime import datetime

from common.constants import LAB_PAIRS, TIME_SLOTS


def _parse(t):
    return datetime.strptime(t, "%H:%M").time()


# Ordered list of real (non-break) periods: [{label, start, end, order}, ...]
PERIODS = [
    {"label": label, "start": _parse(start), "end": _parse(end), "order": i}
    for i, (start, end, is_break, label) in enumerate(TIME_SLOTS)
    if not is_break
]
PERIOD_BY_LABEL = {p["label"]: p for p in PERIODS}
PERIOD_LABELS_IN_ORDER = [p["label"] for p in PERIODS]

# The lunch break start time — used to decide whether a period is "before
# lunch" for the Section 16 soft constraint (core subjects before lunch).
_LUNCH_START = next(_parse(start) for (start, end, is_break, label) in TIME_SLOTS if is_break and "LUNCH" in label)

LAB_PAIR_LABELS = LAB_PAIRS  # [("P1", "P2"), ("P3", "P4"), ...]


def is_before_lunch(period_label):
    return PERIOD_BY_LABEL[period_label]["start"] < _LUNCH_START


def periods_for_pair(pair):
    """Given ('P1', 'P2'), return the two period dicts in order."""
    return [PERIOD_BY_LABEL[pair[0]], PERIOD_BY_LABEL[pair[1]]]
