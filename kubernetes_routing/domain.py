"""Domain model for the Kubernetes objects used by the example."""

import re
from collections.abc import Mapping
from dataclasses import dataclass

_PINNED_IMAGE = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")


class ContractViolation(ValueError):
    """Raised when the authored Kubernetes objects no longer form one route."""


@dataclass(frozen=True)
class LabelSelector:
    values: Mapping[str, str]

    def matches(self, labels: Mapping[str, str]) -> bool:
        return all(labels.get(key) == value for key, value in self.values.items())

    def render(self) -> str:
        return ",".join(f"{key}={value}" for key, value in sorted(self.values.items()))


@dataclass(frozen=True)
class ContainerPort:
    name: str
    number: int


@dataclass(frozen=True)
class ServicePort:
    name: str
    number: int
    target_name: str


@dataclass(frozen=True)
class ResourceIdentity:
    name: str
    namespace: str


@dataclass(frozen=True)
class DeploymentContract:
    namespace: str
    name: str
    replicas: int
    selector: LabelSelector
    pod_labels: Mapping[str, str]
    image: str
    container_port: ContainerPort


@dataclass(frozen=True)
class ServiceContract:
    namespace: str
    name: str
    service_type: str
    selector: LabelSelector
    port: ServicePort


@dataclass(frozen=True)
class IngressContract:
    namespace: str
    name: str
    class_name: str
    path: str
    path_type: str
    service_name: str
    service_port_name: str


@dataclass(frozen=True)
class StackContract:
    deployment: DeploymentContract
    service: ServiceContract
    ingress: IngressContract

    def validate(self) -> None:
        self._validate_identity()
        self._validate_deployment()
        self._validate_service_route()

    def _validate_identity(self) -> None:
        namespaces = {self.deployment.namespace, self.service.namespace, self.ingress.namespace}
        if namespaces != {"xnova-k8s-article"}:
            raise ContractViolation("all resources must use namespace xnova-k8s-article")
        if self.deployment.name != "xnova-web" or self.service.name != "xnova-web":
            raise ContractViolation("Deployment and Service must be named xnova-web")

    def _validate_deployment(self) -> None:
        if self.deployment.replicas != 2:
            raise ContractViolation("Deployment must request two replicas")
        if not self.deployment.selector.matches(self.deployment.pod_labels):
            raise ContractViolation("Deployment selector must match the Pod template labels")
        if not _PINNED_IMAGE.fullmatch(self.deployment.image):
            raise ContractViolation("container image must be pinned by sha256 digest")
        if self.deployment.container_port != ContainerPort(name="http", number=80):
            raise ContractViolation("container must expose the named port http:80")

    def _validate_service_route(self) -> None:
        if not self.service.selector.matches(self.deployment.pod_labels):
            raise ContractViolation("Service selector must match the Pod template labels")
        if self.service.service_type != "ClusterIP":
            raise ContractViolation("Service must remain ClusterIP")
        if self.service.port != ServicePort(name="http", number=80, target_name="http"):
            raise ContractViolation("Service must map http:80 to the named targetPort http")
        if self.ingress.class_name != "traefik":
            raise ContractViolation("Ingress must target the traefik class")
        if self.ingress.path != "/" or self.ingress.path_type != "Prefix":
            raise ContractViolation("Ingress must route the / prefix")
        if self.ingress.service_name != self.service.name:
            raise ContractViolation("Ingress backend must reference Service xnova-web")
        if self.ingress.service_port_name != self.service.port.name:
            raise ContractViolation("Ingress backend must reference the Service port named http")
