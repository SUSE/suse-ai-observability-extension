from pathlib import Path
import re
import shutil
import subprocess
import unittest

import yaml

from support import ROOT, TEMPLATES, nodes


class TemplateRegressions(unittest.TestCase):
    def test_registry_monitor_targets_match_both_discovery_paths(self):
        for monitor in nodes("monitors/kubeflow-model-registry/monitor.sty"):
            self.assertEqual(monitor["arguments"]["urnTemplate"],
                             "urn:suse-ai:product:ml-registry:kubeflow-model-registry")
        lint = shutil.which("npm-groovy-lint")
        self.assertIsNotNone(lint, "Use task stackpack-test to expose the bundled Groovy runtime")
        classpath = str(Path(lint).resolve().parent / "java/groovy/lib/*")
        result = subprocess.run(["java", "-cp", classpath, "groovy.ui.GroovyMain",
                                 str(ROOT / "tests/topology_mapping.groovy"), str(ROOT)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_packaged_metric_binding_references_resolve(self):
        def include(match):
            return (TEMPLATES.parent / match[1]).read_text()
        assembled = re.sub(r'^\{\{ include "([^"]+)" "yaml" \}\}$', include,
                           (TEMPLATES / "suse-ai.sty").read_text(), flags=re.MULTILINE)
        data = yaml.safe_load(re.sub(r"\{\{.*?\}\}", "TEMPLATE", assembled))["nodes"]
        identifiers = [node["identifier"] for node in data if "identifier" in node]
        self.assertEqual(len(identifiers), len(set(identifiers)), "Duplicate packaged identifiers")
        references = set(re.findall(r'urn:stackpack:suse-ai:shared:metric-binding:[\w:.-]+', assembled))
        self.assertEqual(references - set(identifiers), set(), "Unresolved packaged metric binding")
        for match in re.finditer(r'\{\{ include "([^"]+)"', assembled):
            self.assertTrue((TEMPLATES.parent / match[1]).is_file(), match[1])

    def test_topology_expires_after_updates_stop(self):
        datasource = next(node for node in nodes("synchronization.sty")
                          if node.get("config", {}).get("topic") == "sts_topo_suse-ai_collector")
        self.assertEqual(datasource["config"]["expireElementsAfter"], 300000)
