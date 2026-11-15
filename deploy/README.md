# deploy

- `k8s.yaml` — Deployment/Service/PVC/PDB/NetworkPolicy, probes `/ready`, non-root, resources.
- SQLite: 1 replica, RWO PVC, HPA не применяется.
- PG: отдельный деплой с `--db postgresql://...`; multi-replica.
- Live K8s не проверялся (внешний блокер); манифест — стартовая точка.
