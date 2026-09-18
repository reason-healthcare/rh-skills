#!/usr/bin/env node
/** Independent run005 score contract: actual extraction and alternate-source Observations. */
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';
const args = Object.fromEntries(process.argv.slice(2).reduce((a,v,i,all) => { if(i%2===0)a.push([v.slice(2),all[i+1]]); return a; }, []));
for (const key of ['content','runtime','fixtures','oracle-root','output','rh-cli','computable','terminology']) if(!args[key]) throw Error(`--${key} required`);
const read = p => JSON.parse(readFileSync(p,'utf8'));
const write = (p,v) => writeFileSync(p,JSON.stringify(v,null,2)+'\n');
const sha = p => createHash('sha256').update(readFileSync(p)).digest('hex');
const resources = b => (b?.entry??[]).map(e=>e.resource).filter(Boolean);
const clone = x => JSON.parse(JSON.stringify(x));
const out = resolve(args.output); mkdirSync(out,{recursive:true});
const contentPath=resolve(args.content), runtimePath=resolve(args.runtime), indexPath=resolve(args.fixtures);
const content=read(contentPath), index=read(indexPath), oracle=read(resolve(args['oracle-root'],'manifest.json'));
const all=resources(content), questionnaire=all.find(r=>r.resourceType==='Questionnaire'), measure=all.find(r=>r.resourceType==='Measure'), plan=all.find(r=>r.resourceType==='PlanDefinition' && r.id==='steadi-fall-risk-screening-protocol');
if(!questionnaire||!measure||!plan) throw Error('Required package resources missing');
const calculatedItems=questionnaire.item.filter(i=>i.extension?.some(e=>e.url==='http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-calculatedExpression'));
if(calculatedItems.length!==1) throw Error('This declared run005 contract needs one calculated score');
const scoreItem=calculatedItems[0];
if(scoreItem.type!=='integer'||scoreItem.readOnly!==true||scoreItem.code?.length!==1) throw Error('Score item must have integer/readOnly/single Coding');
const coding=scoreItem.code[0];
if (!['system','version','code'].every(k=>typeof coding[k]==='string'&&coding[k].length>0)) throw Error('Score Coding must pin system/version/code');
const isScore=r=>r.resourceType==='Observation'&&r.code?.coding?.some(c=>c.system===coding.system&&c.version===coding.version&&c.code===coding.code);
const runtime=await import(pathToFileURL(runtimePath).href);
const extraction=[], prepared=[];
const preparedDir=resolve(out,'prepared');mkdirSync(preparedDir,{recursive:true});
for(const f of index.fixtures) {
 const raw=read(resolve(dirname(indexPath),'..',f.dataBundlePath));
 const qr=resources(raw).find(r=>r.resourceType==='QuestionnaireResponse');
 const original=oracle.cases.find(c=>c.id===f.id);
 if(!original)throw Error(`No frozen oracle for ${f.id}`);
 const assertions=read(resolve(args['oracle-root'],original.assertions));
 const truths=Object.fromEntries(assertions.assertions.map(a=>[a.expression,a.expected?.value]));
 let extractionValue={status:'not-invoked'}, data=clone(raw), call;
 if(qr){call=runtime.extractQuestionnaireObservations(questionnaire,qr,f.subject,{encounter:f.encounter}); if(call.success) {extractionValue=call.value;data=runtime.reconcileExtractedObservations(raw,`QuestionnaireResponse/${qr.id}`,extractionValue.status==='extracted'?extractionValue.transaction:undefined);}}
 data.entry=data.entry.filter(e=>!['Questionnaire','QuestionnaireResponse'].includes(e.resource?.resourceType));
 const scores=resources(data).filter(isScore);
 const expectedCount=truths['Completed Three Question Screen']===true?1:0;
 const expectedScore=truths['Completed Three Question Screen']?Number(truths['At Increased Fall Risk']):undefined; // Frozen complete examples have zero or one Yes.
 const actualObservations=extractionValue.observations??[];
 const actualScores=actualObservations.filter(isScore);
 const transactionObservations=resources(extractionValue.transaction);
 const checks={invocationSucceeded:!qr||call?.success===true,exactStatus:extractionValue.status===(expectedCount?'extracted':'not-invoked'),actualExtraction:expectedCount===0?actualObservations.length===0:actualObservations.length===4&&actualScores.length===1&&actualScores[0].valueInteger===expectedScore&&actualScores[0].derivedFrom?.some(r=>r.reference===`QuestionnaireResponse/${qr?.id}`),transactionMatches:expectedCount===0?transactionObservations.length===0:extractionValue.transaction?.type==='transaction'&&JSON.stringify(transactionObservations)===JSON.stringify(actualObservations),scoreCount:scores.length===expectedCount,scoreValue:expectedCount===0||scores[0]?.valueInteger===expectedScore,observations:resources(data).filter(r=>r.resourceType==='Observation').length===(expectedCount?4:0),qrFree:!resources(data).some(r=>['Questionnaire','QuestionnaireResponse'].includes(r.resourceType))};
 write(resolve(preparedDir,`${f.id}.json`),data);
 if(call)write(resolve(out,`${f.id}--extraction.json`),call);
 prepared.push({fixtureId:f.id,preparedDataPath:`${f.id}.json`,sha256:sha(resolve(preparedDir,`${f.id}.json`))});
 extraction.push({fixtureId:f.id,status:extractionValue.status,checks,passed:Object.values(checks).every(Boolean)});
}
write(resolve(preparedDir,'manifest.json'),{runId:'run005',sourceFixtureIndexSha256:sha(indexPath),questionnaireSha256:createHash('sha256').update(JSON.stringify(questionnaire,null,2)+'\n').digest('hex'),contentSha256:sha(contentPath),runtimeSha256:sha(runtimePath),cases:prepared});
const originalFixture=index.fixtures.find(f=>f.id==='eligible-unsteady-yes');
const baseline=read(resolve(preparedDir,'eligible-unsteady-yes.json'));
const baselineScore=resources(baseline).find(isScore);
if(!baselineScore)throw Error('Actual extraction did not produce a baseline score');
const plain=clone(baselineScore);plain.id='alternate-source-score';delete plain.derivedFrom;delete plain.identifier;
const nonObservations=baseline.entry.filter(e=>e.resource.resourceType!=='Observation');
const synthetic=[];
function add(id, mutate, completed, risk){const score=clone(plain), list=[score];mutate(score,list);synthetic.push({id,data:{resourceType:'Bundle',type:'collection',entry:[...clone(nonObservations),...list.map(resource=>({resource}))]},completed,risk});}
for(let n=0;n<=3;n++) add(`score-${n}-no-questionnaire-provenance`,s=>{s.valueInteger=n;},true,n>=1);
add('missing-score',(_s,list)=>{list.length=0;},false,null);
add('missing-value',s=>{delete s.valueInteger;},false,null);
add('string-value',s=>{delete s.valueInteger;s.valueString='1';},false,null);
add('boolean-value',s=>{delete s.valueInteger;s.valueBoolean=true;},false,null);
add('negative-score',s=>{s.valueInteger=-1;},false,null);
add('above-range-score',s=>{s.valueInteger=4;},false,null);
add('preliminary-score',s=>{s.status='preliminary';},false,null);
add('entered-in-error-score',s=>{s.status='entered-in-error';},false,null);
add('wrong-code',s=>{s.code.coding[0].code='some-other-score';},false,null);
add('wrong-system',s=>{s.code.coding[0].system='https://example.invalid/other';},false,null);
add('wrong-patient',s=>{s.subject.reference='Patient/some-other-patient';},false,null);
add('wrong-encounter',s=>{s.encounter.reference='Encounter/some-other-encounter';},false,null);
add('missing-effective-time',s=>{delete s.effectiveDateTime;},false,null);
add('out-of-period-score',s=>{s.effectiveDateTime='2025-01-01T00:00:00Z';},false,null);
add('duplicate-valid-score',(s,list)=>{const other=clone(s);other.id='ambiguous-second-score';other.valueInteger=0;list.push(other);},false,null);
add('valid-with-unrelated-patient',(s,list)=>{const other=clone(s);other.id='unrelated-patient-score';other.subject.reference='Patient/some-other-patient';list.push(other);},true,true);
const cases=[];
for(const test of synthetic){
 const file=resolve(out,`${test.id}.json`);write(file,test.data);
 const options={data:test.data,encounter:originalFixture.encounter,evaluationDate:originalFixture.evaluationDate,measurementPeriod:originalFixture.measurementPeriod};
 const m=runtime.evaluateMeasure(measure,originalFixture.subject,content,options), p=runtime.applyPlanDefinition(plan,originalFixture.subject,content,options);
 const counts=Object.fromEntries((m.value?.group?.[0]?.population??[]).map(x=>[x.code?.coding?.[0]?.code,x.count]));
 const notes=resources(p.value).filter(r=>r.resourceType==='RequestGroup').flatMap(r=>r.note??[]).map(n=>n.text??'');
 const has=id=>notes.some(n=>n.startsWith(`Source action: ${id} `)||n===`Source action: ${id}`);
 const checks={observationOnlyInput:!resources(test.data).some(r=>['Questionnaire','QuestionnaireResponse'].includes(r.resourceType))&&resources(test.data).filter(r=>r.resourceType==='Observation').every(r=>r.derivedFrom===undefined),measureSucceeded:m.success===true&&m.value?.status==='complete',population:counts['initial-population']===1&&counts.denominator===1,completion:counts.numerator===Number(test.completed),applySucceeded:p.success===true,exercise:has('refer-exercise-intervention')===(test.risk===true),multifactorial:has('individualize-multifactorial-decision')===(test.risk===true),unknown:has('await-complete-response')===(test.risk===null)};
 const native=[];
 for(const library of ['FallRiskScreeningRecommendationLogic','MeasureMeasure'])for(const [expression,expected] of [['Completed Three Question Screen',test.completed],['At Increased Fall Risk',test.risk]]){
  const command=[resolve(args.computable,`${library}.cql`),expression,'--data',file,'--terminology',resolve(args.terminology),'--subject',originalFixture.subject,'--evaluation-date',originalFixture.evaluationDate,'--measurement-period-start',originalFixture.measurementPeriod.start,'--measurement-period-end',originalFixture.measurementPeriod.end,'--lib-path',resolve(args.computable)];
  const r=spawnSync(resolve(args['rh-cli']),['cql','eval',...command],{encoding:'utf8'});let actual;try{actual=JSON.parse(r.stdout.trim());}catch{actual=r.stdout;}
  native.push({library,expression,expected,actual,exitCode:r.status,stderr:r.stderr,passed:r.status===0&&actual===expected});
 }
 checks.native=native.every(x=>x.passed);
 write(resolve(out,`${test.id}--MeasureReport.json`),m);write(resolve(out,`${test.id}--apply.json`),p);
 cases.push({id:test.id,expected:{completed:test.completed,risk:test.risk},checks,native,passed:Object.values(checks).every(Boolean)});
}
const report={runId:'run005',scope:'Actual public Node/WASM extraction from six frozen raw cases; independent alternate-source score-only data with no Questionnaire/QuestionnaireResponse/derivedFrom; both native CQL libraries and public Node Measure/CPG semantics.',inputs:{content:{path:contentPath,sha256:sha(contentPath)},runtime:{path:runtimePath,sha256:sha(runtimePath)},wasm:{sha256:sha(resolve(dirname(runtimePath),'../wasm-node/rh_cpg_bg.wasm'))},native:{path:resolve(args['rh-cli']),sha256:sha(resolve(args['rh-cli']))},fixtures:{path:indexPath,sha256:sha(indexPath)},scoreCoding:coding},extraction,cases,passed:extraction.every(x=>x.passed)&&cases.every(x=>x.passed)};
write(resolve(out,'score-contract.json'),report);
console.log(JSON.stringify({passed:report.passed,extraction:extraction.filter(x=>!x.passed),cases:cases.filter(x=>!x.passed)},null,2));
if(!report.passed)process.exitCode=1;
