import assert from 'node:assert/strict';
import test from 'node:test';
import { aggregateMeasurements, gapScale } from '../src/features/factoryRuns/measurementModel.ts';
const observation = (arm, ttft, extra = {}) => ({kind:'measurement',obs_id:`${arm}-${ttft}`,source_artifacts:['source:OPS/runs/test/result.json@sha256:abc'],values:{arm,prompt_tokens:512,ttft_s:ttft,decode_tps:ttft,warm:true,...extra}});
test('median preserves early slow warm samples and full observed range', () => {
 const rows=aggregateMeasurements([1,2,3,100,200].map((value)=>observation('A',value)));
 assert.equal(rows[0].ttft,3); assert.equal(rows[0].count,5);
 assert.equal(rows[0].ttftMin,1); assert.equal(rows[0].ttftMax,200);
 assert.equal(rows[0].decode,3); assert.equal(rows[0].artifacts.length,1);
});
test('exclude explicit ineligible/discarded requests; surface safety min and cgroup peak',()=>{
 const rows=aggregateMeasurements([observation('A',2,{peak_memory_bytes:50,min_mem_available_bytes:20}),observation('A',3,{peak_memory_bytes:60,min_mem_available_bytes:10}),observation('A',99,{discarded:true}),observation('A',99,{measurement_eligible:false})]);
 assert.equal(rows[0].count,2); assert.equal(rows[0].ttft,2.5); assert.equal(rows[0].memory,60);assert.equal(rows[0].available,10);
});
test('matching median controls derive negative and >100% closure without clipping',()=>{
 const rows=aggregateMeasurements([observation('A',10),observation('S',5),observation('C1',20),observation('D',2)]);
 assert.equal(rows.find(row=>row.arm==='C1').gap,-2);assert.equal(rows.find(row=>row.arm==='D').gap,1.6);
 const scale=gapScale(rows); assert.equal(scale.position(-2),0); assert.equal(scale.position(1.6),100);
});
test('A matching or beating S yields undefined gap; absent controls stay undefined',()=>{
 for(const values of [[observation('A',5),observation('S',10)],[observation('A',5),observation('S',5)],[observation('A',5)]]) assert.ok(aggregateMeasurements(values).every(row=>row.gap===null));
});
