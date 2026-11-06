"""Condition-keeping follow-up of a successful taxon_traits query: one supported condition is added.

The previous plan travels as a server-signed token; nothing else from the client is trusted, and the
merged plan re-runs the fixed query (a previous page is never filtered). No new application database.
"""
from dataclasses import asdict, dataclass, replace
import os
import re

from ..retrieval.graph_condition_extractor import (_DIET_CONDITIONS, _KOREA, _NEGATION, _UNSUPPORTED, _Claims,
                                                   _claim_taxon, _residual, extract_graph_intent)
from ..retrieval.graph_questions import LIMITATIONS, GraphQuestion, TraitCondition, checked_conditions, condition_label

_SALT = "robingraph.chat.followup"
_MAX_AGE = 60 * 60
# A demonstrative start is the only follow-up signal; without one the question is a new, standalone one.
_MARKER = re.compile(
    r"\s*(?:(?:그럼|그러면)\s*)?"
    r"(?:(?:그|이|저)\s*(?:새|종|결과)들?\s*(?:중|가운데)|그\s*(?:중|가운데)|이\s+(?:중|가운데)|이중(?=에)|"
    r"(?:그|이)\s*결과|여기|거기)(?:에서|에|서)?(?:도|는)?(?![가-힣])\s*,?\s*")
# "한국에서 볼 수 있는" reads as the existing Korea record scope (records, not residency).
_KOREA_SEEN = r"(국내|한국|우리나라)(에서|에)?\s*(?:볼\s*수\s*있는|관찰할\s*수\s*있는|관찰되는)"
_PROMPTS = {
    "context_missing": "이어서 조회할 이전 조건을 찾지 못했습니다. 원하는 조건을 모두 넣어 새로 질문해 주세요.",
    "context_invalid": "이전 조회 조건이 만료되었거나 확인되지 않았습니다. 원하는 조건을 모두 넣어 새로 질문해 주세요.",
    "context_scope_mismatch": "이전 조회와 선택한 종 범위가 달라 조건을 이어받지 않았습니다. 원하는 조건을 모두 넣어 새로 질문해 주세요.",
    "route_conflict": "이전 조건 조회를 이어가려면 개별 종 필터나 다른 조회 유형을 비우고 다시 질문해 주세요.",
    "unsupported_addition": "제외·비교 조건이나 종 사이 관계는 이전 조건에 이어 붙일 수 없습니다. 먹이·서식지·분류군·국내 기록 조건 하나를 알려 주세요.",
    "unresolved_addition": "추가할 조건을 확인하지 못했습니다. 먹이·서식지·분류군·국내 기록 조건 하나를 구체적으로 알려 주세요.",
    "multiple_additions": "이전 조건에는 조건을 한 번에 하나씩 추가할 수 있습니다. 하나만 먼저 알려 주세요.",
    "duplicate_condition": "이미 적용된 조건입니다.",
    "conflicting_condition": "이전 조건과 함께 적용할 수 없는 조건입니다. 바꾸려면 원하는 조건을 모두 넣어 새로 질문해 주세요.",
}


class FollowupRejected(ValueError):
    def __init__(self, reason, plan=None):
        super().__init__(reason)
        self.reason, self.plan = reason, plan

    def prompt(self, species_scope):
        kept = describe(self.plan, species_scope) if self.plan else None
        return _PROMPTS[self.reason] + (f" 유지한 조건: {kept}." if kept else "")


@dataclass(frozen=True)
class FollowupPlan:
    root_question: str
    rank: str | None
    conditions: tuple[TraitCondition, ...]
    scope: str | None = None   # 'korea' once a follow-up added the Korea record scope
    turn: int = 0
    added: str | None = None

    def question(self):
        return GraphQuestion("taxon_traits", (), self.rank, conditions=self.conditions)

    def species_scope(self, requested):
        return self.scope or requested


def followup_text(question):
    """The follow-up remainder ('' for a bare "그중?") when ``question`` starts with a demonstrative, else None."""
    match = _MARKER.match(question)
    return question[match.end():].strip(" \t\n?？!.,~") if match else None


def plan_of(question, graph_question):
    """Plan of an executed taxon_traits/order_fruit query, else None (other kinds are not continued)."""
    if graph_question.kind == "taxon_traits":
        conditions = graph_question.conditions
    elif graph_question.kind == "order_fruit" and graph_question.criterion in _DIET_CONDITIONS:
        conditions = (_DIET_CONDITIONS[graph_question.criterion],)
    else:
        return None
    return FollowupPlan(question[:200], graph_question.rank_name, tuple(conditions))


_SCOPE_LABELS = {"korea": "국내 기록", "outside": "국외 분포", "unknown": "한국 분포 미확인"}


def describe(plan, species_scope):
    scope = _SCOPE_LABELS.get(plan.species_scope(species_scope))
    labels = [plan.rank, *(condition_label(c) for c in plan.conditions), scope]
    return ", ".join(label for label in labels if label)


def _shown(plan, species_scope):
    return {"conditions": [condition_label(c) for c in plan.conditions], "taxon": plan.rank,
            "scope": plan.species_scope(species_scope)} if plan else None


def info(status, species_scope, plan=None, retained=None, reason=None):
    """``plan``: what this response ran or kept; ``retained``: what its followup_context carries next."""
    return {"status": status, "reason": reason, "root_question": plan.root_question if plan else None,
            "added": plan.added if plan and status == "applied" else None,
            "plan": _shown(plan, species_scope), "retained": _shown(retained, species_scope)}


def issue(plan, species_scope):
    """Signed token for ``plan`` or None when signing is unavailable (the answer itself is unaffected)."""
    from django.core import signing

    try:
        return signing.dumps({"v": 1, "q": plan.root_question, "rank": plan.rank,
                              "c": [asdict(c) for c in plan.conditions], "s": plan.scope, "t": plan.turn,
                              "ss": species_scope, "target": os.getenv("ROBINGRAPH_DEPLOY_TARGET", "legacy")},
                             salt=_SALT, compress=True)
    except Exception:
        return None


def read(token, species_scope):
    """Verified plan of ``token``; FollowupRejected for a missing, forged, expired or mismatched one."""
    from django.core import signing

    if not token:
        raise FollowupRejected("context_missing")
    try:
        data = signing.loads(token, salt=_SALT, max_age=_MAX_AGE)
        if not isinstance(data, dict) or data.get("v") != 1 or data.get("target") != os.getenv(
                "ROBINGRAPH_DEPLOY_TARGET", "legacy"):
            raise ValueError
        rank, scope, turn, question = data.get("rank"), data.get("s"), data.get("t"), data.get("q")
        if (not isinstance(question, str) or not question or rank is not None and not (
                isinstance(rank, str) and re.fullmatch(r"[가-힣]+|[A-Z][a-z]+(?: [a-z]+(?:-[a-z]+)?){0,2}", rank))
                or scope not in (None, "korea") or type(turn) is not int or not isinstance(data.get("c"), list)):
            raise ValueError
        plan = FollowupPlan(question, rank, checked_conditions(tuple(TraitCondition(**c) for c in data["c"])),
                            scope, turn)
    except Exception:
        raise FollowupRejected("context_invalid") from None
    if data.get("ss") != species_scope:
        raise FollowupRejected("context_scope_mismatch")
    return plan


def _addition(text):
    """The one (kind, value, label) the follow-up text adds; FollowupRejected otherwise."""
    # "…새만 보여줘": a restriction particle on the target noun, not on a food ("열매만 먹는" stays).
    text = re.sub(_KOREA_SEEN, r"\1\2 기록된", text)
    text = re.sub(r"(?<=[새종것들목과속])만(?=\s*(?:보여|알려|찾아|있|[?.!]|$))", "", text)
    text = re.sub(r"(?<=[가-힣][목과속])인(?=\s)", "", text)   # "참새목인 새"
    intent = extract_graph_intent(text)
    if intent.negation or intent.unsupported or intent.unsupported_food or re.search(_NEGATION, text) or any(
            re.search(pattern, text) for _, pattern in _UNSUPPORTED):
        raise FollowupRejected("unsupported_addition")
    if intent.residual or intent.ambiguity:
        raise FollowupRejected("unresolved_addition")
    if intent.kind in ("taxon_traits", "order_fruit"):
        conditions = ([c for c, _ in intent.conditions] if intent.kind == "taxon_traits"
                      else [_DIET_CONDITIONS[intent.diet]])
        units = [("condition", c, condition_label(c)) for c in conditions]
        if intent.rank:
            units.append(("taxon", intent.rank.text.strip(), intent.rank.text.strip()))
        if intent.scope:
            units.append(("scope", "korea", "국내 기록"))
    elif intent.kind is not None:
        raise FollowupRejected("unsupported_addition")
    else:
        # No trait cue: only a taxon or the Korea scope can be added; every other word blocks.
        claims = _Claims(text)
        claims.each(_KOREA, "scope", "korea")
        _claim_taxon(claims)
        if _residual(claims):
            raise FollowupRejected("unresolved_addition")
        units = [("scope", "korea", "국내 기록") for _ in claims.of("scope")]
        units += [("taxon", claims.span(r).text, claims.span(r).text) for r in claims.of("rank")]
    if not units:
        raise FollowupRejected("unresolved_addition")
    if len(units) > 1:
        raise FollowupRejected("multiple_additions")
    return units[0]


def extend(plan, text, species_scope):
    """``plan`` with the one condition ``text`` adds; every existing condition is kept."""
    try:
        kind, value, label = _addition(text)
    except FollowupRejected as rejected:
        raise FollowupRejected(rejected.reason, plan) from None
    if kind == "scope":
        if plan.scope or species_scope == "korea":
            raise FollowupRejected("duplicate_condition", plan)
        if species_scope != "all":
            raise FollowupRejected("conflicting_condition", plan)
        return replace(plan, scope="korea", turn=plan.turn + 1, added=label)
    if kind == "taxon":
        if plan.rank:
            raise FollowupRejected("duplicate_condition" if plan.rank == value else "conflicting_condition", plan)
        return replace(plan, rank=value, turn=plan.turn + 1, added=label)
    if value in plan.conditions:
        raise FollowupRejected("duplicate_condition", plan)
    try:
        conditions = checked_conditions(plan.conditions + (value,))
    except ValueError:
        raise FollowupRejected("conflicting_condition", plan) from None
    return replace(plan, conditions=conditions, turn=plan.turn + 1, added=label)


KOREA_LIMITATION = LIMITATIONS["korea_record"]
