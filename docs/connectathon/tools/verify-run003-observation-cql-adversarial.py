#!/usr/bin/env python3
"""Exercise final run003 Observation CQL failure/null behavior without QR input."""
import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

CLI: Path
TERMINOLOGY: Path
ADVERSARIAL: Path
PREPARED: Path
COMPUTABLE: Path
CQL: Path
OUTPUT_DIR: Path
REPORT: Path
BASE: dict[str, Path] = {}

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def resources(bundle): return [entry['resource'] for entry in bundle.get('entry', [])]
def ids(path):
    rs=resources(json.loads(path.read_text()))
    patient=next(r for r in rs if r['resourceType']=='Patient')['id']
    return patient

def write_mutations():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_path=PREPARED/'eligible-unsteady-yes.json'
    base=json.loads(base_path.read_text())
    observations=[e['resource'] for e in base['entry'] if e['resource']['resourceType']=='Observation']
    if len(observations)!=3: raise RuntimeError('expected three v2 extracted Observations')
    duplicate=copy.deepcopy(base)
    duplicate_obs=copy.deepcopy(observations[0]); duplicate_obs['id']='adversarial-duplicate-same-code'
    duplicate['entry'].append({'resource': duplicate_obs})
    duplicate_path=OUTPUT_DIR/'duplicate-same-code.json'; duplicate_path.write_text(json.dumps(duplicate, indent=2)+'\n')
    partial=copy.deepcopy(base)
    removed=False
    keep=[]
    for entry in partial['entry']:
        resource=entry['resource']
        if resource['resourceType']=='Observation' and not removed:
            removed=True; continue
        keep.append(entry)
    partial['entry']=keep
    partial_path=OUTPUT_DIR/'partial-screen.json'; partial_path.write_text(json.dumps(partial, indent=2)+'\n')
    wrong_version=(CQL.read_text().replace("version '0.2.0'\n\nparameter", "version '9.9.9'\n\nparameter", 1))
    # Replace only the first ValueSet declaration version, leaving the library identity untouched.
    wrong_version=wrong_version.replace("ValueSet/feel-unsteady-when-standing-or-walking' version '0.2.0'", "ValueSet/feel-unsteady-when-standing-or-walking' version '9.9.9'", 1)
    wrong_path=OUTPUT_DIR/'FallRiskScreeningRecommendationLogic-wrong-valueset-version.cql'; wrong_path.write_text(wrong_version)
    return duplicate_path, partial_path, wrong_path

def invoke(cql, data, expression, terminology=None):
    terminology = terminology or TERMINOLOGY
    patient=ids(data)
    command=[str(CLI),'cql','eval',str(cql),expression,'--data',str(data),'--terminology',str(terminology),
             '--subject',f'Patient/{patient}','--evaluation-date','2026-06-15T09:20:00Z',
             '--measurement-period-start','2026-01-01T00:00:00Z','--measurement-period-end','2026-12-31T23:59:59Z',
             '--lib-path',str(COMPUTABLE)]
    p=subprocess.run(command, text=True, capture_output=True)
    return command, p.returncode, p.stdout.strip(), p.stderr.strip()

def run_case(name, data, expected_completed, expected_risk, cql=None, terminology=None, expects_error=False):
    cql = cql or CQL
    terminology = terminology or TERMINOLOGY
    actual={}; commands=[]
    for expression in ['Completed Three Question Screen','At Increased Fall Risk']:
        cmd, rc, out, err=invoke(cql,data,expression,terminology)
        commands.append(cmd); actual[expression]={'exitCode':rc,'stdout':out,'stderr':err}
    if expects_error:
        passed=all(x['exitCode'] != 0 and 'Valueset not found' in x['stderr'] for x in actual.values())
    else:
        passed=all(x['exitCode']==0 for x in actual.values()) and json.loads(actual['Completed Three Question Screen']['stdout'])==expected_completed and json.loads(actual['At Increased Fall Risk']['stdout'])==expected_risk
    return {'case':name,'input':{'path':str(data),'sha256':sha(data)},'expected': {'completed': expected_completed,'risk':expected_risk,'error':expects_error},'actual':actual,'commands':commands,'passed':passed}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',required=True,type=Path,help='run003 durable workspace')
    parser.add_argument('--runtime-root',required=True,type=Path,help='RH checkout containing target/debug/rh')
    parser.add_argument('--terminology-root',required=True,type=Path,help='terminology-cql-replay durable directory')
    parser.add_argument('--prepared-root',required=True,type=Path,help='v2 QR-free prepared-data directory')
    parser.add_argument('--run-id',default='run003',help='simple report label')
    parser.add_argument('--output',required=True,type=Path,help='JSON report path')
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*',args.run_id): parser.error('--run-id must be a simple report label')
    global CLI, TERMINOLOGY, ADVERSARIAL, PREPARED, COMPUTABLE, CQL, OUTPUT_DIR, REPORT, BASE
    CLI=(args.runtime_root.resolve()/'target/debug/rh')
    TERMINOLOGY=(args.terminology_root.resolve()/'terminology.json')
    ADVERSARIAL=(args.terminology_root.resolve()/'adversarial')
    PREPARED=args.prepared_root.resolve()
    COMPUTABLE=(args.workspace.resolve()/'topics/steadi-live-replay/computable')
    CQL=COMPUTABLE/'FallRiskScreeningRecommendationLogic.cql'
    OUTPUT_DIR=args.output.resolve().parent/'adversarial-inputs'
    REPORT=args.output.resolve()
    BASE={name: ADVERSARIAL/f'{name}.json' for name in [
      'wrong-code','wrong-system','missing-boolean','unrelated-patient','wrong-encounter',
      'mixed-derived-from','mixed-encounter','non-questionnaire-derived-from']}
    required=[CLI,TERMINOLOGY,PREPARED/'eligible-unsteady-yes.json',CQL]
    if any(not item.is_file() for item in required):
        parser.error('runtime, terminology, prepared data, or final CQL source is missing')
    duplicate,partial,wrong_version=write_mutations()
    cases=[]
    for name,data in BASE.items():
        cases.append(run_case(name,data,False,None))
    cases.append(run_case('duplicate-same-code',duplicate,False,None))
    cases.append(run_case('partial-screen',partial,False,None))
    cases.append(run_case('missing-valueset',PREPARED/'eligible-unsteady-yes.json',None,None,terminology=ADVERSARIAL/'missing-valueset.json',expects_error=True))
    cases.append(run_case('wrong-declared-valueset-version',PREPARED/'eligible-unsteady-yes.json',None,None,cql=wrong_version,expects_error=True))
    report={'runId':args.run_id,'scope':'Final Observation-primary CQL adverse behavior. Synthetic cases verify false/null for malformed or incomplete clinical Observation groups; missing or version-mismatched ValueSet expansion fails visibly. This is CQL-level coverage, separate from extractor/reconciliation negatives.',
            'passed':all(c['passed'] for c in cases),
            'runtime':{'path':str(CLI),'sha256':sha(CLI)},
            'cql':{'path':str(CQL),'sha256':sha(CQL)},
            'terminology':{'path':str(TERMINOLOGY),'sha256':sha(TERMINOLOGY)},
            'cases':cases}
    REPORT.parent.mkdir(parents=True,exist_ok=True); REPORT.write_text(json.dumps(report,indent=2)+'\n')
    print(REPORT)
    return 0 if report['passed'] else 1
if __name__=='__main__': sys.exit(main())
