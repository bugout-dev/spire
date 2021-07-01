"""
Data required to automatically upgrade Bugout slack installations
"""
from typing import Callable, List

from sqlalchemy.orm import Session

from ..models import SlackOAuthEvent
from . import version_1
from . import version_2
from . import version_3

upgrade_handlers: List[Callable[[Session, SlackOAuthEvent], SlackOAuthEvent]] = [
    version_1.upgrade_one,
    version_2.upgrade_one,
    version_3.upgrade_one,
]
