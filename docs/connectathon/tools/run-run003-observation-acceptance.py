#!/usr/bin/env python3
"""Run repeatable local acceptance for run003's SDC-to-Observation CQL path.

The required core uses a frozen raw QuestionnaireResponse extraction capture,
then verifies CQL only with QR-free clinical data. Service replay is separate:
it needs a final uploaded package, snapshot ID, and an authenticated cookie.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, re, subprocess
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def invoke(command: list[str], cwd: Path, log: Path, env: dict[str, str] | None=None) -> dict[str, Any]:
    result=subprocess.run(command,cwd=cwd,capture_output=True,text=True,env=env)
    log.write_text(result.stdout + ('\nSTDERR:\n'+result.stderr if result.stderr else ''))
    text=result.stdout+result.stderr
    pairs=[tuple(map(int, match)) for match in re.findall(r'(\d+)\s*/\s*(\d+)',text)]
    pairs.extend((int(value),int(value)) for value in re.findall(r'PASS\s+[—-]\s+(\d+)\s+assertion',text))
    return {'command':command,'exitCode':result.returncode,'log':str(log),'counts':pairs}
def json_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.is_file() else {}
def count_pass(result: dict[str,Any], expected: int) -> bool:
    total=sum(total for _,total in result['counts']); passed=sum(value for value,_ in result['counts'])
    return result['exitCode']==0 and total==expected and passed==expected

def verify_capture_reuse(workspace: Path, content: Path, capture: Path) -> dict[str,Any]:
    """Bind the frozen QR-free test data to the exact captured Questionnaire."""
    manifest_path=capture/'manifest.json'
    provenance_path=workspace/'tests/cql/observation-capture-provenance.json'
    if not manifest_path.is_file() or not provenance_path.is_file():
        raise ValueError('frozen extraction capture manifest and CQL capture provenance are required')
    manifest=json.loads(manifest_path.read_text())
    provenance=json.loads(provenance_path.read_text())
    expected_questionnaire_sha=manifest.get('questionnaireSha256')
    if not isinstance(expected_questionnaire_sha,str) or len(expected_questionnaire_sha)!=64:
        raise ValueError('extraction capture manifest lacks questionnaireSha256')
    content_bundle=json.loads(content.read_text())
    questionnaires=[entry.get('resource') for entry in content_bundle.get('entry',[]) if entry.get('resource',{}).get('resourceType')=='Questionnaire']
    if len(questionnaires)!=1:
        raise ValueError(f'executable content must contain exactly one Questionnaire, found {len(questionnaires)}')
    packaged_questionnaire_sha=hashlib.sha256((json.dumps(questionnaires[0],indent=2)+'\n').encode()).hexdigest()
    if packaged_questionnaire_sha!=expected_questionnaire_sha:
        raise ValueError('executable Questionnaire differs from the frozen extraction-capture input; create a fresh native capture instead of reusing prepared data')
    capture_manifest_sha=sha(manifest_path)
    if provenance.get('captureManifestSha256')!=capture_manifest_sha or provenance.get('captureQuestionnaireSha256')!=expected_questionnaire_sha:
        raise ValueError('CQL capture provenance is not bound to the supplied frozen extraction capture')
    for case in provenance.get('cases',[]):
        paths_by_library={Path(relative).parts[2]:relative for relative in case.get('testBundlePaths',[]) if len(Path(relative).parts)>=4 and Path(relative).parts[:2]==('tests','cql')}
        for library, expected in (case.get('testBundleSha256ByLibrary') or {}).items():
            relative=paths_by_library.get(library)
            if not isinstance(relative,str) or not isinstance(expected,str) or sha(workspace/relative)!=expected:
                raise ValueError(f"CQL fixture is not bound to its recorded captured transaction: {library}")
    return {'captureManifest':str(manifest_path),'captureManifestSha256':capture_manifest_sha,'questionnaireSha256':expected_questionnaire_sha,'provenance':str(provenance_path),'provenanceSha256':sha(provenance_path)}

def same_public_runtime(report: dict[str,Any], identity: dict[str,str], kind: str) -> bool:
    if kind=='extraction':
        actual=report.get('wrapper',{})
        return actual.get('moduleSha256')==identity['runtime'] and actual.get('wasmSha256')==identity['wasm']
    if kind=='direct':
        actual=report.get('inputs',{})
        return actual.get('runtime',{}).get('sha256')==identity['runtime'] and actual.get('wasm',{}).get('sha256')==identity['wasm']
    raise ValueError(f'unknown public runtime report kind: {kind}')

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',required=True,type=Path,help='durable run003 workspace')
    parser.add_argument('--content',required=True,type=Path,help='final executable content Bundle')
    parser.add_argument('--runtime-root',required=True,type=Path,help='RH checkout with target/debug/rh')
    parser.add_argument('--runtime',required=True,type=Path,help='public @reasonhealth/cpg dist/node.js')
    parser.add_argument('--terminology-root',required=True,type=Path,help='durable terminology-cql-replay directory')
    parser.add_argument('--prepared-root',required=True,type=Path,help='v2 QR-free prepared Observation data')
    parser.add_argument('--extraction-capture',required=True,type=Path,help='frozen v2 raw-QR extraction capture')
    parser.add_argument('--oracle-root',required=True,type=Path,help='frozen six-case oracle test-bundles directory')
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--run-id',default='run003',help='simple report label; use run004 for a successor package')
    parser.add_argument('--rh-skills-bin',default='rh-skills')
    parser.add_argument('--node-bin',default='node')
    args=parser.parse_args()
    paths={name:getattr(args,name).resolve() for name in ['workspace','content','runtime_root','runtime','terminology_root','prepared_root','extraction_capture','oracle_root','output']}
    if not paths['workspace'].is_dir() or not paths['terminology_root'].is_dir() or not paths['prepared_root'].is_dir() or not paths['extraction_capture'].is_dir() or not (paths['oracle_root']/'manifest.json').is_file(): parser.error('workspace, frozen oracle, and required durable input directories must exist')
    if not paths['content'].is_file() or not paths['runtime'].is_file() or not (paths['runtime_root']/'target/debug/rh').is_file(): parser.error('content, public runtime, and native runtime must exist')
    wasm=paths['runtime'].parent.parent/'wasm-node'/'rh_cpg_bg.wasm'
    if not wasm.is_file(): parser.error(f'public runtime WASM companion is missing: {wasm}')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', args.run_id): parser.error('--run-id must be a simple report label')
    try:
        capture_reuse=verify_capture_reuse(paths['workspace'],paths['content'],paths['extraction_capture'])
    except (ValueError,KeyError,json.JSONDecodeError,FileNotFoundError) as error:
        parser.error(str(error))
    paths['output'].mkdir(parents=True,exist_ok=True)
    native_env=os.environ.copy(); native_env['RH_CLI_PATH']=str(paths['runtime_root']/'target/debug/rh')
    initial_runtime={'native':sha(paths['runtime_root']/'target/debug/rh'),'runtime':sha(paths['runtime']),'wasm':sha(wasm)}
    checks=[]
    for library,expected in [('FallRiskScreeningRecommendationLogic',48),('MeasureMeasure',18)]:
        result=invoke([args.rh_skills_bin,'cql','test','steadi-live-replay',library],paths['workspace'],paths['output']/f'native-{library}.log',native_env)
        checks.append({'name':f'native-cql:{library}','status':'pass' if count_pass(result,expected) else 'fail','expectedAssertions':expected,**result})
    extraction_report=paths['output']/'public-node-extraction.json'
    result=invoke([args.node_bin,str(TOOLS/'verify-run003-public-node-extraction.mjs'),'--capture-root',str(paths['extraction_capture']),'--runtime',str(paths['runtime']),'--run-id',args.run_id,'--output',str(extraction_report)],paths['workspace'],paths['output']/'public-node-extraction.log')
    extraction_payload=json_report(extraction_report)
    extraction_identity=same_public_runtime(extraction_payload,initial_runtime,'extraction')
    checks.append({'name':'public-node-wasm:raw-sdc-extraction','status':'pass' if result['exitCode']==0 and extraction_payload.get('passed') is True and extraction_identity else 'fail','runtimeIdentityMatchesRunner':extraction_identity,'report':str(extraction_report),**result})
    adverse_report=paths['output']/'cql-adversarial.json'
    result=invoke(['python3',str(TOOLS/'verify-run003-observation-cql-adversarial.py'),'--workspace',str(paths['workspace']),'--runtime-root',str(paths['runtime_root']),'--terminology-root',str(paths['terminology_root']),'--prepared-root',str(paths['prepared_root']),'--run-id',args.run_id,'--output',str(adverse_report)],paths['workspace'],paths['output']/'cql-adversarial.log')
    checks.append({'name':'native-cql:adversarial-observation-terminology','status':'pass' if result['exitCode']==0 and json_report(adverse_report).get('passed') is True else 'fail','report':str(adverse_report),**result})
    direct_dir=paths['output']/'direct-node'
    result=invoke([args.node_bin,str(TOOLS/'verify-run003-observation-node.mjs'),'--content',str(paths['content']),'--runtime',str(paths['runtime']),'--prepared-root',str(paths['prepared_root']),'--oracle-root',str(paths['oracle_root']),'--run-id',args.run_id,'--output',str(direct_dir)],paths['workspace'],paths['output']/'direct-node.log')
    direct_report=direct_dir/'results.json'
    direct_payload=json_report(direct_report)
    direct_identity=same_public_runtime(direct_payload,initial_runtime,'direct')
    checks.append({'name':'public-node-wasm:qr-free-cpg-measure','status':'pass' if result['exitCode']==0 and direct_payload.get('passed') is True and direct_identity else 'fail','runtimeIdentityMatchesRunner':direct_identity,'report':str(direct_report),**result})
    final_runtime={'native':sha(paths['runtime_root']/'target/debug/rh'),'runtime':sha(paths['runtime']),'wasm':sha(wasm)}
    runtime_stable=final_runtime==initial_runtime
    report={'checkedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'runId':args.run_id,'scope':'Required local CQL and QR-free CPG/Measure checks only. They prove native 48+18 CQL, raw public Node extraction, adversarial CQL, and direct public Node/WASM execution. Service/browser/validator/second-engine results are not inferred.',
            'inputs':{'workspace':str(paths['workspace']),'content':{'path':str(paths['content']),'sha256':sha(paths['content'])},'runtime':{'path':str(paths['runtime']),'sha256':initial_runtime['runtime']},'wasm':{'path':str(wasm),'sha256':initial_runtime['wasm']},'native':{'path':str(paths['runtime_root']/'target/debug/rh'),'sha256':initial_runtime['native']},'terminologyReplay':str(paths['terminology_root']),'preparedData':str(paths['prepared_root']),'historicalNativeExtractionCapture':capture_reuse,'freshPublicNodeExtractionReplay':'public-node-extraction.json','frozenOracle':{'path':str(paths['oracle_root']),'manifestSha256':sha(paths['oracle_root']/'manifest.json')}},
            'runtimeIdentity':{'start':initial_runtime,'end':final_runtime,'stable':runtime_stable},'core':checks,'corePassed':runtime_stable and all(check['status']=='pass' for check in checks),
            'notRun':[{'name':'standalone-raw-qr-api-parity','reason':'requires final service configuration and raw fixture request mapping'},{'name':'workbench-raw-qr-api-matrix','reason':'requires root snapshot ID and authenticated cookie'},{'name':'browser','reason':'manual root-owned gate'},{'name':'official-fhir-validation','reason':'root-owned gate'},{'name':'reference-engine-execution','reason':'not implemented; reference translator is a well-formedness check'}]}
    (paths['output']/'acceptance-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 0 if report['corePassed'] else 1
if __name__=='__main__': raise SystemExit(main())
