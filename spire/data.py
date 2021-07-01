"""
Pydantic schemas for the Spire HTTP API
"""
from pydantic import BaseModel


class PingResponse(BaseModel):
    """
    Schema for ping response.
    """

    status: str


class VersionResponse(BaseModel):
    """
    Schema for responses on /version endpoint.
    """

    version: str
