import json,urllib.request,urllib.error
from pathlib import Path
w=Path('/tmp/robingraph-n8n-audio-20261105');r=json.loads((w/'collect-after-eof-fix-receipt.json').read_text())['summary'][0]['results'][0]
values=dict(l.split('=',1) for l in Path('/Users/kimdove/robingraph-test/private/audio.env').read_text().splitlines() if '=' in l)
origin='http://192.168.219.97:8000'
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args):return None
op=urllib.request.build_opener(NoRedirect)
rows=[]
for name,method,path,authenticated,range_header in [('private_unauthenticated','GET',r['preview_url'],False,None),('private_head','HEAD',r['preview_url'],True,None),('private_range','GET',r['preview_url'],True,'bytes=0-127'),('unpublished_public_get','GET','/media/audio/'+r['file_sha256']+'.ogg',False,None),('unpublished_public_head','HEAD','/media/audio/'+r['file_sha256']+'.ogg',False,None)]:
 headers={}
 if authenticated:headers['Authorization']='Bearer '+values['ROBINGRAPH_INGEST_INTERNAL_TOKEN']
 if range_header:headers['Range']=range_header
 req=urllib.request.Request(origin+path,method=method,headers=headers)
 try:resp=op.open(req,timeout=15)
 except urllib.error.HTTPError as e:resp=e
 with resp:
  b=resp.read(129) if method!='HEAD' else b''
  rows.append({'check':name,'status':resp.status,'content_type':resp.headers.get('Content-Type'),'content_length':resp.headers.get('Content-Length'),'content_range':resp.headers.get('Content-Range'),'cache_control':resp.headers.get('Cache-Control'),'received_bytes':len(b),'ogg_magic':b.startswith(b'OggS') if name=='private_range' else None})
passed=[x['status'] for x in rows]==[401,200,206,404,404] and rows[2]['received_bytes']==128 and rows[2]['ogg_magic']
out={'candidate_id':r['candidate_id'],'file_sha256':r['file_sha256'],'origin':origin,'rows':rows,'passed':passed,'external_cdn_requests':0,'publication_executed':False}
(w/'private-preview-http.json').write_text(json.dumps(out,indent=2));print(json.dumps(out));assert passed
