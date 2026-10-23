"""Rule-based extraction of a GraphIntent from the original question text (RG-207).

Every non-space, non-punctuation character is either consumed by a recognised
slot or a bounded filler (bird nouns, connectors, question endings), or kept
as ``residual`` so the execution gate refuses to run. Negation, season,
quantity, conservation and region words are never fillers. A question with no
graph relation cue is returned as a clean ``GraphIntent(None)`` so the existing
routes keep it. Species stay as original-text spans; the caller's name
resolver decides identity. Kind candidates can only add ``kind_tie``.
"""
from functools import cache
import re

from .graph_intent_schema import KIND_FAMILIES, GraphIntent, Span
from .graph_questions import FOOD_GAPS, HABITATS, TRAIT_CONDITIONS, TraitCondition, checked_conditions
from .graph_semantic_router import PROTOTYPES
from .species_profile import LABELS, SOURCE_CATEGORY, VALUES
from .taxonomy_lineage import reference_korean_names, sourced_korean_names

MAX_QUESTION_CHARS = 200
SOURCE = 'extractor'
# Group words are not one species; a name equal to one of these is ambiguous.
GROUP_WORDS = frozenset(('오리', '기러기', '새', '조류', '물새', '산새', '맹금류', '철새', '텃새', '오리류'))
# Fruits named as the food itself ("감 먹는"); a specific plant, never general fruit.
FRUIT_NOUNS = ('블루베리', '산딸기', '산수유', '마가목', '도토리', '사과', '포도', '버찌', '앵두', '딸기', '머루', '다래',
               '오디', '대추', '홍시', '곶감', '체리', '팥배', '감', '귤', '배')

_HAB = '|'.join(re.escape(k).replace(r'\ ', r'\s*') for k in sorted(HABITATS, key=len, reverse=True))
_LIVE = r'(?:사는|살면서|살고|살며|서식하는|서식하며|서식하고)'
_ASKS = (r'알려\s*(?:줘|줄래|주세요|주실래요)|알려|뭐야|뭐니|뭔가요|무엇인가요|뭐가|무엇이|어떤|어느|게|것들|것|'
         r'있어요|있어|있니|있나요|있을까요|있을까|있습니까|있는지|궁금해요|궁금해|궁금합니다|찾아|줘|주세요|'
         r'보여|해|좀|목록|알고|싶어요|싶어|인가요|일까요|일까|요')
_FILLER = re.compile(rf'(?:(?:새|종류|종|조류)(?:들)?|중(?:에서|에)?|가운데(?:에서)?|에서|{_ASKS}|'
                     r'은|는|이|가|을|를|의|와|과|랑|이랑|하고|처럼|도)+')
_PUNCT = re.compile(r'[^\w]+')
_BIRD_TARGET = re.compile(r'(?<![가-힣])(?:새|종|종류)(?:들)?(?:은|는|이|가|을|를|도)?(?![가-힣])')

_UNSUPPORTED = (
    ('co_occurrence', r'같은\s*곳에서\s*(?:공존하는|공존|사는)|(?:같이|함께)\s*(?:사는|살고|사는\s*곳)|공존(?:하는|하고)?|동소(?:적|성)'),
    ('evolutionary_distance', r'(?:진화적으로|계통적으로|유전적으로)(?:\s*가장)?(?:\s*(?:가까운|먼|비슷한))?|진화\s*거리|유연\s*관계'),
    ('ranking', r'가장\s*(?:비슷한|닮은|가까운|유사한)|순위|유사도|비슷한\s*순서'),
    ('predation', r'잡아먹(?:는|히는|힌|은|어|고)?|포식(?:하는|자는|자)?|사냥하는'),
    ('other', r'먹이\s*경쟁(?:을\s*하는|하는)?|경쟁(?:하는|관계)'),
    # Foods with no composition key in the data (FOOD_GAPS); 곤충/고기/물고기/씨앗/꽃꿀 are data keys.
    ('food', r'(?<![가-힣])(?:' + '|'.join(FOOD_GAPS) + r')(?:을|를)?(?=\s*먹)'),
    ('other', r'(?<![가-힣])어류(?:을|를)?(?=\s*먹)'),   # = 물고기 (fish): a synonym decision, not a data gap
    ('other', r'같은\s*(?:과|목)(?:인|에\s*속하는|의|에)'),
)
_NEGATION = (r'먹지\s*않는|먹지\s*않고|먹지\s*않은|안\s*먹는|안\s*먹고|겹치지\s*않는|겹치지\s*않고|같지\s*않은|같지\s*않고|'
             r'다르지\s*않은|않는|않은|않고|아닌|아니고|아니면서|말고|제외하고|제외한|제외|빼고|뺀|(?<![가-힣])외에|없는|없이')
_RESIDENCY = (r'(?:국내|한국|우리나라)(?:에서|에|으로)?\s*(?:찾아오는|날아오는|오는|사는|서식하는|번식하는|월동하는|머무는)|'
              r'(?:해외|외국|국외|외래)(?:에서만|에만|에서|에|의)?(?:\s*(?:있는|사는|서식하는|분포하는))?')
_KOREA = (r'(?:국내|한국|우리나라)(?:에서|에)?\s*관찰된(?:\s*적\s*(?:이\s*)?있는)?|'
          r'(?:국내|한국|우리나라)(?:에서|에)?\s*(?:관찰\s*)?기록(?:된\s*적\s*있는|이\s*있는|된|이)(?:\s*있는)?')
_COMMON = (r'공통\s*(?:상위\s*)?분류(?:군)?(?:가|는|를|이|은)?|공통된\s*분류(?:가|는|를)?|분류상\s*공통점(?:이|은)?|'
           r'분류(?:상|학적으로|적으로)?\s*(?:어떤|무슨)\s*(?:관계|사이)(?:야|니|인가요|인가|예요|에요|인지|일까|이야|입니까)?|'
           r'(?:어떤|무슨)\s*(?:관계|사이)(?:야|니|인가요|인가|예요|에요|인지|일까|이야|입니까)?|'
           r'분류\s*(?:계통|경로)?(?:을|를)?\s*비교(?:해\s*줘|해줘|해\s*주세요|해\s*봐)?|'
           r'같은\s*(?:과|목|속)(?:야|이야|인가요|일까요|일까|인지|이니|입니까|이에요|예요|이냐)')
_GENUS = (r'(?:같은|동일한)\s*속(?:으로\s*분류되는|에\s*(?:속하는|속한|들어가는)|이면서|이고|인|의|이|에|으로)?|'
          r'(?<![가-힣])속이\s*(?:같은|같고|동일한)')
_TWO_HABITATS = rf'(?:{_HAB})\s*(?:이랑|랑|과|와|하고|이나|나|및|,)\s*(?:{_HAB})(?:에서|에)?\s*{_LIVE}'
_HABITAT = rf'(?<![가-힣])({_HAB})(?:에서|에)?\s*{_LIVE}'
_HABITAT_SUBJECT = r'(?<![가-힣])(?:서식지|서식\s*환경|사는\s*곳|사는\s*데)(?:가|는|도|이|를|와|은)?'
_SAME_HABITAT = r'같은\s*서식지(?:인데|이면서|이고|에서\s*사는|에\s*사는|를\s*공유하는)?'
_HABITAT_REL = r'겹치는데|겹치면서|겹치지만|겹치고|겹치는|같은데|같으면서|같지만|같고|같은|동일한|일치하는'
_SAME_FRUIT = r'(?:같은|똑같은|동일한)\s*열매'
_FRUGIVORE = (r'과실식(?:성)?(?:을|인|이|의|이면서|이고|이며)?(?:\s*하는)?(?:\s*범주(?:인|의|이면서|이고|이며)?)?|'
              r'열매\s*섭식(?:\s*범주)?(?:인|의|을|하는|이면서|이고|이며|이자)?')
_TREE_FRUIT = r'(?<![가-힣])나무\s*열매(?:를|을|는)?'
_FRUIT = r'열매(?:를|을|는)?'
_SAME_NICHE = r'같은\s*먹이\s*(?:생태\s*)?범주(?:를|의|에)?(?:\s*공유하는)?|같은\s*먹이(?:를)?\s*(?:먹는|공유하는)|같은\s*식성(?:을|의)?'
_NICHE_SUBJECT = (r'(?<![가-힣])(?:먹이\s*(?:생태\s*)?범주|먹이\s*습성|식성|먹이|먹는\s*(?:건|것은|것이|게))'
                  r'(?:가|는|도|를|이|의|은)?')
_NICHE_SAME = r'같은데|같으면서|같지만|같고|같은|공유하는|동일한'
_NICHE_DIFFERENT = r'다르면서|다르지만|다르고|다른|달라'
_EAT = r'먹고\s*사는|먹고사는|먹는다|먹는|먹고|먹어|먹을|먹으며'
_LATIN = r'(?<![A-Za-z])[A-Z][a-z]+ [a-z]+(?![a-z])'
# An explicit literature/observation request is another route's question, even with graph words in it.
_DOCUMENT_REQUEST = r'논문|문헌|연구|기사|출처|인용|관찰\s*기록|관찰|사진|영상'
# ...unless it is a second, independent request next to a graph list request: then clarify.
_SECOND_REQUEST = r'(?:알려|보여|찾아)\s*주고|그리고|(?:논문|문헌|연구|기사|출처|인용|관찰\s*기록|관찰|사진|영상)(?:도|까지)'
_CONJ = re.compile(r'(.+?)(이랑|하고|처럼|와|과|랑)$')
_PARTICLE = re.compile(r'(.+?)(?:의|는|은|이|가|를|을|와|과|랑|이랑|하고|처럼|도)?$')


def _final_consonant(char):
    return '가' <= char <= '힣' and (ord(char) - 0xAC00) % 28 != 0


class _Claims:
    def __init__(self, question):
        self.q = question
        self.items = []          # (start, end, role, value)

    def free(self, start, end):
        return start < end and all(end <= s or start >= e for s, e, _, _ in self.items)

    def add(self, start, end, role, value=None):
        if self.free(start, end):
            self.items.append((start, end, role, value))
            return True
        return False

    def each(self, pattern, role, value=None, group=0):
        for match in re.finditer(pattern, self.q):
            self.add(match.start(group), match.end(group), role, value)

    def of(self, role):
        return sorted((i for i in self.items if i[2] == role), key=lambda i: i[0])

    def span(self, item):
        return Span(self.q[item[0]:item[1]], item[0], item[1])

    def unclaimed(self, start, end):
        """Maximal unclaimed (start, end) runs inside [start, end)."""
        runs, cursor = [], start
        for s, e, _, _ in sorted(self.items, key=lambda item: item[:2]):
            if e <= start or s >= end:
                continue
            if s > cursor:
                runs.append((cursor, s))
            cursor = max(cursor, e)
        if cursor < end:
            runs.append((cursor, end))
        return runs


def _tokens(question):
    return [(m.start(), m.end()) for m in re.finditer(r'\S+', question)]


@cache
def _spaced_names():
    """Compact forms of source-checked Korean names that contain a space (청둥 오리 -> 청둥오리 only if sourced)."""
    return frozenset(re.sub(r'\s+', '', item['name']) for item in sourced_korean_names().values()
                     if isinstance(item, dict) and isinstance(item.get('name'), str))


def _extend_name(claims, tokens, index, name_start, tail):
    """Earliest start joining up to 3 preceding whole unclaimed tokens whose compact text is a sourced name."""
    best = name_start
    for back in range(1, 4):
        if index - back < 0:
            break
        p_start, p_end = tokens[index - back]
        if claims.unclaimed(p_start, p_end) != [(p_start, p_end)] or not re.fullmatch(r'[가-힣]+', claims.q[p_start:p_end]):
            break
        if re.sub(r'\s+', '', claims.q[p_start:name_start]) + tail in _spaced_names():
            best = p_start
    return best


def _valid_name(text):
    text = text.strip()
    if re.fullmatch(_LATIN, text):
        return True
    return (bool(re.fullmatch(r'[가-힣]{1,12}(?:\s[가-힣]{1,12}){0,3}', text)) and not _FILLER.fullmatch(text.replace(' ', ''))
            and text.replace(' ', '') not in {k.replace(' ', '') for k in HABITATS} and not text.endswith('목'))


def _relation_after(claims, end, pattern):
    """(start, end) of a relation word right after ``end``, optionally past one token."""
    match = re.match(rf'\s*(?:\S+\s+)?({pattern})(?![가-힣])', claims.q[end:])
    if match:
        return end + match.start(1), end + match.end(1)
    return None


def _claim_relations(claims):
    for match in re.finditer(_SAME_HABITAT, claims.q):
        claims.add(match.start(), match.end(), 'habitat', 'target')
    for match in re.finditer(_HABITAT_SUBJECT, claims.q):
        if not claims.free(match.start(), match.end()):
            continue
        relation = _relation_after(claims, match.end(), _HABITAT_REL)
        if relation and claims.free(*relation):
            claims.add(match.start(), match.end(), 'habitat', 'target')
            claims.add(*relation, 'habitat_relation', 'same')
        elif re.match(r'\s*(?:\S+\s+)?(?:겹치지|같지|다르지)', claims.q[match.end():]):
            claims.add(match.start(), match.end(), 'habitat', 'target')
    for match in re.finditer(_SAME_NICHE, claims.q):
        claims.add(match.start(), match.end(), 'niche', 'same')
    for match in re.finditer(_NICHE_SUBJECT, claims.q):
        if not claims.free(match.start(), match.end()):
            continue
        for pattern, value in ((_NICHE_SAME, 'same'), (_NICHE_DIFFERENT, 'different'), ('비슷한', 'similar')):
            relation = _relation_after(claims, match.end(), pattern)
            if relation and claims.free(*relation):
                claims.add(match.start(), match.end(), 'niche_subject', value)
                claims.add(*relation, 'niche', value)
                break


@cache
def _taxon_names():
    """Korean names a taxon span can be: pinned order/family/genus labels and source-checked species names.

    These only find a span; the rank and identity are decided against the active taxonomy at execution.
    """
    higher = {label['name'] for key, label in reference_korean_names().items()
              if key.split(':', 1)[0] in ('order', 'family', 'genus')}
    species = {item['name'] for item in sourced_korean_names().values() if isinstance(item, dict)}
    return (frozenset(n for n in higher if re.fullmatch(r'[가-힣]+', n)),
            frozenset(n for n in species if re.fullmatch(r'[가-힣]+', n)))


# What may follow a taxon inside its token, or start the next token ("까마귀과면서", "참새목 중에서", "Corvus에 속하는").
_TAXON_JOIN = r'이면서|면서|이고|이며|며|이자|에서|에|의'
_TAXON_NEXT = r'\s*(?:중|가운데|에\s*속(?:한|하는))'
_SCIENTIFIC = r'(?<![A-Za-z])([A-Z][a-z]+(?: [a-z]+(?:-[a-z]+)?){0,2})(?![A-Za-z])'


def _claim_taxon(claims):
    """One taxon span at any rank; never absorbs a modifier before it (겨울에만 까마귀과 -> 겨울에만 stays residual)."""
    for match in re.finditer(_SCIENTIFIC, claims.q):
        after = claims.q[match.end():]
        joined = re.match(rf'(?:{_TAXON_JOIN})(?![가-힣])|{_TAXON_NEXT}', after)
        if ' ' in match.group(1) and not joined:
            continue   # a bare binomial is a species name for the other kinds ("Anas platyrhynchos와 같은 속")
        if ' ' not in match.group(1) and re.match(r'[가-힣]', after) and not joined and not _FILLER.fullmatch(
                re.match(r'[가-힣]*', after).group()):
            continue
        claims.items = [i for i in claims.items if not (i[2] == 'latin' and i[0] == match.start())]
        if claims.add(match.start(), match.end(), 'rank', bool(joined)) and joined and not joined.group().startswith(' '):
            claims.add(match.end(), match.end() + joined.end(), 'filler')
    higher, species = _taxon_names()
    for start, end in _tokens(claims.q):
        token = claims.q[start:end]
        for cut in range(len(token), 0, -1):
            stem, rest = token[:cut], token[cut:]
            legacy_order = bool(re.fullmatch(r'[가-힣]+목', stem))
            if not (stem in higher or stem in species or legacy_order):
                continue
            after = claims.q[start + cut:]
            if re.match(r'\s*열매', after) or not claims.free(start, start + cut):   # 마가목 열매: a plant
                break
            if stem in species and stem not in higher and not legacy_order:
                # A species is only a scope with an explicit scope link, never a topic particle ("까마귀는 …").
                if not (re.fullmatch(r'이면서|면서|이고|이며|며|이자', rest) or (not rest and re.match(_TAXON_NEXT, after))):
                    break
            elif rest and not (re.fullmatch(_TAXON_JOIN, rest) or _FILLER.fullmatch(rest)):
                break
            # `linked`: an explicit scope link follows ("…면서", "… 중", "…에 속하는"), not a topic particle.
            linked = bool(re.fullmatch(r'이면서|면서|이고|이며|며|이자|에서', rest) or (not rest and re.match(_TAXON_NEXT, after))
                          or (rest == '에' and re.match(r'\s*속(?:한|하는)', after[1:])))
            claims.add(start, start + cut, 'rank', linked)
            if rest:
                claims.add(start + cut, end, 'filler')
            break
    for item in claims.of('rank'):
        position = item[1] + (claims.q[item[1]:item[1] + 1] == '에')
        connector = re.match(r'\s*속(?:한|하는)', claims.q[position:])
        if connector:
            claims.add(position, position + connector.end(), 'filler')


# --- trait conditions (taxon_traits) -------------------------------------------------------
# Surfaces are only the existing display vocabulary (species_profile.VALUES/LABELS, HABITATS); nothing invented.
# A bare surface shared by several traits (잡식, 사체 섭식) needs its trait named, else it is ambiguous.
_LINK = r'(?:성)?(?:\s*범주)?(?:을\s*하는|를\s*하는|하는|하면서|하며|하고|인|이고|이며|이면서|면서|이자|의|이|가)?'
_TRAIT_LABELS = {**{LABELS[name]: name for name, spec in TRAIT_CONDITIONS.items() if spec[1] == 'text'},
                 '서식지': 'habitat', '서식지 밀도': 'habitat_density_category', '생활 방식': 'primary_lifestyle',
                 '먹이 범주': 'trophic_niche'}


def _pattern(surface):
    return re.escape(surface).replace(r'\ ', r'\s*').replace('·', r'\s*[·,]?\s*')


def _trait_surfaces(name):
    if name == 'habitat':
        return {**{VALUES[v]: v for v in TRAIT_CONDITIONS[name][2]}, **HABITATS}
    values = TRAIT_CONDITIONS[name][2]
    # The display ("곤충 (원자료: 무척추동물)"), its source name and its short form when that names one value only
    # (곤충 -> invertebrate; 고기 is 'meat' itself, never one of its components).
    short = {}
    for value in values:
        short.setdefault(VALUES[value].split(' (')[0], []).append(value)
    surfaces = {word: found[0] for word, found in short.items() if len(found) == 1}
    surfaces.update({SOURCE_CATEGORY[v]: v for v in values if v in SOURCE_CATEGORY})
    return {**surfaces, **{VALUES[v]: v for v in values}}


_BARE = {}
for _name, _spec in TRAIT_CONDITIONS.items():
    if _spec[1] == 'text' and _name != 'habitat':   # a bare habitat word needs 사는/서식하는 (_HABITAT)
        for _surface, _value in _trait_surfaces(_name).items():
            _BARE.setdefault(_surface, []).append((_name, _value))
            if _surface.endswith(' 생활'):   # 나무 위 생활 -> "나무 위에서 생활하는" (the same display value)
                _BARE.setdefault(_surface[:-len(' 생활')] + '에서 생활', []).append((_name, _value))
_BARE.pop(VALUES['Frugivore'])   # 열매 섭식/과실식 stay with the established fruit criteria
_SHARE_WORDS = {word: key for word, key in _trait_surfaces('diet_distribution').items() if key != 'fruit'}
_SHARE_WORDS['척추동물'] = 'meat'   # original group name remains a searchable alias; fish/carrion are separate


def _measure_names():
    """Measurement surfaces from the display labels: "X (Y)" is also written "X Y" or "X(Y)"; a bare "X"
    is kept only when one field has it (다리 길이 -> tarsus; 부리 길이 is culmen or nares -> None, ambiguous)."""
    names, bases = {}, {}
    for name, spec in TRAIT_CONDITIONS.items():
        if spec[1] != 'number':
            continue
        label = LABELS[name]
        names[label] = name
        inner = re.fullmatch(r'(.+?)\s*\((.+)\)', label)
        if inner:
            base, qualifier = inner.groups()
            names[f'{base} {qualifier}'] = names[f'{base}({qualifier})'] = name
            bases.setdefault(base, set()).add(name)
    for base, fields in bases.items():
        names.setdefault(base, next(iter(fields)) if len(fields) == 1 else None)
    # Shorter everyday forms of the same labels (몸무게 = 체중; 접은 날개 길이 = 날개 길이).
    names.update({'몸무게': 'body_mass', '날개 길이': 'wing_length', '부척 길이': 'tarsus_length',
                  '부리 전체 길이': 'beak_length_culmen'})
    return names


_MEASURES = _measure_names()
_UNITS = {'kg': ('g', 1000), '킬로그램': ('g', 1000), '킬로': ('g', 1000), 'g': ('g', 1), '그램': ('g', 1),
          'mm': ('mm', 1), '밀리미터': ('mm', 1), 'cm': ('mm', 10), '센티미터': ('mm', 10), '센티': ('mm', 10),
          'm': ('mm', 1000), '미터': ('mm', 1000)}
# A whole plain number only: a sign, separator, exponent or decimal point touching it rejects the phrase,
# so "-1g", "1,000g", ".5g", "1e3g" stay residual instead of losing a character as filler.
_NUM = r'(?<![\d.,\-−+eE])\d+(?:\.\d+)?(?![\d.,eE])'
_UNIT = '|'.join(sorted(map(re.escape, _UNITS), key=len, reverse=True))
_BIGGER = r'보다\s*(?:큰|무거운|긴|넓은|높은|두꺼운)'
_SMALLER = r'보다\s*(?:작은|가벼운|짧은|좁은|낮은|얇은)'
_OPS = rf'이상|이하|초과|미만|넘는|넘고|넘으며|{_BIGGER}|{_SMALLER}'
_MEASURE_RE = '|'.join(_pattern(m) for m in sorted(_MEASURES, key=len, reverse=True))
_MEASURE = re.compile(rf'(?P<measure>{_MEASURE_RE})\s*(?:이|가|은|는)?\s*(?:'
                      rf'(?P<lo>{_NUM})\s*(?P<lounit>{_UNIT})?\s*(?:~|에서|부터)\s*(?P<hi>{_NUM})\s*(?P<hiunit>{_UNIT})\s*(?:사이|까지)?'
                      rf'|(?P<num>{_NUM})\s*(?P<unit>{_UNIT})\s*(?P<op>{_OPS})'
                      rf'(?:\s*(?:이고|이며|이면서|면서)?\s*(?P<num2>{_NUM})\s*(?P<unit2>{_UNIT})\s*(?P<op2>{_OPS}))?)'
                      r'(?:인|이고|이며|이면서|면서|의)?(?![가-힣A-Za-z])')


def _op(word):
    word = re.sub(r'\s+', '', word)
    if word.startswith('보다'):
        return 'num_gt' if re.fullmatch(_BIGGER.replace(r'\s*', ''), word) else 'num_lt'
    return {'이상': 'num_gte', '이하': 'num_lte', '초과': 'num_gt', '미만': 'num_lt'}.get(word, 'num_gt')


def _measure_conditions(match):
    """TraitConditions of one measurement phrase, or None when the unit or measure is unclear."""
    name = next(v for k, v in _MEASURES.items() if re.fullmatch(_pattern(k), match.group('measure')))
    if name is None:
        return None
    unit = TRAIT_CONDITIONS[name][2]
    bounds = ([(match.group('lo'), match.group('lounit') or match.group('hiunit'), 'num_gte'),
               (match.group('hi'), match.group('hiunit'), 'num_lte')] if match.group('lo') else
              [(match.group('num'), match.group('unit'), _op(match.group('op')))]
              + ([(match.group('num2'), match.group('unit2'), _op(match.group('op2')))] if match.group('num2') else []))
    conditions = []
    for number, written, op in bounds:
        base, factor = _UNITS[written]
        if base != unit:
            return None   # 체중 30cm: never guessed
        conditions.append(TraitCondition(name, op, None, round(float(number) * factor, 6), unit))
    return conditions


def _claim_conditions(claims):
    """Qualified ("먹이 생태 범주가 잡식인"), measured and bare category conditions; ambiguous ones are kept as such."""
    for label, name in sorted(_TRAIT_LABELS.items(), key=lambda item: len(item[0]), reverse=True):
        surfaces = _trait_surfaces(name)
        values = '|'.join(_pattern(v) for v in sorted(surfaces, key=len, reverse=True))
        for match in re.finditer(rf'(?<![가-힣]){_pattern(label)}\s*(?:이|가|은|는)?\s*({values}){_LINK}(?![가-힣])', claims.q):
            value = next(v for k, v in surfaces.items() if re.fullmatch(_pattern(k), match.group(1)))
            if name == 'habitat':
                claims.add(match.start(), match.end(), 'habitat', value)
            else:
                claims.add(match.start(), match.end(), 'cond', TraitCondition(name, 'eq', value))
    for match in _MEASURE.finditer(claims.q):
        conditions = _measure_conditions(match)
        if conditions is None:
            claims.add(match.start(), match.end(), 'cond_ambiguous')
        else:
            for index, condition in enumerate(conditions):
                if index == 0:
                    claims.add(match.start(), match.end(), 'cond', condition)
                else:
                    claims.items.append((match.start(), match.end(), 'cond', condition))
    words = '|'.join(_pattern(w) for w in sorted(_SHARE_WORDS, key=len, reverse=True))
    for match in re.finditer(rf'(?<![가-힣])({words})(?:을|를|도)?(?=\s*(?:먹|섭취))', claims.q):
        key = next(v for k, v in _SHARE_WORDS.items() if re.fullmatch(_pattern(k), match.group(1)))
        claims.add(match.start(), match.end(), 'cond', TraitCondition('diet_distribution', 'share_gt', key, 0))
    bare = '|'.join(_pattern(w) for w in sorted(_BARE, key=len, reverse=True))
    for match in re.finditer(rf'(?<![가-힣])({bare}){_LINK}(?:\s*서식지(?:에\s*사는|에서\s*사는|의|인)?)?(?![가-힣])',
                             claims.q):
        options = next(v for k, v in _BARE.items() if re.fullmatch(_pattern(k), match.group(1)))
        if len(options) == 1:
            claims.add(match.start(), match.end(), 'cond', TraitCondition(options[0][0], 'eq', options[0][1]))
        else:
            claims.add(match.start(), match.end(), 'cond_ambiguous')


_ROUTED_KINDS = frozenset(kind for kind, _ in PROTOTYPES)
_DIET_CONDITIONS = {
    'frugivore': TraitCondition('trophic_niche', 'eq', 'Frugivore'),
    'fruit_share': TraitCondition('diet_distribution', 'share_gt', 'fruit', 0),
    'tree_fruit_share': TraitCondition('diet_distribution', 'share_gt', 'fruit', 0, qualifier='tree_fruit'),
}


# Modifiers and adverbs before 열매 are conditions (residual), not plant names.
_NOT_PLANT = frozenset(('대부분', '주로', '많이', '조금', '가끔', '자주', '최근', '보통', '항상', '모두', '전부', '특히',
                        '오직', '여러', '다른', '모든', '각종', '여름', '겨울', '봄', '가을', '제철'))


def _plant_word(word):
    return word not in _NOT_PLANT and word[-1] not in '에의을를이가은는도만로와과랑인한운된던적서'


def _claim_plants(claims):
    for match in re.finditer(_SAME_FRUIT, claims.q):
        claims.add(match.start(), match.end(), 'plant')
    for match in re.finditer(r'열매', claims.q):
        if not claims.free(match.start(), match.end()):
            continue
        before = claims.q[:match.start()].rstrip()
        run = re.search(r'[가-힣]+$', before)
        if not run:
            continue
        start, end = run.start(), run.end()
        runs = claims.unclaimed(start, end)
        if not runs or runs[-1][1] != end:
            continue
        start = runs[-1][0]
        word = claims.q[start:end]
        if word == '나무' or _FILLER.fullmatch(word) or not _plant_word(word):
            continue
        claims.add(start, end, 'plant')
    nouns = '|'.join(FRUIT_NOUNS)
    claims.each(rf'(?<![가-힣])({nouns})(?:을|를)?(?=\s*먹)', 'plant', group=1)


def _claim_names(claims, cue_starts):
    names = []
    tokens = _tokens(claims.q)
    for index, (start, end) in enumerate(tokens):
        runs = claims.unclaimed(start, end)
        if not runs or runs[0][0] != start:
            continue
        run_start, run_end = runs[0]
        match = _CONJ.match(claims.q[run_start:run_end])
        if not match or run_end != end:
            continue
        name, particle = match.group(1), match.group(2)
        latin = bool(re.search(r'[a-z]$', name))
        if not latin:
            final = _final_consonant(name[-1])
            if (particle in ('와', '랑') and final) or (particle in ('과', '이랑') and not final):
                continue
        name_start = _extend_name(claims, tokens, index, run_start, name) if not latin else run_start
        text = claims.q[name_start:run_start + len(name)]
        if _valid_name(text) and claims.add(name_start, run_start + len(name), 'name'):
            claims.add(run_start + len(name), run_end, 'filler')
            names.append(name_start)
    # A name right before a relation cue, with no conjunction ("청둥오리 같은 속", "흰뺨검둥오리의 공통 분류").
    for cue, needs_no_conj in cue_starts:
        if needs_no_conj and names:
            continue
        before = [t for t in tokens if t[1] <= cue]
        if not before:
            continue
        start, end = before[-1]
        runs = claims.unclaimed(start, end)
        if runs != [(start, end)]:
            continue
        match = _PARTICLE.match(claims.q[start:end])
        name = match.group(1)
        name_start = _extend_name(claims, tokens, len(before) - 1, start, name)
        if _valid_name(claims.q[name_start:start + len(name)]) and claims.add(name_start, start + len(name), 'name'):
            claims.add(start + len(name), end, 'filler')
            names.append(name_start)


def _residual(claims):
    spans = []
    for start, end in _tokens(claims.q):
        for run_start, run_end in claims.unclaimed(start, end):
            text = claims.q[run_start:run_end]
            core = _PUNCT.sub('', text)
            if not core or _FILLER.fullmatch(core):
                continue
            # Trim punctuation at the edges so the span is the content itself.
            lead = len(text) - len(text.lstrip('?!.,~？'))
            trail = len(text.rstrip('?!.,~？'))
            spans.append(Span(text[lead:trail], run_start + lead, run_start + trail))
    return spans


def _extract(question):
    claims = _Claims(question)
    claims.each(_LATIN, 'latin')
    for code, pattern in _UNSUPPORTED:
        claims.each(pattern, 'unsupported', code)
    claims.each(_NEGATION, 'negation')
    claims.each(_RESIDENCY, 'residual')
    claims.each(_KOREA, 'scope', 'korea')
    claims.each(_COMMON, 'common')
    claims.each(_GENUS, 'genus', 'same')
    _claim_conditions(claims)
    claims.each(_TWO_HABITATS, 'habitat2')
    for match in re.finditer(_HABITAT, question):
        claims.add(match.start(), match.end(), 'habitat', HABITATS[re.sub(r'\s+', ' ', match.group(1))]
                   if re.sub(r'\s+', ' ', match.group(1)) in HABITATS else HABITATS.get(match.group(1)))
    _claim_relations(claims)
    _claim_taxon(claims)
    claims.each(_FRUGIVORE, 'diet', 'frugivore')
    claims.each(_TREE_FRUIT, 'diet', 'tree_fruit_share')
    _claim_plants(claims)
    claims.each(_FRUIT, 'fruit_word')
    for scope in claims.of('scope'):
        group = re.match(r'\s*([가-힣]{1,10}?)\s*중(?:에서|에)?(?![가-힣])', question[scope[1]:])
        if group and not _FILLER.fullmatch(group.group(1)):
            claims.add(scope[1] + group.start(1), scope[1] + group.end(1), 'group')

    documents = [m for m in re.finditer(_DOCUMENT_REQUEST, question) if claims.free(m.start(), m.end())]
    if documents and not re.search(_SECOND_REQUEST, question):
        return GraphIntent(None, source=SOURCE)
    unsupported = sorted({'other' if i[3] == 'food' else i[3] for i in claims.of('unsupported')}
                         ) if _BIRD_TARGET.search(question) else []
    # Kept apart only while every unsupported claim is a food, so another unsupported relation keeps the clarify.
    foods = claims.of('unsupported')
    foods = tuple(Span(claims.q[s:e].removesuffix('을').removesuffix('를'), s, e - (claims.q[e - 1] in '을를'))
                  for s, e, _, _ in foods) if unsupported and all(i[3] == 'food' for i in foods) else ()
    if foods and claims.of('cond_ambiguous'):
        foods = ()   # 부리 길이 30mm: an unreadable condition is never carried into the guidance
    if foods and claims.of('cond'):
        try:
            checked_conditions(tuple(dict.fromkeys(c[3] for c in claims.of('cond'))))
        except ValueError:
            foods = ()   # 100g 이상 50g 이하
    plants, commons, genus = claims.of('plant'), claims.of('common'), claims.of('genus')
    diets, fruit_words, niches = claims.of('diet'), claims.of('fruit_word'), claims.of('niche')
    habitats = claims.of('habitat')
    conds, vague = claims.of('cond'), claims.of('cond_ambiguous')
    if fruit_words and not plants:
        diets = sorted(diets + [(s, e, 'diet', 'fruit_share') for s, e, _, _ in fruit_words])
    share_eaten = any(c[3].op == 'share_gt' for c in conds)
    if diets or plants or claims.of('unsupported') or share_eaten:
        claims.each(_EAT, 'filler')
    habitat_codes = [h for h in habitats if h[3] != 'target']
    # Trait conditions on a taxon or on "새": habitat alone counts only without a species relation (habitat_*_diet).
    scoped_ask = bool(claims.of('rank') or _BIRD_TARGET.search(question))
    traits = bool(diets or conds or vague) or bool((habitat_codes or claims.of('habitat2')) and not niches and scoped_ask)
    # A measurement word with a number ("체중 -1g", "체중 100 이상") is a trait ask even when it cannot be read.
    traits = traits or bool(re.search(_MEASURE_RE, question) and scoped_ask
                            and re.search(rf'\d|{_OPS}|{_UNIT}|NaN|Infinity|무한', question, re.IGNORECASE))
    if traits and len(conds + vague + habitat_codes + diets) > 1:
        claims.each(r'(?<![가-힣])(?:및|그리고)(?![가-힣])', 'filler')
    cue = bool(unsupported or plants or commons or genus or traits or niches
               or any(h[3] == 'target' for h in habitats))
    if not cue and any(r[3] for r in claims.of('rank')) and (_residual(claims) or claims.of('residual')):
        # "까마귀과 중 야행성인 새": a taxon scope with words no condition reads is held, not sent elsewhere.
        cue = traits = True
    if not cue:
        return GraphIntent(None, source=SOURCE)

    cue_starts = [(c[0], False) for c in commons]
    cue_starts += [(c[0], True) for c in genus + niches + claims.of('niche_subject') + plants]
    cue_starts += [(h[0], True) for h in habitats if h[3] == 'target']
    _claim_names(claims, sorted(cue_starts))
    names = [claims.span(i) for i in sorted(claims.of('name') + claims.of('latin'))]

    if unsupported:
        kind = None
    elif plants:
        kind = 'specific_fruit'
    elif commons:
        kind = 'common_taxonomy'
    elif genus:
        kind = 'korea_same_genus' if claims.of('scope') else 'same_genus'
    elif traits and not niches:
        # The established order shape keeps order_fruit; any other taxon, several conditions or none -> taxon_traits.
        taxa = claims.of('rank')
        legacy = (diets and len({d[3] for d in diets}) == 1 and len(taxa) == 1 and not habitats and not conds
                  and not vague and re.fullmatch(r'[가-힣]+목|[A-Z][a-z]+formes', claims.span(taxa[0]).text))
        kind = 'order_fruit' if legacy else 'taxon_traits'
    elif niches:
        kind = 'habitat_different_diet' if niches[0][3] == 'different' else 'habitat_shared_diet'
    else:
        kind = None

    ambiguity, evidence = [], []
    rank_claims = claims.of('rank')
    # Differing values for one condition, or two kinds of request, are never resolved by picking one.
    families = [bool(commons), bool(genus), bool(niches), traits and not plants, bool(plants)]
    if (claims.of('habitat2') or len(claims.of('rank')) > 1 or len({h[3] for h in habitats}) > 1
            or len({d[3] for d in diets}) > 1 or len({claims.q[p[0]:p[1]] for p in plants}) > 1 or sum(families) > 1):
        ambiguity.append('other')
    if len({n[3] for n in niches}) > 1:
        ambiguity.append('relation_unclear')
    if any(n[3] == 'similar' for n in niches):
        ambiguity.append('relation_unclear')
    if any(re.sub(r'\s+', '', n.text) in GROUP_WORDS for n in names):
        ambiguity.append('name_ambiguous')
    if kind == 'taxon_traits' and (not _BIRD_TARGET.search(question) and not rank_claims
                                   or (fruit_words and not re.search(_EAT, question)) or vague):
        ambiguity.append('other')   # "열매" alone is not a list request; 잡식/부리 길이/30cm 체중 are unclear
    need = {'common_taxonomy': 2, 'same_genus': 1, 'korea_same_genus': 1, 'habitat_shared_diet': 1,
            'habitat_different_diet': 1}.get(kind)
    if need and len(names) != need:
        ambiguity.append('other')

    residual = sorted([claims.span(i) for i in claims.of('residual')] + _residual(claims), key=lambda span: span.start)
    groups = claims.of('group')
    group = None
    if groups and kind == 'korea_same_genus':
        group = claims.span(groups[0])
    else:
        residual += [claims.span(g) for g in groups]
    rank = claims.of('rank')
    scope = claims.of('scope')
    diet = relation = habitat = None
    conditions = []
    if kind == 'order_fruit':
        diet = diets[0][3]
        evidence.append(('diet', claims.span(diets[0])))
    elif kind == 'taxon_traits':
        found = ([(_DIET_CONDITIONS[d[3]], claims.span(d)) for d in diets]
                 + [(TraitCondition('habitat', 'eq', h[3]), claims.span(h)) for h in habitat_codes]
                 + [(c[3], claims.span(c)) for c in conds])
        seen = set()
        conditions = sorted(((c, span) for c, span in found if not (c in seen or seen.add(c))),
                            key=lambda item: item[1].start)   # one condition per meaning, first span kept
        try:
            checked_conditions(tuple(c for c, _ in conditions))
        except ValueError:
            ambiguity.append('other')   # 숲+습지, 100g 이상 50g 이하: contradictory, never one picked
    elif kind in ('habitat_shared_diet', 'habitat_different_diet'):
        diet, relation = 'niche', 'different' if niches[0][3] == 'different' else 'same'
        subject = claims.of('niche_subject')
        evidence += [('diet', claims.span(subject[0] if subject else niches[0])), ('relation', claims.span(niches[0]))]
    elif kind in ('same_genus', 'korea_same_genus'):
        relation = 'same'
        evidence.append(('relation', claims.span(genus[0])))
    if habitats and len({h[3] for h in habitats}) == 1 and kind != 'taxon_traits':   # there it is a condition
        habitat = habitats[0][3]
        evidence.append(('habitat', claims.span(habitats[0])))
    if scope:
        evidence.append(('scope', claims.span(scope[0])))
    negation = [claims.span(i) for i in claims.of('negation')]
    if kind is None and not (negation or residual or unsupported or ambiguity):
        return GraphIntent(None, source=SOURCE)
    if kind is None:
        return GraphIntent(None, negation=tuple(negation), residual=tuple(residual), unsupported=tuple(unsupported),
                           ambiguity=tuple(dict.fromkeys(ambiguity)), source=SOURCE,
                           unsupported_food=() if names else foods)   # 벌레와 곡식: a name-like token is unread
    return GraphIntent(
        kind, tuple(names), claims.span(rank[0]) if rank else None, group, diet, habitat, relation,
        'korea' if scope else None, claims.span(plants[0]) if plants else None, tuple(negation), tuple(residual),
        tuple(unsupported), tuple(dict.fromkeys(ambiguity)), tuple(evidence), SOURCE,
        tuple(conditions))


def extract_graph_intent(question, candidates=()):
    """GraphIntent of ``question`` (source='extractor'); never raises.

    ``candidates`` (KindCandidates or ()) can only add ``kind_tie`` when a confident top kind disagrees.
    """
    if not isinstance(question, str) or not question.strip():
        return GraphIntent(None, source=SOURCE)
    try:
        intent = _extract(question)
        if len(question.strip()) > MAX_QUESTION_CHARS and intent != GraphIntent(None, source=SOURCE):
            # A long question with graph conditions is not handed to other routes with them dropped.
            return GraphIntent(None, ambiguity=('other',), source=SOURCE)
        top = getattr(candidates, 'top', None)
        # The router can only dispute kinds it has prototypes for; for another kind its top is just the
        # nearest of the modelled ones, not evidence (TEST Jina: 직박구리과면서 열매… -> specific_fruit 0.945).
        if (intent.kind in _ROUTED_KINDS and top is not None and top != intent.kind
                and not any({top, intent.kind} <= family for family in KIND_FAMILIES)):
            intent = GraphIntent(**{**intent.__dict__, 'ambiguity': intent.ambiguity + ('kind_tie',)})
        return intent
    except Exception:
        # A bug or a broken candidates object must not run anything; the gate turns this into clarify.
        return GraphIntent(None, ambiguity=('other',), source=SOURCE)
