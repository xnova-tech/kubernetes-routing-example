"""Deterministic observations for the article and CI."""

from dataclasses import dataclass, replace
from pathlib import Path

from kubernetes_routing.domain import ContractViolation, LabelSelector
from kubernetes_routing.manifest import load_stack


@dataclass(frozen=True)
class Observation:
    name: str
    value: str

    def render(self) -> str:
        return f"{self.name}: {self.value}"


def inspect_stack(path: Path) -> tuple[Observation, ...]:
    stack = load_stack(path)
    stack.validate()

    mismatched = replace(
        stack,
        service=replace(stack.service, selector=LabelSelector({"app": "missing"})),
    )
    try:
        mismatched.validate()
    except ContractViolation as error:
        if "Service selector" not in str(error):
            raise
    else:
        raise AssertionError("negative selector control was not rejected")

    return (
        Observation("resources", "Deployment, Service, Ingress"),
        Observation("namespace", stack.deployment.namespace),
        Observation("deployment", f"replicas={stack.deployment.replicas} image_digest=pinned"),
        Observation("selector", stack.service.selector.render()),
        Observation(
            "route",
            (
                f"{stack.ingress.path} -> {stack.service.name}:{stack.service.port.name}"
                f" -> {stack.deployment.container_port.name}:{stack.deployment.container_port.number}"
            ),
        ),
        Observation("negative_control", "mismatched Service selector rejected"),
    )
