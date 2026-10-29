"""KG-01 §7 §19: shared test tooling. CI property tests are reproducible (NFR-06)."""

import re
from pathlib import Path

import pytest
from hypothesis import settings


def test_KG_01_hypothesis_ci_profile_is_derandomized() -> None:
    ci = settings.get_profile("ci")
    assert ci.derandomize is True
    assert ci.database is None  # no local example DB leaking state between CI runs


ROOT = Path(__file__).resolve().parents[2]
PY_SERVICES = ["services/agent", "services/supervisor"]  # mcp-adapter's image is Om's (OM-06)


@pytest.mark.parametrize("service", PY_SERVICES)
def test_KG_01_dockerfiles_pinned(service: str) -> None:
    # infra/CLAUDE.md: multi-arch images only, pinned tags, never :latest.
    text = (ROOT / service / "Dockerfile").read_text()
    stages = set(re.findall(r"^\s*FROM\s+\S+\s+AS\s+(\S+)", text, flags=re.MULTILINE | re.IGNORECASE))
    refs = re.findall(r"^\s*(?:FROM|COPY --from=)\s*(\S+)", text, flags=re.MULTILINE | re.IGNORECASE)
    images = [r for r in refs if r not in stages]  # `COPY --from=builder` names a stage, not an image
    assert images, f"{service}/Dockerfile has no base image"
    for image in images:
        _, _, tag = image.partition(":")
        assert tag and tag != "latest" and re.search(r"\d", tag), f"{service}: pin {image} to a versioned tag"
    assert "--frozen" in text, f"{service}: install from uv.lock (uv sync --frozen)"


@pytest.mark.parametrize("service", PY_SERVICES)
def test_KG_01_unprivileged_images_exclude_privileged_source(service: str) -> None:
    # Golden rule 4: only the factory/evaluation pyproject.toml (workspace metadata) may enter the image.
    text = (ROOT / service / "Dockerfile").read_text()
    for line in re.findall(r"^\s*COPY\s+(?!--from)(.+)$", text, flags=re.MULTILINE | re.IGNORECASE):
        for src in line.split()[:-1]:
            if src.startswith(("packages/scenario-factory", "packages/evaluation")):
                assert src.endswith("/pyproject.toml"), f"{service}: {src} would ship privileged code"
            assert src not in {".", "./", "packages", "packages/"}, f"{service}: COPY {src} is too broad"


@pytest.mark.parametrize("service", PY_SERVICES)
def test_KG_01_runtime_stage_ships_only_the_venv(service: str) -> None:
    # Deleting files in a later layer doesn't remove them from the image: the runtime stage must start clean
    # and copy only the built venv, so no uv binary, workspace source or privileged metadata ships.
    text = (ROOT / service / "Dockerfile").read_text()
    stages = re.split(r"^FROM\s", text, flags=re.MULTILINE | re.IGNORECASE)[1:]
    assert len(stages) >= 2, f"{service}: use a builder stage + a runtime stage"
    runtime = stages[-1]
    copies = re.findall(r"^\s*COPY\s+(.+)$", runtime, flags=re.MULTILINE | re.IGNORECASE)
    assert copies, f"{service}: runtime stage copies nothing"
    for c in copies:
        assert re.match(r"--from=builder\s+/app/\.venv\s+/app/\.venv$", c.replace("--chown=app:app ", "")), (
            f"{service}: runtime stage may only COPY --from=builder /app/.venv, got: COPY {c}"
        )
