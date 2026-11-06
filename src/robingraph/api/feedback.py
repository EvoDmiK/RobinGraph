"""Signed, response-specific feedback capabilities; no new application database."""
import logging
import os

from django.core import signing

from .. import tracing
from .schemas import ChatFeedbackRequest
from .services import ApiError

_SALT = "robingraph.chat.feedback"
_MAX_AGE = 24 * 60 * 60


def feedback_headers(trace_id: str | None) -> dict[str, str]:
    experiment_id = tracing.feedback_experiment_id()
    if not trace_id or not experiment_id:
        return {}
    try:
        token = signing.dumps({"trace_id": trace_id, "experiment_id": experiment_id,
                               "target": os.getenv("ROBINGRAPH_DEPLOY_TARGET", "legacy")}, salt=_SALT)
        return {"X-RobinGraph-Trace-Id": trace_id, "X-RobinGraph-Feedback-Token": token,
                "Cache-Control": "no-store"}
    except Exception as error:
        # Feedback availability must never change the answer or leak the capability.
        logging.getLogger(__name__).debug("Feedback token failed (%s)", type(error).__name__)
        return {}


def submit_feedback(request: ChatFeedbackRequest) -> None:
    try:
        data = signing.loads(request.token, salt=_SALT, max_age=_MAX_AGE)
        if (not isinstance(data, dict) or not isinstance(data.get("trace_id"), str)
                or not isinstance(data.get("experiment_id"), str)
                or data.get("target") != os.getenv("ROBINGRAPH_DEPLOY_TARGET", "legacy")):
            raise signing.BadSignature("Invalid feedback context")
    except signing.BadSignature:
        raise ApiError(400, "Feedback link is invalid or expired") from None
    if tracing.feedback_experiment_id() is None:
        raise ApiError(503, "Feedback is temporarily unavailable")
    try:
        tracing.record_feedback(data["trace_id"], data["experiment_id"], request.rating)
    except tracing.FeedbackConflictError:
        raise ApiError(409, "Feedback was already submitted") from None
    except tracing.FeedbackTargetError:
        raise ApiError(400, "Feedback link is invalid or expired") from None
    except Exception as error:
        logging.getLogger(__name__).warning("Feedback save failed (%s)", type(error).__name__)
        raise ApiError(503, "Feedback is temporarily unavailable") from None
