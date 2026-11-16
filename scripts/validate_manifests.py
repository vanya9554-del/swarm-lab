from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check() -> list[str]:
    errors: list[str] = []
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    k8s = (ROOT / "deploy" / "k8s.yaml").read_text(encoding="utf-8")
    pg = (ROOT / "deploy" / "k8s-postgres.yaml").read_text(encoding="utf-8")
    chart = (ROOT / "deploy" / "helm" / "swarmlab" / "Chart.yaml").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for name, text, needles in [
        ("Dockerfile", docker, ["HEALTHCHECK", "USER app", "EXPOSE 8788"]),
        ("compose", compose, ["healthcheck", "postgres", "/health"]),
        ("k8s", k8s, ["/ready", "startupProbe", "terminationGracePeriodSeconds", "runAsNonRoot", "resources", "PodDisruptionBudget", "NetworkPolicy"]),
        ("k8s-postgres", pg, ["HorizontalPodAutoscaler", "/ready", "startupProbe", "terminationGracePeriodSeconds", "replicas: 2"]),
        ("helm", chart, ["name: swarmlab", "type: application"]),
        ("ci", ci, ["docker build", "helm lint", "helm template", "validate_manifests"]),
    ]:
        for needle in needles:
            if needle not in text:
                errors.append(f"{name}: missing {needle}")
    return errors


if __name__ == "__main__":
    problems = check()
    print("OK" if not problems else "\n".join(problems))
    raise SystemExit(1 if problems else 0)
