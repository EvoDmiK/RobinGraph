'use strict';
const fs=require('node:fs');
(async()=>{
 const dir='/tmp/robingraph-n8n-audio-20261105/';
 const coverage=JSON.parse(fs.readFileSync('/tmp/robingraph-audio-expansion-20261102/coverage.json'));
 const included=coverage.rows.filter(x=>x.finalPlayback==='pass');
 const excluded=coverage.rows.filter(x=>x.finalPlayback!=='pass');
 if(included.length!==12||excluded.length!==2)throw Error('Expected12 decoded successes and2 pending species');
 const result={checkedAt:new Date().toISOString(),target:'http://192.168.219.97:8000',scope:'HTTP basic-profile metadata via POST chat with defer_enrichment=true/defer_discovery=true; no CDN/image/playback request',rows:[]};
 for(const old of included.concat(excluded,[{scientific_name:'Treron sieboldii'}])){
  const expected=included.includes(old);
  const response=await fetch(result.target+'/v1/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:old.scientific_name,intent:'profile',filters:{kind:'profile',name:old.scientific_name},defer_enrichment:true,defer_discovery:true})});
  if(!response.ok){result.rows.push({name:old.scientific_name,httpStatus:response.status,passed:false});continue;}
  const body=await response.json();const profile=body.result?.profile;if(!profile){result.rows.push({name:old.scientific_name,httpStatus:response.status,disposition:body.disposition,passed:false});continue;}const records=(profile.recordings||[]).map(r=>({id:r.id,scientific_name:r.scientific_name,audio_url:r.audio_url,source_url:r.source_url,creator:r.creator,license_name:r.license_name,license_url:r.license_url,recording_type:r.recording_type,recorded_at:r.recorded_at,location:r.location}));
  const passed=profile.taxon.scientific_name===old.scientific_name&&(expected?records.length===1&&profile.recording_availability.status==='available'&&records[0].audio_url===old.audio_url&&records[0].source_url===old.source_url:records.length===0&&profile.recording_availability.status==='no_licensed_recording');
  result.rows.push({name:profile.taxon.scientific_name,korean_name:profile.taxon.korean_name,display_name:profile.taxon.display_name,expectedSupported:expected,supportClass:expected?'supported':old.scientific_name==='Treron sieboldii'?'previously_unsupported':'pending_review',enrichmentPending:profile.enrichment_pending,httpStatus:response.status,availability:profile.recording_availability.status,recordings:records,passed});
  console.log(old.scientific_name,expected?'supported':'pending',records.length,passed);
 }
 result.supported=result.rows.filter(r=>r.expectedSupported).length;result.pendingReview=result.rows.filter(r=>r.supportClass==='pending_review').length;result.previouslyUnsupported=result.rows.filter(r=>r.supportClass==='previously_unsupported').length;result.passed=result.rows.length===15&&result.rows.every(x=>x.passed);
 fs.writeFileSync(dir+'final-support-http-results.json',JSON.stringify(result,null,2));
 console.log(JSON.stringify({supported:result.supported,pending:result.pendingReview,unsupported:result.previouslyUnsupported,passed:result.passed}));if(!result.passed)process.exitCode=1;
})().catch(e=>{console.error(e.name,e.message);process.exitCode=1});
