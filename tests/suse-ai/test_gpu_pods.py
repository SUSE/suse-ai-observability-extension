"""GPU eligibility is driven by workload-attributed telemetry, not node placement."""

import copy
import unittest

from test_contract import BY_ID, component, mapped, record


class GpuPodTest(unittest.TestCase):
    def observation(self, **dimensions):
        return record(
            signal="METRICS",
            resource={
                "service.name": "dcgm",
                "service.namespace": "gpu-operator",
                "k8s.cluster.name": "cluster-a",
                "k8s.node.name": "gpu-node",
                "k8s.namespace.name": "gpu-operator",
                "k8s.pod.name": "dcgm-exporter",
            },
            attributes={"pod_namespace": "ai", "pod_name": "inference", **dimensions},
            metric="DCGM_FI_DEV_GPU_UTIL",
        )

    def test_enriches_workload_pod_not_exporter(self):
        for metric in (
            "DCGM_FI_DEV_GPU_UTIL", "DCGM_FI_DEV_FB_USED",
            "DCGM_FI_DEV_GPU_TEMP", "DCGM_FI_DEV_POWER_USAGE",
        ):
            data = self.observation()
            data["metric"]["name"] = metric
            with self.subTest(metric=metric):
                result = component(data, "pod")
                self.assertEqual(result["identifier"], "urn:kubernetes:/cluster-a:ai:pod/inference")
                self.assertEqual(result["name"], "inference")
                # Base metadata and membership remain the Kubernetes integration's responsibility.
                self.assertEqual(result["tags"], {"suse.ai.gpu.telemetry": "dcgm"})

    def test_incomplete_workload_identity_is_not_gpu_eligibility(self):
        for location, key in (
            ("resource", "k8s.cluster.name"), ("resource", "k8s.node.name"),
            ("datapoint", "pod_namespace"), ("datapoint", "pod_name"),
        ):
            for empty in (False, True):
                data = self.observation()
                if empty:
                    data[location]["attributes"][key] = ""
                else:
                    del data[location]["attributes"][key]
                with self.subTest(location=location, key=key, empty=empty):
                    self.assertEqual(mapped(data), [])

    def test_cpu_and_unattributed_node_telemetry_are_not_gpu_eligibility(self):
        for node in ("gpu-node", "cpu-node"):
            for metric in ("container.cpu.usage", "gen_ai.client.operation.duration"):
                data = self.observation()
                data["resource"]["attributes"]["k8s.node.name"] = node
                data["metric"]["name"] = metric
                with self.subTest(node=node, metric=metric):
                    self.assertFalse(any(x["typeName"] == "pod" for x in mapped(data)))
        data = self.observation()
        data["datapoint"]["attributes"] = {"gpu": "0"}
        self.assertEqual(mapped(data), [])
        data = self.observation()
        data["signal"] = "TRACES"
        self.assertEqual(mapped(data), [])

    def test_cluster_namespace_and_pod_boundaries(self):
        original = self.observation()
        identities = {component(original, "pod")["identifier"]}
        for location, key, value in (
            ("resource", "k8s.cluster.name", "cluster-b"),
            ("datapoint", "pod_namespace", "other-ai"),
            ("datapoint", "pod_name", "other-inference"),
        ):
            data = copy.deepcopy(original)
            data[location]["attributes"][key] = value
            identities.add(component(data, "pod")["identifier"])
        self.assertEqual(len(identities), 4)
        data = copy.deepcopy(original)
        data["resource"]["attributes"]["k8s.pod.name"] = "another-exporter"
        self.assertEqual(component(data, "pod")["identifier"], component(original, "pod")["identifier"])

    def test_presentation_requires_native_pod_and_observation(self):
        presentation = BY_ID["urn:stackpack:suse-ai:component-presentation:gpu-pods"]
        self.assertEqual(
            presentation["binding"]["query"],
            'type = "pod" AND label = "stackpack:kubernetes" AND label = "suse.ai.gpu.telemetry:dcgm"',
        )
        mapping = BY_ID["urn:stackpack:suse-ai:otel-component-mapping:gpu-pods"]
        self.assertEqual(mapping["expireAfter"], 300000)


if __name__ == "__main__":
    unittest.main()
