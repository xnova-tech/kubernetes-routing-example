from pathlib import Path

from kubernetes_routing.contract import inspect_stack
from kubernetes_routing.domain import ContainerPort, ServicePort
from kubernetes_routing.manifest import load_stack

STACK_FILE = Path(__file__).parents[1] / "stack.yaml"


def test_manifest_contract_is_complete() -> None:
    stack = load_stack(STACK_FILE)

    stack.validate()

    assert stack.deployment.replicas == 2
    assert stack.deployment.container_port == ContainerPort(name="http", number=80)
    assert stack.service.port == ServicePort(name="http", number=80, target_name="http")
    assert stack.ingress.service_name == stack.service.name


def test_demo_observations_are_deterministic() -> None:
    rendered = [observation.render() for observation in inspect_stack(STACK_FILE)]

    assert rendered == [
        "resources: Deployment, Service, Ingress",
        "namespace: xnova-k8s-article",
        "deployment: replicas=2 image_digest=pinned",
        "selector: app=xnova-web",
        "route: / -> xnova-web:http -> http:80",
        "negative_control: mismatched Service selector rejected",
    ]
