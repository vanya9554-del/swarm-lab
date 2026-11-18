# PRODUCTION — пошаговый запуск swarm-lab в облаке

Всё, что можно было подготовить без аккаунтов, уже готово и проверено в kind CI.
Ниже — только действия человека с доступами. Везде есть прямые ссылки.

## 1. Создать кластер

| Провайдер | Ссылка |
|---|---|
| AWS EKS | https://console.aws.amazon.com/eks/home |
| GCP GKE | https://console.cloud.google.com/kubernetes |
| Azure AKS | https://portal.azure.com/#create/Microsoft.AKS |
| kind (уже в CI) | https://kind.sigs.k8s.io/ |

```bash
# AWS
eksctl create cluster --name swarmlab --region eu-central-1 --nodes 3
aws eks update-kubeconfig --name swarmlab --region eu-central-1

# GCP
gcloud container clusters create swarmlab --region europe-central2 --num-nodes 3
gcloud container clusters get-credentials swarmlab --region europe-central2

# Azure
az aks create -g swarmlab -n swarmlab --node-count 3 --enable-managed-identity
az aks get-credentials -g swarmlab -n swarmlab
```

Проверка:
```bash
kubectl get nodes
```

## 2. Ingress + TLS

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx --create-namespace

helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager -n cert-manager --create-namespace --set crds.enabled=true
```

`ClusterIssuer` (Let's Encrypt):
```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata: {name: letsencrypt-prod}
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: you@example.com
    privateKeySecretRef: {name: letsencrypt-prod}
    solvers:
      - http01: {ingress: {class: nginx}}
```
Создать DNS A-запись на IP ingress:
```bash
kubectl get svc -n ingress-nginx ingress-nginx-controller
```

## 3. Образ + pull secret

Образ: https://github.com/vanya9554-del/swarm-lab/pkgs/container/swarm-lab

Если пакет приватный:
```bash
kubectl create namespace swarmlab
kubectl -n swarmlab create secret docker-registry ghcr-pull \
  --docker-server=ghcr.io \
  --docker-username=<github-user> \
  --docker-password=<PAT с read:packages>
```

## 4. Секреты

Вариант A — K8s Secrets:
```bash
kubectl -n swarmlab create secret generic swarmlab-auth --from-literal=token='<token>'
kubectl -n swarmlab create secret generic swarmlab-pg \
  --from-literal=dsn='postgresql://user:pass@pg-host:5432/swarm?sslmode=require'
```

Вариант B — Vault + External Secrets (проверено в CI):
- https://external-secrets.io
- https://developer.hashicorp.com/vault

## 5. PostgreSQL

Создать managed PG (RDS/Cloud SQL/Azure DB), БД `swarm`, SSL, DSN в secret.
SQLite в production не масштабируется.

## 6. Helm deploy

`values-prod.yaml`:
```yaml
image:
  repository: ghcr.io/vanya9554-del/swarm-lab
  tag: v11.6.0
imagePullSecrets: [{name: ghcr-pull}]
replicaCount: 3
postgresql:
  enabled: true
  existingSecret: swarmlab-pg
  dsnKey: dsn
persistence:
  enabled: false
auth:
  enabled: true
  existingSecret: swarmlab-auth
  tokenKey: token
ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: swarm.example.com
      paths: [{path: /, pathType: Prefix}]
  tls:
    - secretName: swarmlab-tls
      hosts: [swarm.example.com]
autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
pdb:
  enabled: true
  minAvailable: 2
networkPolicy:
  enabled: true
  ingress:
    - namespaceSelector:
        matchLabels: {kubernetes.io/metadata.name: ingress-nginx}
      podSelector:
        matchLabels: {app.kubernetes.io/name: ingress-nginx}
serviceMonitor:
  enabled: true
prometheusRule:
  enabled: true
```

```bash
helm upgrade --install swarmlab deploy/helm/swarmlab \
  -n swarmlab --create-namespace -f values-prod.yaml --wait --timeout 10m
kubectl -n swarmlab rollout status deploy/swarmlab
curl -fsS https://swarm.example.com/ready
```

## 7. Observability

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install monitoring prometheus-community/kube-prometheus-stack -n monitoring --create-namespace
kubectl apply -f deploy/observability/prometheus-rules.yaml
```
Dashboard: https://github.com/vanya9554-del/swarm-lab/blob/main/deploy/observability/grafana-dashboard.json

## 8. KMS

| Провайдер | Ссылка |
|---|---|
| AWS KMS | https://console.aws.amazon.com/kms |
| GCP KMS | https://console.cloud.google.com/security/kms |
| Vault | https://developer.hashicorp.com/vault |
| External Secrets | https://external-secrets.io |

Приложение не вызывает KMS напрямую: KMS → ESO/CSI → K8s Secret.
Если нужен managed KMS, нужны креды/роль.

## 9. Приёмка

```bash
kubectl -n swarmlab get pods
curl -fsS https://swarm.example.com/ready
curl -fsS https://swarm.example.com/metrics | head
kubectl delete pod -n swarmlab <pod>   # readiness/recovery
helm upgrade ... --wait                # rolling
helm rollback swarmlab <rev>           # rollback
```

Backup/S3 и TLS уже проверены live в kind CI; облачные LB/PVC/IRSA проверяются только на реальном кластере.

## Ссылки

- CI: https://github.com/vanya9554-del/swarm-lab/actions
- Releases: https://github.com/vanya9554-del/swarm-lab/releases
- RUNBOOK: https://github.com/vanya9554-del/swarm-lab/blob/main/deploy/RUNBOOK.md
