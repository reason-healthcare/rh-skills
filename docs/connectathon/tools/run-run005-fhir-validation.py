#!/usr/bin/env python3
"""Validate actual run005 knowledge, extracted resources, or runtime outputs."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

p = argparse.ArgumentParser()
p.add_argument('--scope', choices=['knowledge', 'extraction', 'runtime'], required=True)
p.add_argument('--content', type=Path, required=True)
p.add_argument('--fixtures', type=Path)
p.add_argument('--score-root', type=Path)
p.add_argument('--node-root', type=Path)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[3]
dist = repo / 'dist/connectathon-20260919'
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=True)
deps = out / 'dependencies'
deps.mkdir(exist_ok=True)

def read(path):
    return json.loads(path.read_text())

def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

content = read(a.content)
knowledge = []
for e in content['entry']:
    r = e['resource']
    path = deps / f"{r['resourceType']}-{r['id']}.json"
    if path.parent != deps:
        raise ValueError('Unsafe resource ID')
    write(path, r)
    knowledge.append(path)

if a.scope == 'knowledge':
    inputs = knowledge
elif a.scope == 'runtime':
    assert a.node_root
    inputs = sorted(a.node_root.glob('*--MeasureReport-measure.json')) + sorted(a.node_root.glob('*--steadi-fall-risk-screening-protocol.json'))
    assert len(inputs) == 12, f'Expected 12 actual runtime resources, got {len(inputs)}'
else:
    assert a.fixtures and a.score_root
    report = read(a.score_root / 'score-contract.json')
    assert report['passed'] and report['inputs']['content']['sha256'] == sha(a.content)
    index = read(a.fixtures)
    assert len(index['fixtures']) == 6
    inputs = []
    for f in index['fixtures']:
        raw = read(a.fixtures.parent.parent / f['dataBundlePath'])
        extraction_path = a.score_root / f"{f['id']}--extraction.json"
        if extraction_path.exists():
            result = read(extraction_path)
            assert result['success']
            value = result['value']
            if value['status'] == 'extracted':
                transaction = value['transaction']
                assert len(transaction['entry']) == 4
                target = out / f"{f['id']}--transaction.json"
                write(target, transaction)
                inputs.append(target)
                # Clinical collection Bundles retain transaction fullUrls so their
                # relative references remain valid. Deliberately omit `request`,
                # which belongs only to the transaction representation.
                raw['entry'].extend(
                    {'fullUrl': e['fullUrl'], 'resource': e['resource']}
                    for e in transaction['entry']
                )
        target = out / f"{f['id']}--clinical.json"
        write(target, raw)
        inputs.append(target)
    assert len(inputs) == 10

command = [
    '/Users/bkaney/.asdf/installs/java/adoptopenjdk-17.0.6+10/bin/java',
    '-Xmx2g', f'-Duser.home={dist / "validator-home"}', '-jar',
    str(dist / 'tools/validator_cli-6.10.2.jar'),
    *[str(x.resolve()) for x in inputs], '-version', '4.0.1',
    '-ig', 'hl7.fhir.uv.sdc#4.0.0', '-ig', 'hl7.fhir.uv.cpg#2.0.0',
    '-ig', str(deps), '-tx', 'n/a', '-output', str(out / 'operationoutcome.json'),
]
write(out / 'command.json', command)
with (out / 'validator.log').open('w') as log:
    completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
outcome = read(out / 'operationoutcome.json')
outcomes = [e['resource'] for e in outcome['entry']] if outcome['resourceType'] == 'Bundle' else [outcome]
issues = []
for result in outcomes:
    source = next((e['valueString'] for e in result.get('extension', []) if e['url'].endswith('operationoutcome-file')), None)
    issues.extend({'input': source, **i} for i in result.get('issue', []))
errors = [i for i in issues if i['severity'] in ('error', 'fatal')]
summary = {
    'checkedAt': datetime.now(timezone.utc).isoformat(), 'scope': a.scope,
    'knowledgeBundleSha256': sha(a.content), 'inputCount': len(inputs),
    'inputHashes': {str(x.resolve()): sha(x) for x in inputs},
    'command': str(out / 'command.json'), 'exitCode': completed.returncode,
    'counts': dict(Counter(i['severity'] for i in issues)), 'errors': errors,
    'strictValidatorPassed': not errors and completed.returncode == 0,
    'warningCounts': dict(Counter(i.get('details', {}).get('text', i.get('diagnostics', '')) for i in issues if i['severity'] == 'warning')),
    'operationOutcomeSha256': sha(out / 'operationoutcome.json'),
    'terminologyMode': 'offline; packaged dependencies; no external terminology validation claim',
}
write(out / 'summary.json', summary)
print(json.dumps({k: summary[k] for k in ['scope', 'inputCount', 'counts', 'strictValidatorPassed', 'errors']}, indent=2))
