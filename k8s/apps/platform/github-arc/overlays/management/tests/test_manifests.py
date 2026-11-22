import ipaddress
import subprocess
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT.parent.parent


class ManifestRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rendered = subprocess.run(["kustomize", "build", "--enable-helm", str(ROOT)], check=True, capture_output=True, text=True).stdout
        cls.resources = [item for item in yaml.safe_load_all(rendered) if isinstance(item, dict)]

    def find(self, kind, name):
        return next(item for item in self.resources if item.get("kind") == kind and item.get("metadata", {}).get("name") == name)

    def test_component_base_selected_by_management_overlay(self):
        overlay = (ROOT / "kustomization.yaml").read_text()
        self.assertIn("../../base", overlay)
        self.assertTrue((COMPONENT / "base" / "kustomization.yaml").is_file())

    def test_generated_code_configmap_namespaced_and_referenced(self):
        configmaps = [item for item in self.resources if item.get("kind") == "ConfigMap" and "discovery-code" in item["metadata"]["name"]]
        self.assertEqual(len(configmaps), 1)
        configmap = configmaps[0]
        self.assertEqual(configmap["metadata"]["namespace"], "arc-discovery")
        self.assertRegex(configmap["metadata"]["name"], r"arc-personal-discovery-code-[a-z0-9]{10}")
        deployment = self.find("Deployment", "arc-personal-discovery")
        pod = deployment["spec"]["template"]["spec"]
        self.assertEqual(deployment["metadata"]["namespace"], "arc-discovery")
        code_volume = next(volume for volume in pod["volumes"] if volume["name"] == "code")
        self.assertEqual(code_volume["configMap"]["name"], configmap["metadata"]["name"])
        self.assertEqual(pod["securityContext"]["runAsUser"], 10001)
        self.assertEqual(pod["securityContext"]["fsGroup"], 10001)
        credential_volume = next(volume for volume in pod["volumes"] if volume["name"] == "app-credentials")
        self.assertEqual(credential_volume["secret"]["defaultMode"], 0o440)
        self.assertEqual(next(volume for volume in pod["volumes"] if volume["name"] == "plugin-token")["secret"]["secretName"], "arc-discovery-plugin")
        credential_secret = next(item for item in self.resources if item.get("kind") == "ExternalSecret" and item["metadata"]["name"] == "arc-vfondevilla-discovery-app")
        self.assertEqual({item["secretKey"] for item in credential_secret["spec"]["data"]}, {"app_id", "installation_id", "private_key"})

    def test_plugin_token_external_secrets_exist_in_both_namespaces(self):
        externals = [item for item in self.resources if item.get("kind") == "ExternalSecret" and item["metadata"]["name"] == "arc-discovery-plugin"]
        self.assertEqual({item["metadata"]["namespace"] for item in externals}, {"argocd", "arc-discovery"})
        for item in externals:
            entry = item["spec"]["data"][0]
            self.assertEqual((entry["remoteRef"]["key"], entry["remoteRef"]["property"]), ("ARC Argo plugin", "token"))

    def test_network_policies_have_valid_cidrs_dns_and_private_denials(self):
        policies = [item for item in self.resources if item.get("kind") == "NetworkPolicy" and item["metadata"]["name"] == "runner-public-egress-only"]
        policies += [item for item in self.resources if item.get("kind") == "NetworkPolicy" and item["metadata"]["name"] == "arc-personal-discovery"]
        self.assertEqual(len(policies), 3)
        for policy in policies:
            egress = policy["spec"]["egress"]
            dns = [rule for rule in egress if any(port.get("port") == 53 for port in rule.get("ports", []))]
            self.assertTrue(dns, policy["metadata"])
            public = [peer["ipBlock"] for rule in egress for peer in rule.get("to", []) if "ipBlock" in peer]
            self.assertTrue(public, policy["metadata"])
            for block in public:
                network = ipaddress.ip_network(block["cidr"])
                public_probe = ipaddress.ip_address("8.8.8.8" if network.version == 4 else "2606:4700:4700::1111")
                if public_probe in network:
                    self.assertFalse(any(public_probe in ipaddress.ip_network(cidr) for cidr in block.get("except", [])))
                for excluded in block.get("except", []):
                    self.assertTrue(ipaddress.ip_network(excluded).subnet_of(network), (block, excluded))
                probes = (["10.1.2.3", "172.20.1.1", "192.168.1.2", "127.0.0.1", "169.254.169.254", "100.64.1.1"] if network.version == 4 else ["fc00::1", "fe80::1"])
                for address in probes:
                    candidate = ipaddress.ip_address(address)
                    if candidate in network:
                        self.assertTrue(any(candidate in ipaddress.ip_network(cidr) for cidr in block.get("except", [])), (block, address))
        runners = [item for item in policies if item["metadata"]["name"] == "runner-public-egress-only"]
        for policy in runners:
            egress = policy["spec"]["egress"]
            dns = [rule for rule in egress if any(port.get("port") == 53 for port in rule.get("ports", []))]
            self.assertEqual({(port["protocol"], port["port"]) for rule in dns for port in rule["ports"]}, {("UDP", 53), ("TCP", 53)})
            public = [rule for rule in egress if any("ipBlock" in peer for peer in rule.get("to", []))]
            self.assertEqual(len(public), 1)
            self.assertEqual(public[0]["ports"], [{"protocol": "TCP", "port": 443}])
            for address in ("10.20.0.4", "172.20.0.5", "192.168.1.7", "100.64.1.2", "169.254.169.254"):
                candidate = ipaddress.ip_address(address)
                allowed = any(candidate in ipaddress.ip_network(peer["ipBlock"]["cidr"]) and not any(candidate in ipaddress.ip_network(excluded) for excluded in peer["ipBlock"].get("except", [])) for rule in public for peer in rule.get("to", []) if "ipBlock" in peer)
                self.assertFalse(allowed, address)
            self.assertTrue(any(ipaddress.ip_address("8.8.8.8") in ipaddress.ip_network(peer["ipBlock"]["cidr"]) for rule in public for peer in rule.get("to", []) if "ipBlock" in peer))
        cilium = [item for item in self.resources if item.get("kind") == "CiliumNetworkPolicy"]
        self.assertEqual(cilium, [])

    def test_org_runner_listener_and_personal_application_pods_are_compliant(self):
        runner_set = self.find("AutoscalingRunnerSet", "cloud-viking-io")
        for spec in (runner_set["spec"]["template"]["spec"], runner_set["spec"]["listenerTemplate"]["spec"]):
            self.assertEqual(spec["securityContext"]["runAsUser"], 1001)
            self.assertEqual(spec["securityContext"]["runAsGroup"], 1001)
            self.assertEqual(spec["securityContext"]["seccompProfile"]["type"], "RuntimeDefault")
        runner = runner_set["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(runner["image"], "ghcr.io/actions/actions-runner:2.338.2")
        self.assertEqual(runner["securityContext"]["capabilities"]["drop"], ["ALL"])
        for pod_spec in (runner_set["spec"]["template"]["spec"], runner_set["spec"]["listenerTemplate"]["spec"]):
            self.assertTrue(pod_spec["securityContext"]["runAsNonRoot"])
            for container in pod_spec["containers"]:
                self.assertFalse(container["securityContext"]["allowPrivilegeEscalation"])
                self.assertEqual(container["securityContext"]["capabilities"]["drop"], ["ALL"])

        appset_result = subprocess.run(["kustomize", "build", str(Path("k8s/argocd/applicationsets/management"))], check=True, capture_output=True, text=True).stdout
        appset = next(item for item in yaml.safe_load_all(appset_result) if isinstance(item, dict) and item.get("kind") == "ApplicationSet" and item["metadata"]["name"] == "github-arc-vfondevilla")
        template = appset["spec"]["template"]["spec"]
        values = template["source"]["helm"]["valuesObject"]
        self.assertEqual(appset["spec"]["syncPolicy"]["applicationsSync"], "sync")
        self.assertEqual(template["destination"]["namespace"], "arc-runners-vfondevilla")
        self.assertEqual(values["template"]["spec"]["containers"][0]["image"], "ghcr.io/actions/actions-runner:2.338.2")
        self.assertEqual(values["template"]["spec"]["securityContext"]["runAsUser"], 1001)
        self.assertEqual(values["template"]["spec"]["securityContext"]["runAsGroup"], 1001)
        self.assertTrue(values["template"]["spec"]["securityContext"]["runAsNonRoot"])
        self.assertEqual(values["listenerTemplate"]["spec"]["containers"][0]["name"], "listener")
        listener = values["listenerTemplate"]["spec"]
        self.assertEqual(listener["securityContext"]["runAsUser"], 1001)
        self.assertTrue(listener["securityContext"]["runAsNonRoot"])
        self.assertFalse(listener["containers"][0]["securityContext"]["allowPrivilegeEscalation"])
        self.assertEqual(values["runnerGroup"], "Default")
        self.assertIn("{{.repoName}}", values["githubConfigUrl"])


if __name__ == "__main__":
    unittest.main()
