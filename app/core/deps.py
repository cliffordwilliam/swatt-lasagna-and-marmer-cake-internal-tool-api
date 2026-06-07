"""Session provider.

This module has API to give `request response unit` (UoW) owner a new Session state, owner can be in arbitrary location too.
This hands off a new Session state to owner, and when owner is done we resume here to send commit to cluster and close the session.
So it does not matter where owner is, we always close it here.
"""

from .database import session


def get_db():
    db = session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
