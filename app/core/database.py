"""Database interaction setup.

This module creates Engine once in this worker heap, provision Session generator in heap, defines the mapped class base class.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Creates Engine once in this worker process heap, so that everything can access it
# This Engine manages database connection pool
engine = create_engine("postgresql://user:password@localhost/mydb", echo=True)

# The goal is for each `request response` unit to have one session tied to its lifetime
# The reasoning is that session is `request response` unit's UoW state
# This lives in heap so everyone can access it
# This is to be used in a `try finally` block so that when owner is out of scope it clean itself up
session = sessionmaker(engine)


# This is the base class of all `mapped classes` (Python classes that represent database tables in ORM-centric code)
# The goal is that they must all extend it so that they auto register themselves to MetaData
# `mapped classes` must be in MetaData to allow you to use Python objects intead of raw SQL to talk to database
class Base(DeclarativeBase):
    pass
