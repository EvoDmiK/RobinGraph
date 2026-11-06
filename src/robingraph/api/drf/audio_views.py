"""Opt-in internal audio operations and hash-addressed same-origin playback."""
import re
import asyncio
from django.http import HttpResponse, StreamingHttpResponse
from rest_framework.response import Response
from .views import RobinGraphView
from .validation import read_json_body
from ..services import ApiError


class AudioOperationView(RobinGraphView):
    http_method_names = ['post']
    audio = None

    def post(self,request,action):
        self.audio.require_internal_bearer(request.META.get('HTTP_AUTHORIZATION'))
        body = read_json_body(request)
        allowed = {
            'targets':({'limit','after_taxon_id'},set()),
            'discover':({'scientific_name','limit'},{'scientific_name'}),
            'stage':({'scientific_name','file_title'},{'scientific_name','file_title'}),
            'status':({'candidate_id'},{'candidate_id'}),
            'review':({'candidate_id','reviewer','taxon_verified','playback_verified','approved'},
                      {'candidate_id','reviewer','taxon_verified','playback_verified','approved'}),
            'publish':({'candidate_id'},{'candidate_id'}),
        }
        if action not in allowed:
            raise ApiError(404,'Not Found')
        optional,required = allowed[action]
        if not isinstance(body,dict) or not required <= body.keys() or body.keys()-optional:
            raise ApiError(422,'Invalid audio operation fields')
        if 'candidate_id' in body and (not isinstance(body['candidate_id'],str) or not re.fullmatch('[a-f0-9]{64}',body['candidate_id'])):
            raise ApiError(422,'Invalid audio candidate ID')
        result = getattr(self.audio,action)(**body)
        if result.get('status')=='deferred':
            return Response(result,status=429,headers={'Retry-After':str(result['retry_after_seconds'])})
        return Response(result)


def audio_response(request,path,mime,*,private=False):
    size = path.stat().st_size
    start,end,status = 0,size-1,200
    headers = {'Accept-Ranges':'bytes','X-Content-Type-Options':'nosniff',
               'Cache-Control':'private, no-store' if private else 'public, max-age=31536000, immutable'}
    value = request.META.get('HTTP_RANGE')
    if value:
        match = re.fullmatch(r'bytes=(\d*)-(\d*)',value)
        if len(value)>128 or not match or not any(match.groups()):
            return HttpResponse(status=416,headers={**headers,'Content-Range':f'bytes */{size}'})
        first,last = match.groups()
        if first:
            start = int(first); end = min(int(last),size-1) if last else size-1
        else:
            length = int(last)
            if length==0:
                return HttpResponse(status=416,headers={**headers,'Content-Range':f'bytes */{size}'})
            start = max(0,size-length)
        if start>=size or start>end:
            return HttpResponse(status=416,headers={**headers,'Content-Range':f'bytes */{size}'})
        status=206;headers['Content-Range']=f'bytes {start}-{end}/{size}'
    headers['Content-Length']=str(end-start+1)
    if request.method=='HEAD':
        return HttpResponse(status=status,content_type=mime,headers=headers)
    async def chunks():
        with path.open('rb') as handle:
            handle.seek(start);remaining=end-start+1
            while remaining:
                chunk=await asyncio.to_thread(handle.read,min(64*1024,remaining))
                if not chunk:
                    break
                remaining-=len(chunk)
                yield chunk
    return StreamingHttpResponse(chunks(),status=status,content_type=mime,headers=headers)


class AudioMediaView(RobinGraphView):
    http_method_names=['get','head']
    audio=None
    private=False

    def get(self,request,name):
        if self.private:
            self.audio.require_internal_bearer(request.META.get('HTTP_AUTHORIZATION'))
            path,mime=self.audio.preview(name)
        else:
            path,mime=self.audio.media(name)
        return audio_response(request,path,mime,private=self.private)

    head=get
