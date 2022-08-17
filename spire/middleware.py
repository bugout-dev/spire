import os
import logging
import json
from tokenize import group
from typing import Callable, Awaitable, List, Optional

import requests

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response

logger = logging.getLogger(__name__)


class BroodAuthMiddleware(BaseHTTPMiddleware):
    """
    Checks the authorization header on the request. If it represents a verified Brood user,
    create another request and get groups user belongs to, after this
    adds a brood_user attribute to the request.state. Otherwise raises a 403 error.
    """

    def __init__(self, app, whitelist: Optional[List[str]] = None):
        self.whitelist: List[str] = []
        if whitelist is not None:
            self.whitelist = whitelist
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ):
        if request.url.path in self.whitelist:
            return await call_next(request)

        bugout_auth_url = os.environ.get("BUGOUT_AUTH_URL", "").rstrip("/")
        if bugout_auth_url == "":
            logger.error("BROOD_API_URL environment variable was not set")
            return Response(status_code=500, content="Internal server error")

        brood_endpoint = f"{bugout_auth_url}/auth"

        authorization_header = request.headers.get("authorization")
        if authorization_header is None:
            return Response(
                status_code=403, content="No authorization header passed with request"
            )

        headers = {"Authorization": authorization_header}
        user_token_list = authorization_header.split()
        if len(user_token_list) != 2:
            return Response(status_code=403, content="Wrong authorization header")
        user_token: str = user_token_list[-1]
        try:
            # Get user info
            r = requests.get(brood_endpoint, headers=headers)
            r.raise_for_status()
            response = r.json()
            user_id: Optional[str] = response.get("user_id")
            verified: Optional[bool] = response.get("verified")
            if user_id is None:
                logger.error(
                    f"Brood API returned invalid response: {json.dumps(response)}"
                )
                return Response(status_code=500, content="Internal server error")
            if not verified:
                logger.info(
                    f"Attempted journal access by unverified Brood account: {user_id}"
                )
                return Response(
                    status_code=403,
                    content="Only verified accounts can access journals",
                )

            # Get user's group info
            user_group_id_list: Optional[list] = [
                group.get("group_id") for group in response.get("groups")
            ]
            user_group_id_list_owner: Optional[list] = [
                group.get("group_id")
                for group in response.get("groups")
                if group.get("user_type") == "owner"
            ]

        except requests.HTTPError as e:
            logger.error(f"Error interacting with Brood API: {str(e)}")
            return Response(status_code=500, content="Internal server error")
        except Exception as e:
            logger.error(f"Error processing Brood response: {str(e)}")
            return Response(status_code=500, content="Internal server error")

        request.state.auth_headers = headers
        request.state.user_group_id_list_owner = user_group_id_list_owner
        request.state.user_group_id_list = user_group_id_list
        request.state.user_id = user_id
        request.state.token = user_token
        return await call_next(request)
