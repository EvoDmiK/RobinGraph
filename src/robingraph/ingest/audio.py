"""Bounded Commons collection, explicit review, and immutable local audio publication."""
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from hashlib import sha1, sha256
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, HTTPRedirectHandler, build_opener

from robingraph.api.services import ApiError
from robingraph.retrieval.recordings import (
    SOURCE_ID, READ_RECORDINGS, UPSERT_RECORDINGS, reviewed_record, read_recordings, source_allowed, _reviewed_data,
)

STORED_RELEASE = 'commons-stored-reviewed-v1'
MAX_AUDIO_BYTES = 20 * 1024 * 1024
FILE_NAME = re.compile(r'^[a-f0-9]{64}\.(ogg|mp3|wav)$')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Audio provider redirect is not allowed')


def retry_seconds(value, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        seconds = int(value)
    except (ValueError, TypeError):
        try:
            seconds = math.ceil((parsedate_to_datetime(value) - now).total_seconds())
        except (ValueError, TypeError, OverflowError):
            seconds = 600
    return max(1, seconds)


def provider_bytes(url, maximum, opener=None):
    opener = opener or build_opener(NoRedirect())
    started = time.monotonic()
    with opener.open(Request(url, headers={'User-Agent':'RobinGraph/0.1 (reviewed bird audio collection)',
                                          'Accept-Encoding':'identity'}), timeout=15) as response:
        if response.status != 200 or response.headers.get('Content-Encoding', 'identity') != 'identity':
            raise ValueError('Unexpected audio provider response')
        data = bytearray()
        reader = getattr(response,'read1',response.read)
        while True:
            remaining = 30 - (time.monotonic()-started)
            if remaining <= 0:
                raise ValueError('Audio provider read deadline exceeded')
            # read1 closes fp at Content-Length EOF; never reuse its previous socket.
            socket = getattr(getattr(getattr(response,'fp',None),'raw',None),'_sock',None)
            if socket is not None:
                socket.settimeout(min(15,remaining))
            chunk = reader(min(64 * 1024,maximum+1-len(data)))
            if not chunk:
                return bytes(data)
            data.extend(chunk)
            if len(data) > maximum:
                raise ValueError('Audio provider response exceeds request limits')


def validate_file(data, info):
    if not data or len(data) != info.get('size') or sha1(data).hexdigest() != info.get('sha1'):
        raise ValueError('Audio file size or source SHA-1 mismatch')
    mime = info['mime']
    if mime in ('application/ogg','audio/ogg'):
        valid = data.startswith(b'OggS') and (b'OpusHead' in data[:512] or b'\x01vorbis' in data[:512])
        extension, content_type = 'ogg', 'audio/ogg'
    elif mime == 'audio/mpeg':
        valid = data.startswith(b'ID3') or (len(data)>1 and data[0]==255 and data[1]&224==224)
        extension, content_type = 'mp3', 'audio/mpeg'
    elif mime == 'audio/wav':
        valid = data.startswith(b'RIFF') and data[8:12] == b'WAVE'
        extension, content_type = 'wav', 'audio/wav'
    else:
        raise ValueError('Unsupported audio MIME')
    if not valid:
        raise ValueError('Audio container does not match source MIME')
    return sha256(data).hexdigest()+'.'+extension, content_type


class AudioService:
    def __init__(self, store, root, repository, resolve_exact, token):
        if not token or not Path(root).is_absolute():
            raise ValueError('Audio storage requires an absolute persistent root and internal token')
        self.store, self.root, self.repository, self.resolve_exact = store, Path(root), repository, resolve_exact
        self.token = token

    def require_internal_bearer(self, value):
        import secrets
        supplied = value[7:] if value and value.startswith('Bearer ') else ''
        if not supplied or not secrets.compare_digest(supplied,self.token):
            raise ApiError(401,'Unauthorized',{'WWW-Authenticate':'Bearer'})

    @staticmethod
    def result(row):
        if row is None:
            raise ApiError(404,'Audio candidate not found')
        data = row['data']
        result = {'candidate_id':row['id'],'status':row['status'],
                  'scientific_name':row['scientific_name'],'file_title':row['file_title']}
        for key in ('recording','file_sha256','retry_at','review','error_code'):
            if key in data:
                result[key] = data[key]
        if row['status'] == 'deferred':
            until = datetime.fromisoformat(data['retry_at'])
            result['retry_after_seconds'] = max(1, math.ceil((until-datetime.now(timezone.utc)).total_seconds()))
        if 'file_name' in data:
            result['preview_url'] = '/internal/v1/audio/preview/'+row['id']
        return result

    def targets(self, limit=5, after_taxon_id=''):
        from robingraph.retrieval.species_scope import _bundle
        if type(limit) is not int or not 1 <= limit <= 5 or not isinstance(after_taxon_id,str):
            raise ApiError(422,'A target batch must contain between one and five species')
        targets = []
        pending = self.store.pending_species()
        entries = sorted(_bundle()['taxa'].items())
        cursor = None
        for taxon_id, entry in entries:
            if taxon_id <= after_taxon_id or entry['status']!='korea' or entry['scientific_name'] in pending:
                continue
            cursor = taxon_id
            try:
                resolved = self.resolve_exact(entry['scientific_name'])
            except ApiError:
                continue
            if resolved['taxon_id'] != taxon_id:
                continue
            targets.append({'taxon_id':taxon_id,'scientific_name':entry['scientific_name']})
            if len(targets)==limit:
                break
        return {'targets':targets,'next_cursor':cursor if len(targets)==limit else None}

    def discover(self, scientific_name, limit=3):
        if type(limit) is not int or not 1 <= limit <= 3:
            raise ApiError(422,'Discovery is limited to three candidates per species')
        if not isinstance(scientific_name,str) or not re.fullmatch(r'[A-Z][a-z]+ [a-z]+(?:-[a-z]+)?',scientific_name):
            raise ApiError(422,'An exact species name is required')
        self.resolve_exact(scientific_name)
        if not source_allowed():
            raise ApiError(409,'Audio source is not allowed')
        identity = sha256((scientific_name+'\n__discover__').encode()).hexdigest()
        try:
            with self.store.session(collect=True) as cursor:
                until = self.store.cooldown(cursor)
                if until is not None and until > datetime.now(timezone.utc):
                    raise ApiError(429,'Commons retry window is still active',{'Retry-After':str(math.ceil((until-datetime.now(timezone.utc)).total_seconds()))})
                try:
                    url = 'https://commons.wikimedia.org/w/api.php?'+urlencode({
                        'action':'query','format':'json','formatversion':2,'list':'search','srnamespace':6,
                        'srsearch':'filetype:audio "'+scientific_name+'"','srlimit':limit})
                    data = json.loads(provider_bytes(url,1_000_000))
                    if (not isinstance(data,dict) or not isinstance(data.get('query'),dict)
                            or not isinstance(data['query'].get('search'),list)
                            or any(not isinstance(row,dict) for row in data['query']['search'])):
                        raise ValueError('Invalid Commons discovery response')
                    candidates = [{'scientific_name':scientific_name,'file_title':row['title']}
                                  for row in data.get('query',{}).get('search',[])
                                  if isinstance(row.get('title'),str) and row['title'].endswith(('.ogg','.mp3','.wav'))
                                  and re.search(r'(?<![A-Za-z])'+re.escape(scientific_name)+r'(?![A-Za-z])',row['title'].replace('_',' ').replace('-',' '))]
                    return {'scientific_name':scientific_name,'status':'candidates','candidates':candidates[:limit],
                            'verification':'unreviewed_search_results'}
                except HTTPError as error:
                    if error.code!=429:
                        raise ApiError(502,'Commons discovery failed') from None
                    seconds = retry_seconds(error.headers.get('Retry-After'))
                    payload = {'retry_at':(datetime.now(timezone.utc)+timedelta(seconds=seconds)).isoformat(),
                               'error_code':'provider_rate_limited'}
                    self.store.save(cursor,identity,scientific_name,'__discover__','deferred',payload)
                    return self.result({'id':identity,'scientific_name':scientific_name,'file_title':'__discover__',
                                        'status':'deferred','data':payload})
                except (OSError,TimeoutError):
                    raise ApiError(502,'Commons discovery failed') from None
                except (ValueError,KeyError,IndexError,TypeError,AttributeError):
                    raise ApiError(422,'Commons discovery response validation failed') from None
        except BlockingIOError:
            raise ApiError(409,'Audio collection is already running',{'Retry-After':'5'}) from None

    def stage(self, scientific_name, file_title):
        if (not isinstance(scientific_name,str) or not re.fullmatch(r'[A-Z][a-z]+ [a-z]+(?:-[a-z]+)?',scientific_name)
                or not isinstance(file_title,str) or len(file_title)>400 or not file_title.startswith('File:')
                or not file_title.endswith(('.ogg','.mp3','.wav'))):
            raise ApiError(422,'Exact species and Commons audio file title are required')
        if not source_allowed():
            raise ApiError(409,'Audio source is not allowed')
        target = self.resolve_exact(scientific_name)
        identity = sha256((scientific_name+'\n'+file_title).encode()).hexdigest()
        try:
            with self.store.session(collect=True) as cursor:
                previous = self.store.get(cursor,identity)
                if previous is not None and previous['status'] != 'deferred':
                    return self.result(previous)
                until = self.store.cooldown(cursor)
                if until is not None and until > datetime.now(timezone.utc):
                    raise ApiError(429,'Commons retry window is still active',{'Retry-After':str(math.ceil((until-datetime.now(timezone.utc)).total_seconds()))})
                try:
                    url = 'https://commons.wikimedia.org/w/api.php?'+urlencode({
                        'action':'query','format':'json','formatversion':2,'prop':'imageinfo|revisions',
                        'titles':file_title,'iiprop':'url|size|sha1|mime|extmetadata','rvprop':'ids'})
                    metadata = json.loads(provider_bytes(url,1_000_000))
                    pages = metadata.get('query',{}).get('pages',[])
                    if len(pages)!=1 or pages[0].get('missing') or pages[0].get('title')!=file_title:
                        raise ValueError('Exact Commons file page was not returned')
                    page = pages[0]
                    row = {'scientific_name':scientific_name,'title':file_title,'page_id':page['pageid'],
                           'revision_id':page['revisions'][0]['revid'],'imageinfo':page['imageinfo'][0]}
                    now = datetime.now(timezone.utc).isoformat()
                    source_time = now
                    pinned = _reviewed_data()
                    for original in pinned['records']:
                        if (original['scientific_name']==scientific_name and original['title']==file_title
                                and original['imageinfo']==row['imageinfo'] and original['revision_id']==row['revision_id']):
                            row = original
                            source_time = original.get('retrieved_at',pinned['retrieved_at'])
                            break
                    record = reviewed_record(row,source_time)
                    info = row['imageinfo']
                    if type(info.get('size')) is not int or not 0 < info['size'] <= MAX_AUDIO_BYTES:
                        raise ValueError('Audio exceeds the bounded file size')
                    audio = provider_bytes(record['audio_url'],MAX_AUDIO_BYTES)
                    file_name, mime = validate_file(audio,info)
                    self.root.mkdir(parents=True,exist_ok=True)
                    destination = self.root/file_name
                    if destination.exists():
                        if sha256(destination.read_bytes()).hexdigest()!=file_name.split('.')[0]:
                            raise ValueError('Stored audio integrity mismatch')
                    else:
                        descriptor, temporary = tempfile.mkstemp(dir=self.root,prefix='.pending-')
                        try:
                            with os.fdopen(descriptor,'wb') as handle:
                                handle.write(audio); handle.flush(); os.fsync(handle.fileno())
                            os.replace(temporary,destination)
                        finally:
                            if Path(temporary).exists():
                                Path(temporary).unlink()
                    data = {'recording':record,'raw_record':row,'retrieved_at':source_time,'metadata_fetched_at':now,'target':target,
                            'file_name':file_name,'file_sha256':file_name.split('.')[0],'mime':mime}
                    state = 'awaiting_review'
                except HTTPError as error:
                    if error.code != 429:
                        raise ApiError(502,'Commons audio request failed') from None
                    seconds = retry_seconds(error.headers.get('Retry-After'))
                    data = {'retry_at':(datetime.now(timezone.utc)+timedelta(seconds=seconds)).isoformat(),
                            'error_code':'provider_rate_limited','target':target}
                    state = 'deferred'
                except (OSError,TimeoutError):
                    raise ApiError(502,'Commons audio request failed') from None
                except (ValueError, KeyError, IndexError, TypeError) as error:
                    raise ApiError(422,'Audio source validation failed') from error
                self.store.save(cursor,identity,scientific_name,file_title,state,data)
                return self.result({'id':identity,'scientific_name':scientific_name,'file_title':file_title,'status':state,'data':data})
        except BlockingIOError:
            raise ApiError(409,'Audio collection is already running',{'Retry-After':'5'}) from None

    def status(self, candidate_id):
        with self.store.session() as cursor:
            return self.result(self.store.get(cursor,candidate_id))

    def review(self,candidate_id,reviewer,taxon_verified,playback_verified,approved):
        if not isinstance(reviewer,str) or not 1 <= len(reviewer.strip()) <= 120:
            raise ApiError(422,'A reviewer identity is required')
        if type(approved) is not bool or type(taxon_verified) is not bool or type(playback_verified) is not bool:
            raise ApiError(422,'Explicit boolean review decisions are required')
        if approved and not (taxon_verified and playback_verified):
            raise ApiError(409,'Exact species and actual playback must both be reviewed')
        with self.store.session() as cursor:
            row = self.store.get(cursor,candidate_id)
            self.result(row)
            if row['status'] not in ('awaiting_review','approved','rejected'):
                raise ApiError(409,'Candidate is not awaiting a review decision')
            if approved and ('recording' not in row['data'] or 'file_name' not in row['data']):
                raise ApiError(409,'A validated stored recording is required')
            row['data']['review'] = {'reviewer':reviewer.strip(),'taxon_verified':taxon_verified,
                                    'playback_verified':playback_verified,'approved':approved,
                                    'reviewed_at':datetime.now(timezone.utc).isoformat()}
            row['status'] = 'approved' if approved else 'rejected'
            self.store.save(cursor,row['id'],row['scientific_name'],row['file_title'],row['status'],row['data'])
            return self.result(row)

    def publish(self,candidate_id):
        if not source_allowed():
            raise ApiError(409,'Audio source is not allowed')
        with self.store.session() as cursor:
            row = self.store.get(cursor,candidate_id)
            self.result(row)
            if row['status']=='published':
                return self.result(row)
            if row['status']!='approved' or any(row['data'].get('review',{}).get(key) is not True for key in ('approved','taxon_verified','playback_verified')):
                raise ApiError(409,'An explicit approved review is required')
            data = row['data']; target = self.resolve_exact(row['scientific_name'])
            if target != data['target']:
                raise ApiError(409,'Active taxon context changed; review a new candidate')
            self.file(data)
            record = reviewed_record(data['raw_record'],data['retrieved_at'])
            if record != data['recording']:
                raise ApiError(409,'Reviewed source metadata changed')
            node_id = 'commons-stored:'+row['id']
            graph = {'id':node_id,'scientific_name':record['scientific_name'],'asset_uri':record['audio_url'],
                     'landing_uri':record['source_url'],'creator':record['creator'],'publisher':'Wikimedia Commons',
                     'attribution':record['creator']+' · '+record['license_name'],'license_uri':record['license_url'],
                     'format':data['mime'],'metadata_sha256':record['evidence']['metadata_sha256'],
                     'retrieved_at':data['retrieved_at'],'evidence_id':node_id+':'+record['evidence']['metadata_sha256'],
                     'payload_json':json.dumps(record,ensure_ascii=False,sort_keys=True)}
            safe_upsert = UPSERT_RECORDINGS.replace("MERGE (media:MediaAsset:Recording", "WITH row, collect(DISTINCT taxon) AS targets\nWHERE size(targets)=1 AND targets[0].id=$taxon_id\nWITH row, targets[0] AS taxon\nMERGE (media:MediaAsset:Recording")
            count = self.repository._run(safe_upsert,taxon_id=target['taxon_id'],rows=[graph],dataset_id=SOURCE_ID,source_release=STORED_RELEASE,
                                         concept_set_id=target['concept_set_id'],taxonomy_release=target['taxonomy_release'])
            if len(count)!=1 or count[0]['recordings']!=1:
                raise ApiError(409,'Exact reviewed graph target is no longer available')
            row['status']='published'
            self.store.save(cursor,row['id'],row['scientific_name'],row['file_title'],row['status'],data)
            return self.result(row)

    def file(self,data, *, verify=True):
        name = data.get('file_name','')
        if not FILE_NAME.fullmatch(name):
            raise ApiError(404,'Audio file not found')
        path = self.root/name
        if path.is_symlink() or not path.is_file() or (verify and sha256(path.read_bytes()).hexdigest()!=data.get('file_sha256')):
            raise ApiError(404,'Audio file not found')
        return path,data['mime']

    def _validated_stored(self,row,target,graph=None):
        data = row['data']
        if not source_allowed() or data['target'] != target:
            return None
        record = reviewed_record(data['raw_record'],data['retrieved_at'])
        if record != data['recording'] or record['scientific_name'] != row['scientific_name']:
            return None
        if graph is None:
            graph = self.repository._run(READ_RECORDINGS,scientific_name=row['scientific_name'],**target,
                                         dataset_id=SOURCE_ID,source_release=STORED_RELEASE)
        evidence = next((item for item in graph if item.get('id')=='commons-stored:'+row['id']),None)
        if (evidence is None or json.loads(evidence['payload_json']) != record
                or evidence.get('metadata_sha256') != record['evidence']['metadata_sha256']):
            return None
        self.file(data,verify=False)
        return {**record,'audio_url':'/media/audio/'+data['file_name']}

    def media(self,name):
        if not FILE_NAME.fullmatch(name):
            raise ApiError(404,'Audio file not found')
        try:
            for row in self.store.published(file_name=name):
                target = self.resolve_exact(row['scientific_name'])
                if self._validated_stored(row,target) is not None:
                    return self.file(row['data'])
        except Exception:
            # Public bytes require the same current exact-target/evidence chain as profile metadata.
            pass
        raise ApiError(404,'Audio file not found')

    def preview(self,candidate_id):
        with self.store.session() as cursor:
            row = self.store.get(cursor,candidate_id)
            self.result(row)
            return self.file(row['data'])

    def recordings(self,lineage):
        base = read_recordings(self.repository,lineage)
        target = lineage.items[-1]
        if target.rank!='species' or not source_allowed():
            return base
        try:
            stored = self.store.published(scientific_name=target.scientific_name)
            if not stored:
                return base
            graph = self.repository._run(READ_RECORDINGS,taxon_id=target.taxon_id,scientific_name=target.scientific_name,
                                        concept_set_id=lineage.concept_set_id,taxonomy_release=lineage.taxonomy_release,
                                        dataset_id=SOURCE_ID,source_release=STORED_RELEASE)
            combined = {record['id']:record for record in base}
            context = {'taxon_id':target.taxon_id,'concept_set_id':lineage.concept_set_id,
                       'taxonomy_release':lineage.taxonomy_release}
            for row in stored:
                record = self._validated_stored(row,context,graph)
                if record is not None:
                    combined[record['id']]=record
            return list(combined.values())[:3]
        except Exception:
            # Stored enrichment is optional; a PG/disk outage must not hide the reviewed pinned catalog.
            return base
