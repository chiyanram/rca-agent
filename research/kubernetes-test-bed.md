# Kubernetes test bed and Azure hosting signals

Researched 2026-11-08 for [Does the Test bed get a Kubernetes profile, and which pod-level Seeded faults does it add?](https://github.com/chiyanram/rca-agent/issues/32): kind vs k3d, which pod-level signals each Azure host (AKS, Container Apps, App Service, Functions) exposes, and test-bed footprint. Uncertain points are marked **(?)**. Decisions taken from it are in the ticket's resolution.

## K8s profile research for the RCA test bed

Facts only. Uncertain points are marked **(?)**. I checked release dates against the GitHub API on 2026-11-08.

**1. kind vs k3d**
- **Footprint and startup:** In the one reproducible benchmark (kind v0.22, k3d v5.6), an empty cluster used about 463 MiB on kind and about 423 MiB on k3d. Startup was about 20 s for kind and 7 s for k3d. The node image is about 956 MB for kind and 263 MB for k3d. Blog figures vary a lot, so treat these as rough. [besthub benchmark](https://www.besthub.dev/articles/which-local-kubernetes-tool-is-fastest-minikube-vs-kind-vs-k3d-performance-comparison-3a4e32497f50)
- **Loading local images:** kind uses `kind load docker-image`, and a local registry is a documented recipe. k3d has `k3d image import` plus a built-in `k3d registry create` / `--registry-create`, which suits repeated builds better. [oneuptime k3d](https://oneuptime.com/blog/post/2026-02-08-how-to-use-docker-images-with-k3d-k3s-in-docker/view)
- **Ingress and LoadBalancer:** k3d ships with k3s's Traefik ingress and ServiceLB, and maps ports with `-p 8080:80@loadbalancer`. kind has no built-in LoadBalancer; you need `cloud-provider-kind` or MetalLB, and ingress is installed separately. [cloud-provider-kind](https://github.com/kubernetes-sigs/cloud-provider-kind/wiki)
- **Multi-node and maintenance:** Both support multi-node. Both are actively maintained: kind v0.33.0 came out 2026-08-26, and k3d v5.9.0 came out 2026-06-02 with commits in Nov 2026. kind is the upstream SIG project and the usual choice for CI.
- **Sharing a network with the Compose stack:** k3d has `--network <existing>`, and pods can reach the host as `host.k3d.internal`. kind uses a Docker network called `kind`; you can `docker network connect kind <compose-container>` or set `KIND_EXPERIMENTAL_DOCKER_NETWORK`. **(?)** I did not re-verify the network flags against current docs.
- **Others:** minikube is heavier (VM or Docker driver plus addons). Plain k3s is the lightest option on a VPS but runs on the host, not inside Docker. Neither is clearly better for running next to Compose.

**2. kube-state-metrics (v2.20) and cAdvisor**
Names are from the [KSM pod-metrics](https://github.com/kubernetes/kube-state-metrics/blob/main/docs/metrics/workload/pod-metrics.md) and [deployment-metrics](https://github.com/kubernetes/kube-state-metrics/blob/main/docs/metrics/workload/deployment-metrics.md) docs.
- **OOM:** `kube_pod_container_status_last_terminated_reason{reason="OOMKilled"}`, `kube_pod_container_status_last_terminated_exitcode` (137, experimental), `kube_pod_container_status_last_terminated_timestamp` (experimental).
- **Crash loop and restarts:** `kube_pod_container_status_waiting_reason{reason="CrashLoopBackOff"}` (also catches ImagePullBackOff), `kube_pod_container_status_restarts_total`.
- **Readiness:** `kube_pod_container_status_ready`, `kube_pod_status_ready{condition}`, `kube_deployment_status_replicas_ready`. KSM has no metric for an individual probe failure; those come from kubelet `prober_probe_total` **(?)** or from `Unhealthy` events.
- **Failed rollouts:**
  - `kube_deployment_status_condition{condition="Progressing",status="false"}` (this is ProgressDeadlineExceeded)
  - `kube_deployment_status_replicas_unavailable`
  - `kube_deployment_status_replicas_updated` compared with `kube_deployment_spec_replicas`
  - `kube_deployment_metadata_generation` compared with `kube_deployment_status_observed_generation`
- **Limits:** `kube_pod_container_resource_limits{resource="memory"|"cpu"}` and `..._requests`.
- **cAdvisor, memory near limit:** `container_memory_working_set_bytes` divided by `container_spec_memory_limit_bytes` (or by the KSM limit).
- **cAdvisor, CPU throttling:** `container_cpu_cfs_throttled_periods_total` divided by `container_cpu_cfs_periods_total`. Also `container_oom_events_total`.

**3. Kubernetes events into Loki or Elasticsearch**
- **Grafana Alloy `loki.source.kubernetes_events`:** This is the current Grafana-native path. It tails the events API into Loki in logfmt or JSON, with optional namespace scoping and clustering. [docs](https://grafana.com/docs/alloy/latest/reference/components/loki/loki.source.kubernetes_events/)
- **OTel `k8s_events` receiver:** Still **alpha**, with no formal deprecation. [README](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/receiver/k8seventsreceiver/README.md)
- **OTel `k8sobjects` receiver:** **Beta**, watching `events`. Vendors are moving to it; Splunk's chart deprecated its k8s_events option, and it is part of Elastic's EDOT collector. The whole object lands in the log body. [Splunk upgrading](https://github.com/ZenoCC-Peng/splunk-otel-collector-chart/blob/main/UPGRADING.md), [EDOT](https://docs-v3-preview.elastic.dev/elastic/docs-builder/docs/3102/reference/edot-collector/components/k8sobjectsreceiver.md)
- **kubernetes-event-exporter (resmoio, now mustafaakin):** Last release v1.7 in Feb 2024, with some commits in 2026. It has an Elasticsearch sink but no native Loki sink; the "ownkube" fork claims Loki support and ES8 compatibility. [fork](https://github.com/ownkube/kubernetes-events-exporter)
- **Elasticsearch:** Yes, events can go there too, either through the OTel `k8sobjects` receiver into Elastic, the Elastic Agent Kubernetes integration's event dataset **(?)**, or the exporter's Elasticsearch sink.
- **k8s-monitoring Helm chart (v3):** It installs Alloy Operator, Alloy instances, kube-state-metrics, node-exporter and more. No default memory figures are published; this is heavier than you need for a laptop. [overview](https://grafana.com/docs/grafana-cloud/monitor-infrastructure/kubernetes-monitoring/configuration/helm-chart-config/helm-chart/)

**4. Argo Rollouts vs a plain Deployment**
- **Plain Deployment:**
  - Rollout history is the retained ReplicaSets (`revisionHistoryLimit`, default 10), shown by `kubectl rollout history`.
  - `--record` is deprecated. The `kubernetes.io/change-cause` annotation still fills the CHANGE-CAUSE column.
  - **(?)** I found no official source for the deprecation, only kubectl's own warning text.
- **How a failed plain rollout shows:** After `progressDeadlineSeconds` (default 600) the Progressing condition becomes False with reason `ProgressDeadlineExceeded`. There is no automatic rollback.
- **What Argo adds:**
  - Canary and blue-green steps, and AnalysisTemplates (for example Prometheus queries) that abort automatically.
  - Abort sends traffic back to the stable ReplicaSet and marks the rollout Degraded.
  - `progressDeadlineAbort` is opt-in (default false).
  - Current release is v1.10.2 (2026-11-04). [spec](https://argo-rollouts.readthedocs.io/en/release-1.5/features/specification/)
- **Is it worth it?** The production targets (App Service, Container Apps, Dynatrace or ELK) do not use Argo. A plain Deployment already produces the signals an RCA agent needs. Argo is overkill unless you want to test canary auto-rollback specifically.

**5. Recording the deployed commit on Kubernetes**
- **Image tag:** `:<sha>`. `docker/metadata-action` sets `org.opencontainers.image.revision` automatically.
- **OTel `k8sattributes` processor:**
  - Adds `k8s.deployment.name`, `k8s.pod.name`, `container.image.tag` and similar.
  - Supports `service.version` as metadata, derived from the image tag. That value cannot be used in `pod_association`.
  - Can lift labels or annotations into arbitrary attributes via `labels` / `annotations` blocks (`tag_name`, `key`, `from: pod|namespace|node|deployment`).
  - With `otel_annotations: true`, an annotation `resource.opentelemetry.io/<attr>` becomes resource attribute `<attr>`.
  - The default key name changed to the singular `k8s.pod.label.<key>`.
  - [README](https://pkg.go.dev/github.com/open-telemetry/opentelemetry-collector-contrib/processor/k8sattributesprocessor), [Alloy](https://grafana.com/docs/alloy/latest/reference/components/otelcol/otelcol.processor.k8sattributes/)
- **Collector-free alternative:** The OTel Java agent reads `OTEL_RESOURCE_ATTRIBUTES`, which can be filled from a pod label or annotation through the Downward API. This matches the current Compose stamping.
- **GitHub deployment records:** A job with `environment:` creates the record whatever the job does. If the job runs `kubectl apply` followed by `kubectl rollout status --timeout`, a failed rollout fails the job, so the deployment record is marked failed.

**6. Azure mapping**

| Signal | AKS | App Service (Java) | Container Apps | Functions (Java) |
|---|---|---|---|---|
| OOM kill | Real OOMKilled (exit 137); `KubePodInventory.ContainerStatusReason`, `KubeEvents` | Not a k8s concept; seen as restarts and platform logs **(?)** | `OOMKilled` in system logs | No probes or limits model; instance memory is fixed (Flex: 512/2048/4096 MB) |
| Crash loop / restarts | `ContainerRestartCount`, CrashLoopBackOff | "Web App Restarted" detector, `AppServicePlatformLogs` (no single restart event) | `ContainerAppSystemLogs` (`Reason`, `RevisionName`, `ReplicaName`), ErrorCode `ContainerCrashing` | Host restarts in App Insights `traces` and `FunctionAppLogs` |
| Failed rollout | ProgressDeadlineExceeded | Slot swap or deploy failure (Activity log) | "Error provisioning revision" with `ErrImagePull`, `Timeout`, `ContainerCrashing`; "Deployment Progress Deadline Exceeded"; revision `Degraded` | Deploy failures in `traces` (Flex), `AzureActivity` |
| Health / readiness | k8s probes | Health check pings every minute; instance pulled from the LB after failures, replaced after 1 h (max 1 per hour, 3 per day) | k8s-style probes; defaults added when ingress is on; `Unhealthy` events | None |
| Limits | requests and limits | Plan SKU | CPU and memory per container | Instance size |

Sources: [ACA troubleshooting](https://learn.microsoft.com/azure/container-apps/troubleshoot-container-start-failures), [ACA system logs table](https://learn.microsoft.com/azure/azure-monitor/reference/tables/containerappsystemlogs), [App Service health check](https://learn.microsoft.com/azure/app-service/monitor-instances-health-check), [KubePodInventory](https://learn.microsoft.com/azure/azure-monitor/reference/tables/kubepodinventory), [Flex Consumption](https://learn.microsoft.com/azure/azure-functions/flex-consumption-how-to).
- **Container insights caveat:** By default it does not collect Normal events; enable `collect_all_kube_events` to get them.
- **Dynatrace on AKS:**
  - "Monitor events" is enabled per cluster; it needs ActiveGate 1.265+ and log monitoring, and supports field-selector filters.
  - Events are queryable in Grail via `fetch events | filter event.provider=="KUBERNETES_EVENT"`.
  - It infers cgroup OOM kills, and Warning and BackOff events feed Davis.
  - It infers events when a workload's spec changes (image, replicas, probes), which is useful for deploy correlation.
  - [docs](https://docs.dynatrace.com/docs/observe/infrastructure-observability/container-platform-monitoring/kubernetes-monitoring/monitor-events-kubernetes)
- **Dynatrace on App Service, Container Apps and Functions:** Not verified **(?)**. As I understand it, OneAgent coverage there is via extension or in-container agent, with process crash and restart events.
- **ELK:** Not verified **(?)**. As I understand it, Azure data reaches ELK via diagnostic settings, then Event Hub, then Elastic's Azure integration.

**7. RAM estimate (rough, not measured)**
- kube-state-metrics on a tiny cluster: about 30–80 MiB.
- Alloy (or an OTel collector) as the event shipper plus k8sattributes: about 100–250 MiB.
- Empty cluster: about 450–600 MiB.
- Total extra beyond what Compose already uses: about **0.7–1 GiB**.
- The Java services cost about the same in Kubernetes as in Compose (probably 300–600 MiB each), but they double up if both stacks run the same services at once.
- The full k8s-monitoring chart (node-exporter, operator, several Alloy instances) would add noticeably more **(?)**.
- A machine with about 2 GiB of headroom is a safe minimum.
