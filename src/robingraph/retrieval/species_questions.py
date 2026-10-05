"""Bounded natural-language species questions and answers from attributed facts."""
from dataclasses import dataclass
import math
import re
from urllib.parse import urlsplit

from .species_profile import VALUES


@dataclass(frozen=True)
class SpeciesQuestion:
    name: str
    topic: str
    category: str | None = None


_NAME = r'(?P<name>[가-힣]+?|[A-Za-z][a-z]+\s+[a-z]+(?:\s+[a-z]+)?)'
_ASK = r'(?:알려\s*줘|알려\s*주세요|설명해\s*줘|설명해\s*주세요|알고\s*싶어(?:요)?)'
_WHAT = r'(?:뭐야|뭔가요|무엇인가요|어떤\s*거야|어떤가요)'
_PATTERNS = (
    ('ecological_related', 'trophic_niche', rf'{_NAME}(?:와|과|랑|하고)\s*(?:먹이|먹이\s*생태|식성)(?:가|이)?\s*(?:비슷한|같은)\s*(?:새|종)(?:는|은|이|가)?\s*(?:(?:어떤\s*(?:게|것|종|새)(?:가)?\s*)?(?:있니|있어(?:요)?|있나요)|{_ASK})?'),
    ('ecological_related', 'habitat', rf'{_NAME}(?:와|과|랑|하고)\s*(?:서식\s*환경|서식지)(?:가|이)?\s*(?:비슷한|같은)\s*(?:새|종)(?:는|은|이|가)?\s*(?:(?:어떤\s*(?:게|것|종|새)(?:가)?\s*)?(?:있니|있어(?:요)?|있나요)|{_ASK})?'),
    ('related', None, rf'{_NAME}(?:와|과|랑|하고)\s*(?:비슷한|관련된)\s*(?:새|종)(?:들)?(?:은|는|이|가)?\s*(?:(?:어떤\s*(?:게|것|종|새)(?:가)?\s*)?(?:있니|있어(?:요)?|있나요)|{_ASK})?'),
    ('related', None, rf'{_NAME}(?:와|과|랑|하고)\s*같은\s*(?P<rank>속|과)(?:에\s*속하는|의)?\s*(?:새|종)(?:은|는|이|가)?\s*(?:(?:어떤\s*(?:게|것|종|새)(?:가)?\s*)?(?:있니|있어(?:요)?|있나요)|{_ASK})?'),
    ('diet', None, rf'{_NAME}(?:은|는|이|가)?\s*(?:무엇을|뭘|뭐를|뭐|어떤\s*(?:먹이|음식)(?:를|을))\s*먹(?:고\s*(?:사니|살아(?:요)?|살까요)|어(?:요)?|니|나요|습니까|는지\s*{_ASK})'),
    ('diet', None, rf'{_NAME}(?:의|은|는)?\s*(?:먹이|식성|먹이\s*유형|먹이\s*생태)(?:는|가|에\s*대해)?\s*(?:{_WHAT}|{_ASK})'),
    ('habitat', None, rf'{_NAME}(?:은|는|이|가)?\s*어디(?:에서|에|서)?\s*(?:살아(?:요)?|사니|사나요|살고\s*있니|살고\s*있나요)'),
    ('habitat', None, rf'{_NAME}(?:의|은|는)?\s*(?:서식지|서식\s*환경)(?:는|은|가|이|에\s*대해)?\s*(?:{_WHAT}|{_ASK})'),
    ('activity', None, rf'{_NAME}(?:은|는|이|가)?\s*(?:야행성이니|야행성인가요|야행성이야|밤에\s*활동해(?:요)?|밤에\s*활동하니|언제\s*활동하니|언제\s*활동해(?:요)?)'),
    ('activity', None, rf'{_NAME}(?:의)?\s*활동\s*시간(?:은|이|에\s*대해)?\s*(?:{_WHAT}|{_ASK})'),
    ('appearance', None, rf'{_NAME}(?:은|는|이|가)?\s*(?:어떻게\s*생겼니|어떻게\s*생겼어(?:요)?)'),
    ('appearance', None, rf'{_NAME}(?:의)?\s*(?:외관|외모|생김새|외관적\s*특징)(?:는|은|가|이|에\s*대해)?\s*(?:{_WHAT}|{_ASK})'),
)
_COMPILED = tuple((topic, category, re.compile(pattern)) for topic, category, pattern in _PATTERNS)


def parse_species_question(question):
    normalized = re.sub(r'\s+', ' ', question.strip()).rstrip('.!?？').strip()
    for topic, category, pattern in _COMPILED:
        match = pattern.fullmatch(normalized)
        if match:
            rank = match.groupdict().get('rank')
            return SpeciesQuestion(match.group('name').strip(), topic, {'속':'genus','과':'family'}.get(rank, category))
    return None


def _sourced(item):
    if (not isinstance(item, dict) or not isinstance(item.get('source_name'),str)
            or not item['source_name'].strip()):
        return False
    try:
        url = urlsplit(item.get('source_url') or '')
        return url.scheme in ('https','http') and bool(url.hostname) and not url.username
    except (TypeError, ValueError):
        return False


def focused_answer(profile, question, relations=None):
    """Use only own attributed fields; never infer diet from a broad niche."""
    label = next((profile.get('taxon',{}).get(k) for k in ('korean_name','english_name','scientific_name')
                  if profile.get('taxon',{}).get(k)), question.name)
    title = {'diet':'먹이와 식성','habitat':'서식 환경','activity':'활동 시간',
             'appearance':'외관적 특징','related':'비슷한 종','ecological_related':'생태가 비슷한 종'}[question.topic]
    items = []
    traits = [t for t in profile.get('traits',[]) if _sourced(t) and not t.get('inferred')]
    if question.topic == 'diet':
        distribution = next((t for t in traits if t.get('name')=='diet_distribution' and isinstance(t.get('value'),dict)), None)
        if distribution:
            for key, amount in distribution['value'].items():
                if (key in ('invertebrate','endotherm_vertebrate','ectotherm_vertebrate','fish','unknown_vertebrate','carrion','fruit','nectar','seed','other_plant') and isinstance(amount,(int,float)) and not isinstance(amount,bool)
                        and math.isfinite(amount) and 0 < amount <= 100):
                    items.append({**distribution,'text':f'{VALUES[key]} {amount:g}% (자료의 먹이 구성비)'})
        if not items:
            for name in ('diet_category','trophic_niche'):
                trait = next((t for t in traits if t.get('name')==name and isinstance(t.get('value'),str) and t['value'] in VALUES), None)
                if trait:
                    items.append({**trait,'text':f"{trait['label']}: {trait['display']} (자료의 범주)"})
    elif question.topic in ('habitat','activity'):
        allowed = ('habitat','habitat_density_category') if question.topic=='habitat' else ('activity_pattern','nocturnal')
        for trait in traits:
            if trait.get('name') in allowed and isinstance(trait.get('display'),str) and trait['display'].strip() and trait.get('display') not in ('자료 없음','번역 확인 필요'):
                items.append({**trait,'text':f"{trait['label']}: {trait['display']}"})
    elif question.topic == 'appearance':
        for section in profile.get('sections',[]):
            if section.get('key')=='appearance':
                items.extend(item for item in section.get('items',[]) if _sourced(item) and item.get('text'))
    elif relations is not None:
        for group in relations.get('groups',[]):
            if question.category and group.get('relation' if question.topic=='ecological_related' else 'rank') != question.category:
                continue
            source = group.get('source') or group
            if not _sourced(source):
                continue
            peers = [p for p in group.get('items',[]) if p.get('rank')=='species']
            names = [p.get('korean_name') or p.get('english_name') or p.get('scientific_name') for p in peers]
            if any(names):
                group_label = group.get('label') or '같은 생태 범주의 새'
                category = f" · {group['display']}" if group.get('display') else ''
                
                if question.topic == 'ecological_related':
                    for peer in peers:
                        evidence = peer.get('evidence')
                        if _sourced(evidence):
                            peer_label = peer.get('korean_name') or peer.get('english_name') or peer.get('scientific_name')
                            items.append({**evidence,'text':f'{group_label}{category}: {peer_label}'})
                else:
                    items.append({**source,'text':f"{group_label}{category}: {', '.join(n for n in names if n)}"})
    if items:
        if question.topic=='diet':
            text=f'{label}의 자료에서 확인되는 먹이는 다음과 같습니다. 구성비는 해당 자료의 분류값이며 모든 지역·계절의 식단을 뜻하지 않습니다.'
        elif question.topic=='related':
            text=f'{label}와 같은 속·과에 속하는 종을 그래프에서 찾았습니다. 분류상 관련 종이며 외형 유사도나 가장 가까운 계통의 순위는 아닙니다.'
        elif question.topic=='ecological_related':
            text=f'{label}와 같은 자료의 생태 범주를 공유하는 종을 찾았습니다. 실제 공존이나 포식 관계를 뜻하지 않습니다.'
        else:
            text=f'{label}의 출처로 확인한 {title}입니다.'
    else:
        text=f'{label}의 {title}에 관한 출처가 확인된 자료를 현재 제공하지 못했습니다.'
    return {'topic':question.topic,'title':f'{label} · {title}','text':text,
            'items':items,'relations':relations}, bool(items)
