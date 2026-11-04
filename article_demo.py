"""Run the deterministic Kubernetes manifest contract."""

from pathlib import Path

from kubernetes_routing.contract import inspect_stack


def main() -> None:
    stack_file = Path(__file__).resolve().parent / "stack.yaml"
    for observation in inspect_stack(stack_file):
        print(observation.render())


if __name__ == "__main__":
    main()
