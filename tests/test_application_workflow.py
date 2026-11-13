import pytest

from app.models.enums import ApplicationStatus as Status
from app.services.application_workflow import can_transition


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (Status.APPLIED, Status.SCREENING),
        (Status.SCREENING, Status.INTERVIEW),
        (Status.INTERVIEW, Status.OFFER),
        (Status.OFFER, Status.HIRED),
        (Status.APPLIED, Status.REJECTED),
        (Status.INTERVIEW, Status.WITHDRAWN),
    ],
)
def test_allowed_transitions(current: Status, target: Status) -> None:
    assert can_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (Status.APPLIED, Status.INTERVIEW),
        (Status.APPLIED, Status.HIRED),
        (Status.OFFER, Status.SCREENING),
        (Status.HIRED, Status.APPLIED),
        (Status.REJECTED, Status.SCREENING),
        (Status.WITHDRAWN, Status.APPLIED),
    ],
)
def test_blocked_transitions(current: Status, target: Status) -> None:
    assert not can_transition(current, target)


@pytest.mark.parametrize("final", [Status.HIRED, Status.REJECTED, Status.WITHDRAWN])
def test_final_states_have_no_way_out(final: Status) -> None:
    assert not any(can_transition(final, target) for target in Status)
