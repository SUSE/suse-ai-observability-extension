"""Read-only spike snapshots, always using an explicit demo URL and token file."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--token-file', required=True, type=Path)
    parser.add_argument('--token-type', choices=('service', 'api'), default='service')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--stage', required=True)
    parser.add_argument('--sts', default='sts')
    parser.add_argument('--name', default='suse-ai')
    args = parser.parse_args()
    if urlparse(args.url).hostname not in ('127.0.0.1', 'localhost', '::1'):
        parser.error('Use the explicit local demo port-forward; this harness never targets the SA instance')
    os.umask(0o077)
    args.output.mkdir(parents=True, exist_ok=True)
    token = args.token_file.read_text().strip()
    token_flag = '--service-token' if args.token_type == 'service' else '--api-token'
    token_header = 'X-API-Key' if args.token_type == 'service' else 'X-API-Token'

    def save(name, data):
        path = args.output / f'{name}-{args.stage}.json'
        if path.exists():
            raise FileExistsError(f'Refusing to overwrite evidence: {path}')
        path.write_text(json.dumps(data, indent=2) + '\n')
        return data

    def cli(*parts):
        result = subprocess.run([args.sts, '--url', args.url, token_flag, token,
                                 *parts, '-o', 'json'], capture_output=True, text=True)
        if result.returncode:
            return {'exitCode': result.returncode, 'error': result.stderr.replace(token, '<redacted>')}
        return json.loads(result.stdout)

    def api(path, body=None):
        req = Request(args.url.rstrip('/') + path,
                      None if body is None else json.dumps(body).encode(),
                      {token_header: token, 'Content-Type': 'application/json'})
        with urlopen(req, timeout=60) as response:
            return json.load(response)

    for name, command in (
        ('instances', ['stackpack', 'list-instances', '--name', args.name]),
        ('versions', ['stackpack', 'list-versions', '--name', args.name]),
        ('monitors', ['monitor', 'list']),
        ('domains', ['settings', 'list', '--type', 'Domain']),
        ('layers', ['settings', 'list', '--type', 'Layer']),
    ):
        save(name, cli(*command))
    syncs = save('sync-list', cli('topology-sync', 'list'))
    save('sync-details', [cli('topology-sync', 'describe', '--id', str(s['nodeId']))
                          for s in syncs['synchronizations']])
    for kind in ('component', 'relation'):
        entries = save(kind + '-mappings', cli('otel-' + kind + '-mapping', 'list'))
        save(kind + '-mapping-status', [
            {'identifier': entry['identifier'],
             'result': cli('otel-' + kind + '-mapping', 'status', '--identifier', entry['identifier'])}
            for entry in entries['otel_' + kind + '_mappings'] if ':' + args.name + ':' in entry['identifier']
        ])
    save('topology', api('/api/snapshot', {
        'query': 'label = "stackpack:' + args.name + '" or type in ("node", "pod")',
        'queryVersion': '0.0.1',
        'metadata': {'groupingEnabled': False, 'showIndirectRelations': False,
                     'minGroupSize': 0, 'groupedByLayer': False, 'groupedByDomain': False,
                     'groupedByRelation': False, 'autoGrouping': False,
                     'connectedComponents': False, 'neighboringComponents': False,
                     'showFullComponent': True},
    }))
    for metric in ('DCGM_FI_DEV_GPU_UTIL', 'ollama_api_up', 'ollama_model_info'):
        save(metric, api('/api/metrics/query_batch', {'queries': [{
            'id': 'q', 'query': metric, '_type': 'instant', 'time': str(int(time.time())),
        }]}))
    print(f'Saved {args.stage} snapshots under {args.output}')


if __name__ == '__main__':
    main()
