from dataclasses import replace
from pathlib import Path

import pytest

from kubernetes_routing.domain import ContractViolation, LabelSelector
from kubernetes_routing.manifest import load_stack

STACK_FILE = Path(__file__).parents[1] / "stack.yaml"


def test_mismatched_service_selector_is_rejected() -> None:
    stack = load_stack(STACK_FILE)
    mismatched = replace(
        stack,
        service=replace(stack.service, selector=LabelSelector({"app": "missing"})),
    )

    with pytest.raises(ContractViolation, match="Service selector"):
        mismatched.validate()


def test_unpinned_container_image_is_rejected() -> None:
    stack = load_stack(STACK_FILE)
    unpinned = replace(
        stack,
        deployment=replace(stack.deployment, image="nginx:stable-alpine"),
    )

    with pytest.raises(ContractViolation, match="pinned by sha256"):
        unpinned.validate()
