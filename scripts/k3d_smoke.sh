#!/usr/bin/env bash
set -euo pipefail

cluster_name="xnova-routing-ci"
context="k3d-${cluster_name}"
namespace="xnova-k8s-article"

cleanup() {
  k3d cluster delete "${cluster_name}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

k3d cluster create "${cluster_name}" \
  --image rancher/k3s:v1.35.5-k3s1 \
  --port '127.0.0.1:8081:80@loadbalancer' \
  --wait

for _ in {1..60}; do
  if kubectl --context "${context}" -n kube-system get job helm-install-traefik >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
kubectl --context "${context}" -n kube-system wait --for=condition=complete job/helm-install-traefik --timeout=180s
kubectl --context "${context}" -n kube-system rollout status deployment/traefik --timeout=180s

kubectl --context "${context}" create namespace "${namespace}"
kubectl --context "${context}" apply --dry-run=server -f stack.yaml
kubectl --context "${context}" apply -f stack.yaml
kubectl --context "${context}" -n "${namespace}" rollout status deployment/xnova-web --timeout=180s

ready_addresses="$(kubectl --context "${context}" -n "${namespace}" get endpointslices \
  -l kubernetes.io/service-name=xnova-web \
  -o jsonpath='{range .items[*].endpoints[?(@.conditions.ready==true)]}{.addresses[0]}{"\n"}{end}')"
test "$(printf '%s\n' "${ready_addresses}" | sed '/^$/d' | wc -l | tr -d ' ')" = "2"

status=""
for _ in {1..30}; do
  status="$(curl -sS -o /tmp/xnova-routing-positive.html -w '%{http_code}' --max-time 10 http://127.0.0.1:8081/ || true)"
  if test "${status}" = "200"; then
    break
  fi
  sleep 1
done
test "${status}" = "200"
grep -q '<h1>Welcome to nginx!</h1>' /tmp/xnova-routing-positive.html

kubectl --context "${context}" -n "${namespace}" set selector service/xnova-web app=missing
for _ in {1..30}; do
  addresses="$(kubectl --context "${context}" -n "${namespace}" get endpointslices \
    -l kubernetes.io/service-name=xnova-web \
    -o jsonpath='{range .items[*].endpoints[*]}{.addresses[0]}{"\n"}{end}')"
  if test -z "${addresses}"; then
    break
  fi
  sleep 1
done
test -z "${addresses}"

status=""
for _ in {1..30}; do
  status="$(curl -sS -o /tmp/xnova-routing-negative.txt -w '%{http_code}' --max-time 10 http://127.0.0.1:8081/ || true)"
  case "${status}" in
    5??) break ;;
  esac
  sleep 1
done
case "${status}" in
  5??) ;;
  *) exit 1 ;;
esac

kubectl --context "${context}" -n "${namespace}" set selector service/xnova-web app=xnova-web
for _ in {1..30}; do
  addresses="$(kubectl --context "${context}" -n "${namespace}" get endpointslices \
    -l kubernetes.io/service-name=xnova-web \
    -o jsonpath='{range .items[*].endpoints[?(@.conditions.ready==true)]}{.addresses[0]}{"\n"}{end}')"
  if test "$(printf '%s\n' "${addresses}" | sed '/^$/d' | wc -l | tr -d ' ')" = "2"; then
    break
  fi
  sleep 1
done
test "$(printf '%s\n' "${addresses}" | sed '/^$/d' | wc -l | tr -d ' ')" = "2"

status=""
for _ in {1..30}; do
  status="$(curl -sS -o /tmp/xnova-routing-restored.html -w '%{http_code}' --max-time 10 http://127.0.0.1:8081/ || true)"
  if test "${status}" = "200"; then
    break
  fi
  sleep 1
done
test "${status}" = "200"

printf '%s\n' \
  'positive: replicas=2 endpoints=2 http=200' \
  'negative: pods=ready endpoints=0 http=5xx' \
  'restored: endpoints=2 http=200'
