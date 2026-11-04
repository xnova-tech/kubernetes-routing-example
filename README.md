# Маршрут HTTP-запроса в Kubernetes

Этот пример XNova связывает четыре обязанности Kubernetes: Deployment поддерживает две реплики Nginx, Service
выбирает Pod по метке, EndpointSlice хранит адреса готовых backend, а Ingress передаёт HTTP-запрос контроллеру
Traefik. Образ Nginx закреплён по digest.

## Статическая проверка

Нужен Python 3.12. Детерминированная проверка читает `stack.yaml`, преобразует документы в типизированную доменную
модель и проверяет namespace, реплики, метки, порты и ссылку Ingress на Service. Отрицательный контроль подтверждает,
что селектор `app: missing` не соответствует метке Pod.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt -r requirements-dev.txt
.venv/bin/python article_demo.py
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff format --check .
.venv/bin/python -m ruff check .
```

В Windows создайте окружение командой `py -3.12 -m venv .venv` и замените `.venv/bin/python` на
`.venv\Scripts\python.exe`.

## Проверка в одноразовом кластере

Нужны Docker, k3d, совместимый с кластером `kubectl`, `curl` и свободный порт 8081. Всегда указывайте контекст, чтобы
не применить пример в другой кластер.

```bash
k3d cluster create xnova-routing -p '127.0.0.1:8081:80@loadbalancer'
kubectl --context k3d-xnova-routing create namespace xnova-k8s-article
kubectl --context k3d-xnova-routing apply --dry-run=server -f stack.yaml
kubectl --context k3d-xnova-routing apply -f stack.yaml
kubectl --context k3d-xnova-routing -n xnova-k8s-article rollout status deployment/xnova-web --timeout=180s
kubectl --context k3d-xnova-routing -n xnova-k8s-article get endpointslices -l kubernetes.io/service-name=xnova-web
curl -i --max-time 10 http://127.0.0.1:8081/
```

Для отрицательного контроля временно измените селектор Service. Pod продолжат работать, но EndpointSlice потеряет
адреса, а HTTP-маршрут не сможет выбрать backend.

```bash
kubectl --context k3d-xnova-routing -n xnova-k8s-article set selector service/xnova-web app=missing
kubectl --context k3d-xnova-routing -n xnova-k8s-article get endpointslices -l kubernetes.io/service-name=xnova-web -o yaml
curl -i --max-time 10 http://127.0.0.1:8081/

kubectl --context k3d-xnova-routing -n xnova-k8s-article set selector service/xnova-web app=xnova-web
curl -i --max-time 10 http://127.0.0.1:8081/
```

Удалите только созданный для примера кластер:

```bash
k3d cluster delete xnova-routing
```

CI использует закреплённые k3d v5.9.0, K3s/Kubernetes v1.35.5 и kubectl v1.35.5. Локально можно использовать другую
совместимую версию, но фактический результат нужно проверить заново.

Исходники доступны по лицензии MIT.
