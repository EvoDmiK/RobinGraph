const fs=require('fs'),assert=require('assert');const base='http://127.0.0.1:8000';const results=[];
async function test(name,path,body,expected=200,verify){try{const r=await fetch(base+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(120000)});const data=await r.json();assert.equal(r.status,expected);if(verify)verify(data);results.push({name,status:'passed',http:r.status,kind:data.result?.kind,disposition:data.disposition,returned:data.returned??data.results?.length,warnings:data.warnings,channels:[...new Set((data.results||[]).flatMap(x=>x.channels||[]))],generated_answer:typeof data.answer_text==='string'&&data.answer_text.length>0});}catch(e){results.push({name,status:'failed',error:e.message});}fs.writeFileSync('/tmp/robingraph-browser-qa/api.json',JSON.stringify(results,null,2));}
(async()=>{
for(const endpoint of ['related','similar','ecological-related','subspecies','name-relations','profile'])await test(endpoint,'/v1/taxa/'+endpoint+'?name='+encodeURIComponent('청둥오리'),undefined,200,d=>assert(Object.keys(d).length));
await test('lineage Korean','/v1/taxa/lineage?name='+encodeURIComponent('청둥오리'),undefined,200,d=>assert(d.lineage.some(x=>x.scientific_name==='Anas platyrhynchos')));
await test('lineage scientific','/v1/taxa/lineage?scientific_name=Anas%20platyrhynchos');
await test('observations filtered','/v1/observations?scientific_name=Anas%20platyrhynchos&limit=10');
await test('chat observations explicit','/v1/chat',{question:'청둥오리 관찰 기록',intent:'observations',filters:{kind:'observations',scientific_name:'Anas platyrhynchos',limit:10}},200,d=>assert.equal(d.result.kind,'observations'));
for(const mode of ['fulltext','hybrid'])await test('document search '+mode,'/v1/search',{question:'mallard',mode,limit:5});
await test('evidence generation explicit','/v1/chat',{question:'청둥오리 관련 근거 문서를 찾아줘',intent:'evidence',filters:{kind:'evidence',limit:3}},200,d=>assert.equal(d.result.kind,'evidence'));
await test('unknown taxon','/v1/taxa/profile?name=Doesnotexist12345',undefined,404);
await test('missing lineage parameter','/v1/taxa/lineage',undefined,422);
await test('empty question rejected','/v1/chat',{question:' '},422);
await test('inverted date range rejected','/v1/chat',{question:'기록',intent:'observations',filters:{kind:'observations',observed_from:'2026-10-14',observed_to:'2026-10-01'}},422);
await test('fixture grounded answer','/v1/answers',{question:'참새의 학명은 무엇인가?'});
console.log(JSON.stringify(results));if(results.some(x=>x.status==='failed'))process.exitCode=1;
})().catch(e=>{console.error(e.message);process.exit(1)});
