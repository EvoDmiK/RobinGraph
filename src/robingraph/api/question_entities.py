"""Conservative entity spans from the user's text, independent of Jev output."""
import re
import unicodedata

from ..retrieval.species_questions import bounded_korean_name


_TOPICS = {
    "subspecies": r"아종|subspecies",
    "profile": r"정보|소개|특징|설명|궁금|알려|어떤\s*새|에\s*대해|에\s*관해|about|profile|information|tell\s+me",
    # 속은/과는/목은 must stand alone (황새의 과는), never end a name (황새과는).
    "taxonomy": r"분류|계통|학명|(?<![가-힣])(?:속은|과는|목은)|무슨\s*(?:목|과|속|종)|어느\s*(?:목|과|속|종)|taxonomy|lineage|scientific\s+name",
    "diet": r"먹이|식성|무엇을|뭘|뭐를|먹|diet|eat|feed",
    "habitat": r"서식|어디|habitat|live",
    "activity": r"활동|야행|주행|밤|activity|nocturnal|diurnal|active",
    "appearance": r"생김새|외모|외관|어떻게\s*생|appearance|look",
    "related": r"비슷|관련|같은\s*(?:속|과)|similar|related",
    "ecological_habitat": r"서식|habitat",
    "ecological_diet": r"먹이|식성|diet",
}


def extract_name(question: str, label: str) -> str | None:
    """Return one bounded source substring; ambiguity never becomes a guessed taxon.

    These grammars only locate text. Existence and aliases are checked by the
    existing active taxonomy/name-relation repositories, never by the model.
    """
    if label not in _TOPICS:
        return None
    if re.search(r"그리고|동시에|뿐만\s*아니라|(?<![A-Za-z-])(?:and|or|versus)(?![A-Za-z-])|[,;/\n]", question, re.I):
        return None
    latin = list(re.finditer(r"\b[A-Z][a-z]+ [a-z]+(?: [a-z]+)?\b", question))
    # Require actual binomial formatting; generic English phrases are not names.
    latin = [m for m in latin if m.group().split()[0].lower() not in
             {"tell", "what", "which", "where", "show", "list", "give", "does", "how", "find", "can", "is"}]
    if len(latin) > 1:
        return None
    topic = re.search(_TOPICS[label], question, re.I)
    if topic:
        prefix = question[:topic.start()].strip(" \t'\"“”‘’.,?!")
        prefix = re.sub(r"^(?:혹시\s+|저기\s+|please\s+|tell\s+me\s+about\s+|show\s+me\s+|list\s+the\s+)", "", prefix, flags=re.I)
        prefix = re.sub(r"\s+(?:어떤|무슨|인정된|알려진|전체|모든|하위)$", "", prefix).strip()
        if prefix.casefold() in _reviewed_names():
            return prefix
        # Do not strip final 이: it is part of names such as 부엉이/오목눈이.
        stripped = re.sub(r"(?:에\s*대한|에\s*대해서|에\s*대해|에\s*관한|에서는|에는|의|은|는|가)$", "", prefix).strip()
        if stripped == prefix:
            stripped = _strip_conjunction(prefix, label in _COMPARISON_LABELS or
                                          bool(re.search(r"비슷|같은", question[topic.start():])))
            if stripped is None:
                return None
        prefix = stripped
        if re.fullmatch(r"[가-힣]{2,40}", prefix):
            return prefix
        if bounded_korean_name(prefix):
            return prefix
        if prefix and (prefix.casefold() in _reviewed_names() or _bounded_english_name(prefix)):
            return prefix
    # English topic-first syntax and Korean quoted names need explicit bounds.
    quoted = re.findall(r"(?<!\w)['\"“‘]([^'\"”’]{2,100})['\"”’](?!\w)", question)
    if len(quoted) == 1 and (re.fullmatch(r"[가-힣]{2,40}", quoted[0]) or quoted[0].casefold() in _reviewed_names() or _bounded_english_name(quoted[0])):
        return quoted[0]
    bare = question.strip().rstrip(".!?")
    if _bounded_english_name(bare):
        return bare
    match = re.search(r"\b(?:of|for|about)\s+([^!?\n]{1,80})(?:[!?]|$)", question, re.I)
    if match:
        candidate = match.group(1).strip().rstrip(".")
        if candidate.casefold() in _reviewed_names() or _bounded_english_name(candidate):
            return candidate
    if len(latin) == 1:
        return latin[0].group()
    return None


_COMPARISON_LABELS = frozenset(("related", "ecological_habitat", "ecological_diet"))


def _has_final_consonant(syllable: str) -> bool:
    return "가" <= syllable <= "힣" and (ord(syllable) - 0xAC00) % 28 != 0


def _strip_conjunction(prefix: str, comparison: bool) -> str | None:
    """Remove a final 와/과/랑/이랑/하고 only where it is grammatically a particle.

    와/랑 follow a vowel and 과/이랑 a final consonant, so 황새과 (vowel + 과)
    is a family name, not 황새 + particle. 꿩과 (consonant + 과) is either the
    family or 꿩 + particle; outside comparison questions it is ambiguous.
    """
    match = re.search(r"(?P<stem>[가-힣])(?P<particle>이랑|하고|와|과|랑)$", prefix)
    if not match:
        return prefix
    particle, final = match.group("particle"), _has_final_consonant(match.group("stem"))
    if particle in ("와", "랑") and final or particle == "이랑" and not final:
        return prefix
    if particle == "과" and not final:
        return prefix  # rank ending such as 황새과/오리과
    if particle == "과" and not comparison:
        return None
    return prefix[:match.start("particle")].strip()


def _bounded_english_name(value: str) -> bool:
    """Locate a single name-shaped span; the active taxonomy must verify it.

    No English inventory is hardcoded here. Apostrophes and hyphens occur in
    preferred bird names, while punctuation and conjunction lists are not
    accepted as one entity. This parser does not establish taxon existence.
    """
    return (len(value) <= 80 and
            bool(re.fullmatch(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*['’]?(?:\.)?(?: [^\W\d_]+(?:[-'’][^\W\d_]+)*['’]?(?:\.)?){0,9}", value)) and
            all(c in " -'’." or "LATIN" in unicodedata.name(c, "") for c in value) and
            value.split()[0].casefold() not in
            {"tell", "what", "which", "where", "show", "list", "give", "does", "how", "find", "can", "is", "the", "a", "an"})


def _reviewed_names():
    from ..retrieval.name_relations import reviewed_search_terms
    return reviewed_search_terms()


class AmbiguousNameSpanError(ValueError):
    """A suggested name cannot safely replace this source span."""


def rewrite_name_candidate(question: str, mention: str, scientific_name: str) -> str:
    """Replace a standalone source name, never a substring or a collapsed condition/list."""
    if re.fullmatch(r'[가-힣\s]+', mention):
        compact = ''.join(mention.split())
        if re.search(r'에사는|에서사는|서식하는|서식지|먹는|먹고|먹지|살고|않는|아닌|제외|이면서', compact):
            raise AmbiguousNameSpanError('A condition is embedded in the name')
        from ..retrieval.graph_condition_extractor import _taxon_names
        _, known_species = _taxon_names()
        # An unresolved span containing a complete known name may also contain
        # modifiers or another entity; replacing the whole span would erase them.
        if any(len(name) >= 2 and name != compact and name in compact for name in known_species):
            raise AmbiguousNameSpanError('A known name is embedded in a larger unconfirmed span')
    name = r'\s+'.join(re.escape(part) for part in mention.split())
    particles = r'(?:와|과|랑|이랑|하고|의|은|는|이|가|을|를|에서|에게|에|으로|로|만|도|처럼|보다)'
    boundary = r'(?=$|[^\w]|' + particles + r'(?=$|[^\w]))'
    pattern = r'(?<!\w)' + name + boundary
    # A binomial cannot consume the beginning of an unconfirmed trinomial.
    if re.match(r'[A-Za-z]', mention):
        pattern += r'(?!\s+[a-z])'
    rewritten, count = re.subn(pattern, lambda _: scientific_name, question, count=1)
    if count != 1:
        raise AmbiguousNameSpanError('No standalone source mention')
    return rewritten
