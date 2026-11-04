"""Load the three authored YAML documents into the domain model."""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from kubernetes_routing.domain import (
    ContainerPort,
    ContractViolation,
    DeploymentContract,
    IngressContract,
    LabelSelector,
    ResourceIdentity,
    ServiceContract,
    ServicePort,
    StackContract,
)

YamlMapping = Mapping[str, Any]


def _mapping(value: Any, location: str) -> YamlMapping:
    if not isinstance(value, Mapping):
        raise ContractViolation(f"{location} must be a mapping")
    return value


def _sequence(value: Any, location: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ContractViolation(f"{location} must be a sequence")
    return value


def _required(mapping: YamlMapping, key: str, location: str) -> Any:
    if key not in mapping:
        raise ContractViolation(f"{location}.{key} is required")
    return mapping[key]


def _child(mapping: YamlMapping, key: str, location: str) -> YamlMapping:
    return _mapping(_required(mapping, key, location), f"{location}.{key}")


def _first(mapping: YamlMapping, key: str, location: str) -> YamlMapping:
    items = _sequence(_required(mapping, key, location), f"{location}.{key}")
    if not items:
        raise ContractViolation(f"{location}.{key} must not be empty")
    return _mapping(items[0], f"{location}.{key}[0]")


def _string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractViolation(f"{location} must be a non-empty string")
    return value


def _integer(value: Any, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractViolation(f"{location} must be an integer")
    return value


def _labels(value: Any, location: str) -> dict[str, str]:
    mapping = _mapping(value, location)
    result: dict[str, str] = {}
    for key, label_value in mapping.items():
        if not isinstance(key, str) or not isinstance(label_value, str):
            raise ContractViolation(f"{location} must contain string labels")
        result[key] = label_value
    if not result:
        raise ContractViolation(f"{location} must not be empty")
    return result


def _metadata(document: YamlMapping, kind: str) -> ResourceIdentity:
    metadata = _child(document, "metadata", kind)
    return ResourceIdentity(
        name=_string(_required(metadata, "name", f"{kind}.metadata"), f"{kind}.metadata.name"),
        namespace=_string(_required(metadata, "namespace", f"{kind}.metadata"), f"{kind}.metadata.namespace"),
    )


def _deployment(document: YamlMapping) -> DeploymentContract:
    identity = _metadata(document, "Deployment")
    spec = _child(document, "spec", "Deployment")
    selector = _child(spec, "selector", "Deployment.spec")
    template = _child(spec, "template", "Deployment.spec")
    template_metadata = _child(template, "metadata", "Deployment.spec.template")
    pod_spec = _child(template, "spec", "Deployment.spec.template")
    container = _first(pod_spec, "containers", "Deployment.spec.template.spec")
    port = _first(container, "ports", "Deployment.spec.template.spec.containers[0]")
    return DeploymentContract(
        namespace=identity.namespace,
        name=identity.name,
        replicas=_integer(_required(spec, "replicas", "Deployment.spec"), "Deployment.spec.replicas"),
        selector=LabelSelector(
            _labels(
                _required(selector, "matchLabels", "Deployment.spec.selector"), "Deployment.spec.selector.matchLabels"
            )
        ),
        pod_labels=_labels(
            _required(template_metadata, "labels", "Deployment.spec.template.metadata"),
            "Deployment.spec.template.metadata.labels",
        ),
        image=_string(
            _required(container, "image", "Deployment.spec.template.spec.containers[0]"),
            "Deployment.spec.template.spec.containers[0].image",
        ),
        container_port=ContainerPort(
            name=_string(_required(port, "name", "container port"), "container port.name"),
            number=_integer(_required(port, "containerPort", "container port"), "container port.containerPort"),
        ),
    )


def _service(document: YamlMapping) -> ServiceContract:
    identity = _metadata(document, "Service")
    spec = _child(document, "spec", "Service")
    port = _first(spec, "ports", "Service.spec")
    return ServiceContract(
        namespace=identity.namespace,
        name=identity.name,
        service_type=_string(_required(spec, "type", "Service.spec"), "Service.spec.type"),
        selector=LabelSelector(_labels(_required(spec, "selector", "Service.spec"), "Service.spec.selector")),
        port=ServicePort(
            name=_string(_required(port, "name", "Service.spec.ports[0]"), "Service.spec.ports[0].name"),
            number=_integer(_required(port, "port", "Service.spec.ports[0]"), "Service.spec.ports[0].port"),
            target_name=_string(
                _required(port, "targetPort", "Service.spec.ports[0]"), "Service.spec.ports[0].targetPort"
            ),
        ),
    )


def _ingress(document: YamlMapping) -> IngressContract:
    identity = _metadata(document, "Ingress")
    spec = _child(document, "spec", "Ingress")
    rule = _first(spec, "rules", "Ingress.spec")
    http = _child(rule, "http", "Ingress.spec.rules[0]")
    path = _first(http, "paths", "Ingress.spec.rules[0].http")
    backend = _child(path, "backend", "Ingress path")
    service = _child(backend, "service", "Ingress backend")
    port = _child(service, "port", "Ingress backend.service")
    return IngressContract(
        namespace=identity.namespace,
        name=identity.name,
        class_name=_string(_required(spec, "ingressClassName", "Ingress.spec"), "Ingress.spec.ingressClassName"),
        path=_string(_required(path, "path", "Ingress path"), "Ingress path.path"),
        path_type=_string(_required(path, "pathType", "Ingress path"), "Ingress path.pathType"),
        service_name=_string(_required(service, "name", "Ingress backend.service"), "Ingress backend.service.name"),
        service_port_name=_string(
            _required(port, "name", "Ingress backend.service.port"), "Ingress backend.service.port.name"
        ),
    )


def load_stack(path: Path) -> StackContract:
    documents = [
        _mapping(document, "YAML document")
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if document is not None
    ]
    by_kind = {
        _string(_required(document, "kind", "YAML document"), "YAML document.kind"): document for document in documents
    }
    if set(by_kind) != {"Deployment", "Service", "Ingress"}:
        raise ContractViolation("stack.yaml must contain exactly Deployment, Service and Ingress")
    return StackContract(
        deployment=_deployment(by_kind["Deployment"]),
        service=_service(by_kind["Service"]),
        ingress=_ingress(by_kind["Ingress"]),
    )
