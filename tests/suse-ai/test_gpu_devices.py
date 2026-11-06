"""Physical device identity, workload allocation and MIG exclusion."""

import copy
import unittest

from test_contract import component, mapped, record


class GpuDeviceTest(unittest.TestCase):
    def observation(self):
        return record(signal="METRICS", metric="DCGM_FI_DEV_GPU_UTIL",
                      resource={"service.name": "dcgm", "service.namespace": "gpu-operator",
                                "k8s.cluster.name": "east", "k8s.node.name": "worker",
                                "k8s.pod.name": "exporter"},
                      attributes={"UUID": "GPU-device", "gpu": "0", "modelName": "T4",
                                  "pod_namespace": "ai", "pod_name": "inference"})

    def test_uuid_and_cluster_identify_the_device_independently_of_exporter_or_pod(self):
        data = self.observation()
        expected = "urn:suse-ai:/east:gpu/GPU-device"
        self.assertEqual(component(data, "genai gpu")["identifier"], expected)
        for location, key, value in (("resource", "k8s.pod.name", "new-exporter"),
                                     ("datapoint", "pod_name", "new-workload")):
            changed = copy.deepcopy(data)
            changed[location]["attributes"][key] = value
            self.assertEqual(component(changed, "genai gpu")["identifier"], expected)
        data["resource"]["attributes"]["k8s.cluster.name"] = "west"
        self.assertEqual(component(data, "genai gpu")["identifier"], "urn:suse-ai:/west:gpu/GPU-device")

    def test_relations_use_the_workload_and_native_node_identities(self):
        relations = mapped(self.observation(), "OtelRelationMapping")
        self.assertEqual({r["typeName"]: r["targetId"] for r in relations}, {
            "allocated to": "urn:kubernetes:/east:ai:pod/inference",
            "runs on": "urn:kubernetes:/east:node/worker",
        })
        self.assertTrue(all(r["sourceId"] == "urn:suse-ai:/east:gpu/GPU-device" for r in relations))

    def test_missing_uuid_node_or_cluster_and_mig_slices_cannot_create_devices(self):
        for location, key in (("resource", "k8s.cluster.name"), ("resource", "k8s.node.name"),
                               ("datapoint", "UUID")):
            for empty in (False, True):
                data = self.observation()
                if empty:
                    data[location]["attributes"][key] = ""
                else:
                    del data[location]["attributes"][key]
                self.assertFalse(any(r["typeName"] == "genai gpu" for r in mapped(data)))
                self.assertEqual(mapped(data, "OtelRelationMapping"), [])
        for key, value in (("GPU_I_ID", "0"), ("GPU_I_ID", 1), ("GPU_I_PROFILE", "1g.5gb")):
            data = self.observation()
            data["datapoint"]["attributes"][key] = value
            self.assertFalse(any(r["typeName"] == "genai gpu" for r in mapped(data)))
            self.assertEqual(mapped(data, "OtelRelationMapping"), [])

    def test_unallocated_device_remains_visible_without_inventing_an_exporter_allocation(self):
        data = self.observation()
        del data["datapoint"]["attributes"]["pod_name"]
        self.assertEqual(component(data, "genai gpu")["tags"]["gpu.uuid"], "GPU-device")
        self.assertEqual([r["typeName"] for r in mapped(data, "OtelRelationMapping")], ["runs on"])
