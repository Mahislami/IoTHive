# Kubernetes Migration Plan

## Goals
- Keep the existing Docker Compose deployment intact as a fallback while building a parallel Kubernetes environment.
- Preserve every stateful component: Django `db.sqlite3`, Mosquitto data/logs, InfluxDB data, and Grafana data.
- Run on a routable “live” server where services can be exposed via real IPs/hostnames without losing local dev ergonomics.

## Current Stateful Assets
| Component | Compose reference | Notes |
| --- | --- | --- |
| Django backend | `docker-compose.yml:4-18` | Uses SQLite per `backend/iothive/settings.py:96-97`; file lives at repo root `db.sqlite3`. |
| Mosquitto broker | `docker-compose.yml:53-64` | Mounts config from `mosquitto/config/mosquitto.conf` and two Docker volumes (`mosquitto-data`, `mosquitto-log`). |
| InfluxDB 2.7 | `docker-compose.yml:78-89` | Stores data under `/var/lib/influxdb2` via `influxdb_data` volume. |
| Grafana | `docker-compose.yml:101-113` | Uses `/var/lib/grafana` bound to `grafana_data` volume. |
| Supporting services | Celery workers/beat (`docker-compose.yml:27-51`), Redis (`docker-compose.yml:20-25`), Telegraf (`docker-compose.yml:90-99`), nginx reverse proxy (`docker-compose.yml:115-129`). |

## Target Kubernetes Layout
### Namespaces & Workloads
- Create a dedicated namespace (`iothive-prod`) to isolate everything from other clusters.
- Convert each long-running service into its own manifest (Deployments for stateless pieces, StatefulSets where storage is attached):
  - `backend`, `celery`, `celery-beat`, `telegraf`, and `nginx` ⇒ `Deployment`.
  - `redis` ⇒ `StatefulSet` or `Deployment` with emptyDir depending on persistence requirements (current compose does not persist, so `Deployment` + `emptyDir` is fine).
  - `mosquitto`, `influxdb`, `grafana` ⇒ `StatefulSet` with dedicated PVCs.
  - `client` is tooling only; keep as a `Job`/`Pod` manifest or omit from production cluster.
- Represent service-to-service networking with ClusterIP Services mirroring compose aliases (e.g., `mosquitto:1883`, `redis:6379`).

### Persistent Storage
- Create one `PersistentVolumeClaim` per data directory: `sqlite-pvc`, `mosquitto-data-pvc`, `mosquitto-log-pvc`, `influxdb-pvc`, `grafana-pvc`.
- Back the PVCs with whatever storage class matches the live server:
  - Cloud provider block storage (gp3, pd-ssd, etc.) if running on managed K8s.
  - If self-hosting (k3s, kubeadm), install a CSI driver (e.g., Longhorn, OpenEBS) or attach existing disks and expose them as static PersistentVolumes.
- Mount the PVCs at the same in-container paths used today so the applications do not need changes.

### Config & Secrets
- Convert `.env` into a `Secret` (sensitive entries) plus `ConfigMap` (non-sensitive). Mount/consume via env vars.
- Convert `mosquitto.conf`, `telegraf.conf`, and `nginx.conf` (plus `.htpasswd-*`) into `ConfigMap`/`Secret` objects mounted read-only.

## Data Migration Strategy
1. **Freeze compose stack** during cutover by stopping the services that write to each datastore, or schedule downtime.
2. **Export/copy data**:
   - `db.sqlite3`: copy the file to a safe location (e.g., tarball) and upload to the server that hosts the cluster.
   - Docker named volumes (`mosquitto-data`, `mosquitto-log`, `influxdb_data`, `grafana_data`): use `docker run --rm -v <volume>:/data -v $(pwd):/backup busybox tar czf /backup/<name>.tgz /data`.
3. **Seed Kubernetes volumes**:
   - Create PVCs first.
   - Launch one-off Kubernetes `Job` per dataset that mounts the PVC and untars the corresponding archive (`busybox`/`alpine` + `tar xzf /seed/<archive>`).
   - For SQLite, mount the PVC to `/app/db.sqlite3` inside the backend Deployment so Django immediately sees existing data.
4. **Enable applications** once validation pods confirm the files exist and correct permissions are set.
5. Keep the tarballs so you can roll back to Compose quickly if something fails.

## Networking & Live Server Considerations
- Provision a Kubernetes cluster on the target server (k3s/microk8s if single node, kubeadm or managed service for multi-node).
- Ensure routable IPs:
  - If the server has a public IP, install MetalLB (for bare metal) or rely on the cloud provider LoadBalancer to expose `nginx`/`mosquitto`/`influxdb`/`grafana` as needed.
  - Use Kubernetes `Ingress` plus an ingress controller (nginx-ingress) to replace the current nginx container. Existing auth files can remain as `Secret` volumes.
  - For MQTT (TCP 1883/9001) expose via a `LoadBalancer` or `NodePort` Service plus firewall rules.
- Update DNS to point to the ingress/load balancer IP only after validation.

## Fallback Plan
- Keep `docker-compose.yml` untouched and `.env` aligned with the Kubernetes Secrets so you can bring the Compose stack back up with `docker compose up -d`.
- Version the migration manifests inside `k8s/` so they never interfere with Compose files.
- During rollout, run Compose stack on current host and Kubernetes on the new live server. Only decommission Compose after the new stack runs stably.

## Next Steps
1. Decide on the target cluster distribution (managed, k3s, etc.) and storage class to use for PVCs.
2. Scaffold Kubernetes manifests inside `k8s/` (namespace, Deployments, StatefulSets, Services, PVCs, ConfigMaps/Secrets).
3. Create migration scripts/jobs to seed PVCs from current Docker volumes and the SQLite file.
4. Stand up the cluster in staging, test connectivity + data integrity, then schedule production cutover.
