"""Session provider.

This module has API to give `request response unit` (UoW) owner a new Session state, owner can be in arbitrary location too.
This hands off a new Session state to owner, and when owner is done we resume here to send commit or rollback to cluster and close the session.
So it does not matter where owner is, we always clean it up in here.
"""

from .database import session


def get_db():
    # .begin() would auto commit or rollback once at the end
    # This is context manager protocol compliant, so outside the indentation is closes the Session
    with session.begin() as db:
        yield db
