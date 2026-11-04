"""Typed contract for the Kubernetes routing example."""

from kubernetes_routing.contract import Observation, inspect_stack
from kubernetes_routing.domain import ContractViolation, StackContract
from kubernetes_routing.manifest import load_stack

__all__ = ["ContractViolation", "Observation", "StackContract", "inspect_stack", "load_stack"]
