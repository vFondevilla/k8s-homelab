import subprocess
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parents[7]
BOOTSTRAP_APPLICATION = REPO_ROOT / "k8s" / "bootstrap" / "argocd" / "root-application.yaml"
IN_CLUSTER_SECRET = (
    REPO_ROOT / "k8s" / "apps" / "platform" / "argocd" / "overlays" / "management" / "in-cluster-secret.yaml"
)
ARC_OVERLAY_PATH = "k8s/apps/platform/github-arc/overlays/management"
ARC_OWNER_NAME = "apps-control-plane"
ARGOCD_NAMESPACE = "argocd"
CONTROL_PLANE_TYPE = "control-plane"
CLUSTER_SECRET_TYPE_LABEL = "argocd.argoproj.io/secret-type"
# The ApplicationSet template must render each path from the git generator.
TEMPLATE_PATH = "{{.path.path}}"

# Go path.Match metacharacters. A literal allowlist path must contain none of them.
GO_METACHARACTERS = frozenset("*?[\\")


def _run_kustomize(path):
    return subprocess.run(
        ["kustomize", "build", str(path)], check=True, capture_output=True, text=True
    ).stdout


def _is_literal(path):
    return bool(path) and not any(char in GO_METACHARACTERS for char in path)


def _bootstrap_sources():
    """Yield (repo, revision, [ApplicationSets]) for each bootstrap Application source."""
    application = yaml.safe_load(BOOTSTRAP_APPLICATION.read_text())
    for source in application["spec"]["sources"]:
        out = _run_kustomize(REPO_ROOT / source["path"])
        app_sets = [
            item
            for item in yaml.safe_load_all(out)
            if isinstance(item, dict) and item.get("kind") == "ApplicationSet"
        ]
        yield source["repoURL"], source.get("targetRevision"), app_sets


def _cluster_selector_matches(selector, cluster_labels):
    """Return True/False if the clusters generator selector matches cluster_labels,
    or None if the selector form is unsupported (cannot be interpreted)."""
    selector = selector or {}
    if set(selector) - {"matchLabels"}:
        return None
    match_labels = selector.get("matchLabels") or {}
    return all(cluster_labels.get(key) == value for key, value in match_labels.items())


def _arc_registration_counts(app_sets, root_repo, root_revision, cluster_labels):
    """Return (arc_total, arc_for_actual_cluster) across eligible in-repo matrices."""
    arc_total = 0
    arc_for_cluster = 0
    for app_set in app_sets:
        name = app_set["metadata"]["name"]
        for generator in app_set["spec"].get("generators", []):
            matrix = generator.get("matrix")
            if not matrix:
                continue
            cluster_gens = [sub["clusters"] for sub in matrix["generators"] if "clusters" in sub]
            git_gens = [sub["git"] for sub in matrix["generators"] if "git" in sub]
            for git_gen in git_gens:
                if git_gen["repoURL"] != root_repo or git_gen.get("revision") != root_revision:
                    continue
                dirs = git_gen.get("directories") or []
                positives = [entry.get("path") for entry in dirs if not entry.get("exclude")]
                if len(positives) != len(set(positives)):
                    raise AssertionError(f"{name}: duplicate positive directory entry")
                includes_arc = ARC_OVERLAY_PATH in positives
                for entry in dirs:
                    path = entry.get("path")
                    if not entry.get("exclude") and not _is_literal(path):
                        raise AssertionError(
                            f"{name}: non-literal allowlist path {path!r}; paths must be literal repo-relative"
                        )
                if includes_arc:
                    if name != ARC_OWNER_NAME:
                        raise AssertionError(
                            f"ARC must be registered by {ARC_OWNER_NAME}, found in {name}"
                        )
                    for entry in dirs:
                        if not entry.get("exclude"):
                            continue
                        excluded = entry.get("path", "")
                        if not _is_literal(excluded):
                            raise AssertionError(f"{name}: non-literal exclusion {excluded!r}")
                        if excluded == ARC_OVERLAY_PATH:
                            raise AssertionError(
                                f"{name}: {ARC_OVERLAY_PATH} is both included and excluded"
                            )
                    source = app_set["spec"]["template"]["spec"]["source"]
                    if source.get("repoURL") != root_repo:
                        raise AssertionError(
                            f"{name}: template source repoURL {source.get('repoURL')!r} "
                            f"must match the bootstrap repo {root_repo!r}"
                        )
                    if source.get("targetRevision") != root_revision:
                        raise AssertionError(
                            f"{name}: template source targetRevision {source.get('targetRevision')!r} "
                            f"must match the bootstrap revision {root_revision!r}"
                        )
                    if source.get("path") != TEMPLATE_PATH:
                        raise AssertionError(
                            f"{name}: template source path {source.get('path')!r} "
                            f"must be the git generator path template {TEMPLATE_PATH!r}"
                        )
                for cluster_gen in cluster_gens:
                    selector = cluster_gen.get("selector") or {}
                    match = _cluster_selector_matches(selector, cluster_labels)
                    if match is None and includes_arc:
                        raise AssertionError(f"{name}: unsupported cluster selector for the ARC owner matrix")
                    if includes_arc and (selector.get("matchLabels") or {}).get("type") != CONTROL_PLANE_TYPE:
                        raise AssertionError(
                            f"{name}: ARC cluster selector must require type={CONTROL_PLANE_TYPE}"
                        )
                    if match:
                        arc_for_cluster += positives.count(ARC_OVERLAY_PATH)
                arc_total += positives.count(ARC_OVERLAY_PATH)
    return arc_total, arc_for_cluster


class BootstrapRegistrationTests(unittest.TestCase):
    def test_arc_overlay_registered_once_for_control_plane_cluster(self):
        cluster_labels = yaml.safe_load(IN_CLUSTER_SECRET.read_text())["metadata"]["labels"]
        self.assertEqual(
            cluster_labels.get(CLUSTER_SECRET_TYPE_LABEL),
            "cluster",
            "in-cluster secret must carry the Argo cluster secret type label",
        )
        self.assertEqual(
            cluster_labels.get("type"),
            CONTROL_PLANE_TYPE,
            "in-cluster secret must select the control-plane cluster",
        )

        arc_total = 0
        arc_for_cluster = 0
        for root_repo, root_revision, app_sets in _bootstrap_sources():
            total, for_cluster = _arc_registration_counts(
                app_sets, root_repo, root_revision, cluster_labels
            )
            arc_total += total
            arc_for_cluster += for_cluster

        self.assertEqual(
            arc_total,
            1,
            f"{ARC_OVERLAY_PATH} must be registered exactly once in an eligible in-repo matrix",
        )
        self.assertEqual(
            arc_for_cluster,
            1,
            "the ARC registration must target the control-plane management cluster",
        )

    def test_arc_application_sets_picked_up_by_bootstrap_root(self):
        by_name = {}
        for _repo, _revision, app_sets in _bootstrap_sources():
            for app_set in app_sets:
                name = app_set["metadata"]["name"]
                by_name.setdefault(name, []).append(app_set)

        for name in ("apps-control-plane", "github-arc-vfondevilla"):
            matches = by_name.get(name, [])
            self.assertEqual(len(matches), 1, f"{name} must be rendered exactly once")
            self.assertEqual(
                matches[0]["metadata"]["namespace"],
                ARGOCD_NAMESPACE,
                f"{name} must live in {ARGOCD_NAMESPACE}",
            )


if __name__ == "__main__":
    unittest.main()
