"""Conservative entity spans from the user's text, independent of Jev output."""
import re
import unicodedata


_TOPICS = {
    "subspecies": r"아종|subspecies",
    "profile": r"정보|소개|특징|설명|궁금|알려|어떤\s*새|에\s*대해|에\s*관해|about|profile|information|tell\s+me",
    "taxonomy": r"분류|계통|학명|속은|과는|목은|무슨\s*(?:목|과|속|종)|어느\s*(?:목|과|속|종)|taxonomy|lineage|scientific\s+name",
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
        prefix = re.sub(r"(?:에\s*대한|에\s*대해서|에\s*대해|에\s*관한|에서는|에는|의|은|는|가|와|과|랑|하고)$", "", prefix).strip()
        if re.fullmatch(r"[가-힣]{2,40}", prefix):
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
