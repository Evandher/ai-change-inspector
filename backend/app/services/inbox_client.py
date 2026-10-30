"""MCP -> local web service. No provider key or environment variables cross this boundary."""

from urllib.parse import urlsplit
from uuid import uuid4

from httpx2 import Client as HttpClient
from httpx2 import HTTPError
from pydantic import ValidationError

from app.feedback_models import ReviewFeedback
from app.inspection_models import ChangeScope, InspectionError
from app.local_settings import loopback_url, web_url
from app.review_models import ReviewDetail
from app.services.git_capture import AuthorizedRepository

MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class SubmissionError(InspectionError):
    def __init__(self, code: str, message: str, review_id: str, review_url: str, confirmed: bool):
        super().__init__(code, message)
        self.review_id = review_id
        self.review_url = review_url
        self.confirmed = confirmed


def submit_review(
    repository: AuthorizedRepository,
    scope: ChangeScope,
    text: str,
    base_url: str,
    parent_review_id: str | None = None,
) -> ReviewDetail:
    base = loopback_url(base_url)
    identifier = str(uuid4())
    local_url = f"{web_url()}/reviews/{identifier}"
    confirmed = False

    def request(client: HttpClient, path: str, body: dict, timeout: float) -> ReviewDetail:
        with client.stream("POST", base + path, json=body, timeout=timeout) as response:
            data = bytearray()
            for chunk in response.iter_bytes(chunk_size=64 * 1024):
                data.extend(chunk)
                if len(data) > MAX_RESPONSE_BYTES:
                    raise ValueError("Local response too large")
            if response.status_code not in (200, 201):
                # Never echo an untrusted HTTP body or internal traceback to the agent.
                raise SubmissionError(
                    "web_service_rejected",
                    "La web rechazó la solicitud; revisa su configuración.",
                    identifier,
                    local_url,
                    confirmed,
                )
            detail = ReviewDetail.model_validate_json(bytes(data))
            if detail.review_id != identifier:
                raise ValueError("Unexpected review ID")
            address = urlsplit(detail.review_url)
            loopback_url(f"{address.scheme}://{address.netloc}")
            if address.path != f"/reviews/{identifier}" or address.query or address.fragment:
                raise ValueError("Unexpected local review URL")
            return detail

    try:
        with HttpClient(
            trust_env=False, follow_redirects=False, headers={"X-Inspector-Request": "1"}
        ) as client:
            registered = request(
                client,
                "/api/reviews",
                {
                    "review_id": identifier,
                    "repository": repository.name,
                    "repository_root": str(repository.root),
                    "scope": scope,
                    "diff": text,
                    **({"parent_review_id": parent_review_id} if parent_review_id else {}),
                },
                timeout=5,
            )
            if registered.review_id != identifier:
                raise ValueError("Unexpected review ID")
            local_url = registered.review_url
            confirmed = True
            return request(client, f"/api/reviews/{identifier}/analyze", {}, timeout=90)
    except SubmissionError:
        raise
    except (HTTPError, ValueError, ValidationError) as exc:
        message = (
            "La revisión quedó registrada. No se confirmó el análisis; "
            "consulta su URL antes de repetir."
            if confirmed
            else "No se confirmó el registro. Inicia la web y consulta este ID antes de repetir; "
            "podría existir si se perdió la respuesta. No se llamó a Meta desde MCP."
        )
        raise SubmissionError(
            "web_service_unavailable", message, identifier, local_url, confirmed
        ) from exc


def fetch_feedback(
    repository: AuthorizedRepository, review_id: str, base_url: str
) -> ReviewFeedback:
    """Read one authorized review, with no write requests or provider calls."""
    base = loopback_url(base_url)
    try:
        with HttpClient(trust_env=False, follow_redirects=False, timeout=10) as client:
            with client.stream("GET", f"{base}/api/reviews/{review_id}/feedback") as response:
                if response.status_code != 200:
                    code = {404: "review_not_found", 403: "unauthorized_repository"}.get(
                        response.status_code, "web_service_rejected"
                    )
                    raise InspectionError(
                        code,
                        "Feedback is unavailable for this authorized repository.",
                        blocked=response.status_code == 403,
                    )
                data = bytearray()
                for chunk in response.iter_bytes(chunk_size=64 * 1024):
                    data.extend(chunk)
                    if len(data) > MAX_RESPONSE_BYTES:
                        raise ValueError("Feedback response too large")
                feedback = ReviewFeedback.model_validate_json(bytes(data))
                if (feedback.review_id, feedback.repository, feedback.repository_root) != (
                    review_id,
                    repository.name,
                    str(repository.root),
                ):
                    raise InspectionError(
                        "unauthorized_repository",
                        "Review does not match the authorized repository.",
                        blocked=True,
                    )
                address = urlsplit(feedback.review_url)
                loopback_url(f"{address.scheme}://{address.netloc}")
                if address.path != f"/reviews/{review_id}" or address.query or address.fragment:
                    raise ValueError("Unexpected review URL")
                return feedback
    except (HTTPError, ValueError, ValidationError) as exc:
        raise InspectionError(
            "web_service_unavailable", "Could not read feedback from the local web service."
        ) from exc
