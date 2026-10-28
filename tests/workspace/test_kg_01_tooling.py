"""KG-01 §7 §19: shared test tooling. CI property tests are reproducible (NFR-06)."""

from hypothesis import settings


def test_KG_01_hypothesis_ci_profile_is_derandomized() -> None:
    ci = settings.get_profile("ci")
    assert ci.derandomize is True
    assert ci.database is None  # no local example DB leaking state between CI runs
