import hashlib
import hmac
import logging

from fastapi import Request

from ..utils.settings import GITHUB_WEBHOOK_SECRET

logger = logging.getLogger(__name__)


async def verify_github_request_p(request: Request) -> bool:
    """
    Verifies the request from GitHub.

    Docs:
    https://docs.github.com/en/free-pro-team@latest/developers/webhooks-and-events/securing-your-webhooks
    """

    if GITHUB_WEBHOOK_SECRET is None:
        raise ValueError(
            "Could not verify request: BUGOUT_SLACK_SIGNING_SECRET environment variable not set"
        )
    signing_secret = str.encode(GITHUB_WEBHOOK_SECRET)

    github_signature = request.headers["x-hub-signature-256"]

    body_bytes = await request.body()
    req_digest = hmac.new(signing_secret, body_bytes, hashlib.sha256).hexdigest()
    request_hash = f"sha256={req_digest}"

    return hmac.compare_digest(request_hash, github_signature)
