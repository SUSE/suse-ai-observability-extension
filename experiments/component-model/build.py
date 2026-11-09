"""Stage the Ollama-only experiment; never mutate the release package."""
import argparse
from pathlib import Path
import re
import shutil
import yaml

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

class Tagged(str):
    def __new__(cls, value, tag):
        obj = super().__new__(cls, value)
        obj.tag = tag
        return obj

class Loader(yaml.SafeLoader):
    pass

class Dumper(yaml.SafeDumper):
    pass

for tag in ('!icon', '!include', '!resource'):
    Loader.add_constructor(tag, lambda loader, node: Tagged(loader.construct_scalar(node), node.tag))
Dumper.add_representer(Tagged, lambda dumper, obj: dumper.represent_scalar(obj.tag, str(obj)))

def read(path):
    return yaml.load(path.read_text(), Loader=Loader)

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, Dumper=Dumper, sort_keys=False, width=110))

def build(output, version, mode, specificity=1, probe_field=False, screenshot=None):
    if not re.fullmatch(r'3\.0\.0-spike\.[1-9][0-9]*', version):
        raise ValueError('Use a fresh 3.0.0-spike.N version')
    pack = output / 'suse-ai'
    if pack.exists():
        raise ValueError('Staging directory exists; choose a fresh output directory')
    shutil.copytree(ROOT / 'stackpack/suse-ai', pack)
    manifest = read(pack / 'stackpack.yaml')
    manifest['version'] = version
    write(pack / 'stackpack.yaml', manifest)
    # Retain all non-Ollama behavior. Control removes our presentation contributions
    # only on native Ollama service/instance components, preserving their topology.
    ollama = '(label = "suse.ai.product:ollama" and type in ("otel service", "otel service instance"))'
    for path in (pack / 'settings').rglob('*.sty'):
        doc = read(path)
        changed = False
        for node in doc['nodes']:
            if node['_type'] == 'ComponentPresentation':
                binding = node['binding']
                binding['query'] = '(' + binding['query'] + ') and not ' + ollama
                changed = True
        if changed:
            write(path, doc)
    if mode != 'control':
        for path in (HERE / 'settings').rglob('*.sty'):
            shutil.copyfile(path, pack / 'settings' / ('spike-' + path.name))
        for path in (HERE / 'icons').glob('*.svg'):
            shutil.copyfile(path, pack / 'icons' / path.name)
        for path in (HERE / 'resources').iterdir():
            shutil.copyfile(path, pack / 'resources' / path.name)
        shutil.copytree(HERE / 'includes', pack / 'includes/spike')
        # A low-specificity contribution on native Ollama only.
        runtime = read(pack / 'settings/products/ollama/runtime.sty')['nodes'][0]
        runtime['identifier'] = 'urn:stackpack:suse-ai:component-presentation:spike-ollama-overlay'
        runtime['name'] = 'Ollama AI overlay'
        runtime['binding']['query'] = 'label = "stackpack:suse-ai" and ' + ollama
        runtime['rank']['specificity'] = specificity
        runtime['presentation'].pop('icon', None)
        runtime['presentation']['highlight']['fields'] = [{
            'fieldId': 'suse_ai_spike_product', 'title': 'AI product', 'order': 45,
            'projection': {'_type': 'TextProjection', 'value': "tags.singleValue('suse.ai.product')"},
        }]
        if probe_field:
            runtime['presentation']['highlight']['fields'].append({
                'fieldId': 'namespace', 'title': 'S1 lower-priority namespace', 'order': 95,
                'projection': {'_type': 'TextProjection', 'value': "tags.singleValue('service.namespace')"},
            })
        runtime['presentation']['highlight']['relatedResources'] = [{
            'resourceId': 'suse_ai_spike_served_models', 'title': 'Served models', 'order': 50,
            'topologyQuery': 'withNeighborsOf(direction = "down", components = (identifier = "${identifiers[0]}"), levels = "1") and type = "genai served model"',
            'presentationIdentifier': 'urn:stackpack:suse-ai:component-presentation:served-models',
        }]
        write(pack / 'settings/spike-ollama-overlay.sty', {'nodes': [runtime]})
        models_path = pack / 'settings/products/ollama/model-mapping.sty'
        models = read(models_path)
        models['nodes'][0]['output'].update({
            'domainName': "'SUSE AI'", 'domainIdentifier': "'urn:stackpack:suse-ai:domain:suse-ai'",
            'layerName': "'Models'", 'layerIdentifier': "'urn:stackpack:suse-ai:layer:models'",
        })
        write(models_path, models)
        relation_path = pack / 'settings/products/ollama/model-relation.sty'
        relation = read(relation_path)
        relation['nodes'][0]['output']['typeName'] = "'serves'"
        write(relation_path, relation)
    # Repeated spike -> stable -> spike cycles remove/re-add these mappings.
    # A fresh settings identifier worked around the observed refresh gap; its
    # underlying cause was not isolated. Component URNs remain stable. Releases should preserve
    # their mapping identifiers and upgrade in place.
    if mode != 'control':
        for path in (pack / 'settings').glob('spike-*.sty'):
            doc = read(path)
            for node in doc['nodes']:
                if node['_type'] in ('OtelComponentMapping', 'OtelRelationMapping'):
                    node['identifier'] += '-' + version.rsplit('.', 1)[-1]
            write(path, doc)
    if screenshot:
        shutil.copyfile(screenshot, pack / 'resources/spike-control.png')
        for resource in ('overview.md', 'detailed-overview.md'):
            with (pack / 'resources' / resource).open('a') as f:
                f.write('\n### Screenshot embedding probe\n\n![Relative resource probe](spike-control.png)\n')
                f.write(f'\n![Versioned resource probe](/api/stackpack/suse-ai/resources/{version}/spike-control.png)\n')
    print(pack)
    return pack

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--version', required=True)
    p.add_argument('--mode', choices=['control', 'overlay'], required=True)
    p.add_argument('--specificity', type=float, default=1)
    p.add_argument('--probe-field', action='store_true')
    p.add_argument('--screenshot', type=Path)
    a = p.parse_args()
    build(a.output, a.version, a.mode, a.specificity, a.probe_field, a.screenshot)
