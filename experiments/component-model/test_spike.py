"""Exercise GPU attribution and identity using the actual staged CEL expressions."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/suse-ai'))
from test_contract import evaluate
from build import read

NODES = {n['identifier'].rsplit(':', 1)[-1]: n for n in read(Path(__file__).parent / 'settings/gpu-devices.sty')['nodes']}

class GpuAttribution(unittest.TestCase):
    def setUp(self):
        self.context = {'resource': {'attributes': {
            'k8s.cluster.name': 'cluster-a', 'k8s.node.name': 'node-a',
            'k8s.namespace.name': 'gpu-operator', 'k8s.pod.name': 'dcgm-exporter',
        }}, 'datapoint': {'attributes': {
            'UUID': 'GPU-a', 'pod_namespace': 'ai', 'pod_name': 'ollama-123',
        }}}

    def test_allocation_targets_workload_not_exporter(self):
        m = NODES['spike-gpu-pod']
        self.assertTrue(evaluate(m['input']['resource']['scope']['metric']['datapoint']['condition'], self.context))
        self.assertEqual(evaluate(m['output']['targetId'], self.context), 'urn:kubernetes:/cluster-a:ai:pod/ollama-123')

    def test_missing_allocation_does_not_guess_from_exporter(self):
        cond = NODES['spike-gpu-pod']['input']['resource']['scope']['metric']['datapoint']['condition']
        for key in ['pod_name', 'pod_namespace', 'UUID']:
            attrs = self.context['datapoint']['attributes']
            saved = attrs.pop(key)
            self.assertFalse(evaluate(cond, self.context))
            attrs[key] = ''
            self.assertFalse(evaluate(cond, self.context))
            attrs[key] = saved

    def test_gpu_identity_survives_pod_and_node_change(self):
        expr = NODES['spike-gpu-devices']['output']['identifier']
        identity = evaluate(expr, self.context)
        self.context['resource']['attributes']['k8s.node.name'] = 'node-b'
        self.context['datapoint']['attributes']['pod_name'] = 'ollama-456'
        self.assertEqual(evaluate(expr, self.context), identity)
        self.context['resource']['attributes']['k8s.cluster.name'] = 'cluster-b'
        self.assertNotEqual(evaluate(expr, self.context), identity)

    def test_relations_share_device_identity(self):
        identity = evaluate(NODES['spike-gpu-devices']['output']['identifier'], self.context)
        for key in ['spike-gpu-node', 'spike-gpu-pod']:
            self.assertEqual(evaluate(NODES[key]['output']['sourceId'], self.context), identity)
        self.assertEqual(evaluate(NODES['spike-gpu-node']['output']['targetId'], self.context), 'urn:kubernetes:/cluster-a:node/node-a')

if __name__ == '__main__':
    unittest.main()
