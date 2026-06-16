# SQLAlchemy 2.0 Study Notes

## Overview

SQLAlchemy is presented as two distinct APIs, one building on top of the other:

- **Core** — foundational toolkit. Manages database connectivity, sends queries, handles responses. Imported from `sqlalchemy` namespace.
- **ORM** — optional layer built on top of Core. Maps Python classes to DB tables, manages object state. Imported from `sqlalchemy.orm` namespace.

In SQLAlchemy 2.0 the line between Core and ORM is blurred — ORM queries now use Core's `select()` construct directly. You don't choose one or the other; real applications mix both.

---

## Setup

```toml
# pyproject.toml dependencies
dependencies = ["sqlalchemy", "psycopg2-binary"]
```

```bash
uv add sqlalchemy psycopg2-binary
uv sync

# Provision a PostgreSQL container on a non-default port to avoid conflicts
docker run --rm --name study-db \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=mydb \
  -p 5433:5432 \
  -d postgres:16
```

---

## Engine

Every SQLAlchemy application starts with an `Engine`. It is the central source of connections to a database and manages the **connection pool**.

```python
from sqlalchemy import create_engine

# URL shape: dialect+driver://user:password@host:port/dbname
# driver is optional, defaults to psycopg2 for postgresql
engine = create_engine(
    "postgresql+psycopg2://user:password@localhost:5433/mydb",
    echo=True  # logs all SQL to stdout, good for learning only
)
```

Key points:
- **Lazy initialization** — the Engine does not connect on creation. It connects only when a query needs to be made.
- The Engine is typically a **global object**, created once per process per database.
- `echo=True` lets you see the raw SQL being sent, including the dialect handshake queries on first connection.

---

## Connection and Transactions

### `engine.connect()` — commit as you go

```python
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text("SELECT x, y FROM some_table"))
    print(result.all())
    conn.commit()  # must commit explicitly, otherwise implicit ROLLBACK on exit
```

- `engine.connect()` implicitly starts a transaction on first query (`BEGIN (implicit)`)
- If you don't call `commit()`, a `ROLLBACK` is sent when the `with` block exits
- This pattern is called **commit as you go**

### `engine.begin()` — begin once

```python
with engine.begin() as conn:
    conn.execute(text("INSERT INTO some_table (x, y) VALUES (:x, :y)"), {"x": 1, "y": 1})
# auto COMMIT on clean exit, auto ROLLBACK on exception
```

- Prefer this for writes — intention is clear upfront, commit/rollback is automatic
- This pattern is called **begin once**

---

## Result Object

`conn.execute()` returns a `Result` object — a **cursor**, not a list. It is a one-time-use stream of rows. Once consumed it is exhausted.

```python
result = conn.execute(text("SELECT x, y FROM some_table"))

# Four ways to access rows — all lazy iterators except .all()
for x, y in result:          # tuple unpacking
for row in result: row[0]    # index
for row in result: row.x     # attribute (named tuple)
for row in result.mappings(): row["x"]  # dict-like

# Materialize everything into memory at once
rows = result.all()          # returns a real Python list, consumes the cursor
```

The full stack underneath:
```
Result          ← SQLAlchemy wrapper (what you interact with)
  └─ cursor     ← psycopg2 cursor (DBAPI level)
       └─ TCP connection to PostgreSQL
```

---

## Session (ORM)

When using the ORM, use `Session` instead of `Connection`. Session uses Connection under the hood but adds:

- **Identity map** — load the same row twice, get the same Python object
- **Unit of Work** — tracks all Python object mutations, generates SQL on `commit()`
- **Relationship navigation** — access related objects directly as Python attributes

```python
from sqlalchemy.orm import Session

with Session(engine) as session:
    with session.begin():
        session.execute(...)
# auto commit on clean exit, auto rollback on exception, session closed after
```

### Session provider pattern (e.g. for FastAPI)

```python
"""Session provider.
Hands off a new Session state to the owner (request handler),
resumes here after to commit and close. Owner can be anywhere.
"""
from sqlalchemy.orm import sessionmaker

SessionLocal = sessionmaker(bind=engine)

def get_db():
    with SessionLocal.begin() as session:
        yield session
# commit or rollback and close handled automatically by context managers
```

---

## Database Metadata

SQLAlchemy uses Python objects to represent database tables. These are called **database metadata**.

- `MetaData` — container that holds all Table objects, one per application
- `Table` — represents a database table
- `Column` — represents a column, accessible via `Table.c.column_name`

```python
from sqlalchemy import MetaData, Table, Column, Integer, String, ForeignKey

metadata = MetaData()

user_table = Table(
    "user_account",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(30)),           # String(30) = VARCHAR(30), max 30 chars
    Column("fullname", String),           # no length constraint
)

address_table = Table(
    "address",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("email", String, nullable=False),
    # ForeignKey auto-infers the column type from the target (Integer from user.id)
    Column("user_id", ForeignKey("user_account.id"), nullable=False),
)

# Emit DDL — creates all tables registered to this metadata, handles FK ordering
# Safe to call multiple times, checks if tables exist first
metadata.create_all(engine)

# Drop all tables in reverse order
metadata.drop_all(engine)
```

Notes:
- `create_all` / `drop_all` are good for testing. Use **Alembic** for production migrations.
- Reserved words like `user` get auto-quoted by SQLAlchemy (`"user"`). Better to name tables `users`.
- On PostgreSQL, `Integer` primary keys become `SERIAL` (auto-increment) automatically — dialect abstraction at work.

---

## ORM Mapped Classes (Declarative Table)

The ORM way to define tables. Instead of creating `Table` objects directly, you create Python classes that map to tables. This gives you:

- Python type annotations that reflect DB column types
- IDE type checking and LSP support
- Objects that Session can track and manage

### Declarative Base

```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
# Base.metadata — the MetaData collection, auto-created
# Base.registry — tracks mapped classes and their relationships
```

### Mapped Classes

```python
from typing import Optional, List
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

class User(Base):
    __tablename__ = "user_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30))   # NOT NULL
    fullname: Mapped[Optional[str]]                  # nullable

    # NOT a DB column — Python-level navigation only
    addresses: Mapped[List["Address"]] = relationship(back_populates="user")

class Address(Base):
    __tablename__ = "address"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str]
    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"))

    # NOT a DB column — Python-level navigation only
    user: Mapped["User"] = relationship(back_populates="addresses")

# Emit DDL from ORM mapped classes
Base.metadata.create_all(engine)
```

### Type annotation rules

```python
name: Mapped[str]           # NOT NULL in DB
name: Mapped[Optional[str]] # nullable in DB
```

### `relationship()` explained

`relationship()` adds no column to the DB. It lets you navigate between related objects in Python:

```python
user = session.get(User, 1)
print(user.addresses)   # list of Address objects — no manual JOIN needed

address = session.get(Address, 1)
print(address.user)     # the User object this address belongs to
```

`back_populates` keeps both sides in sync:
```python
user.addresses.append(some_address)
# some_address.user is now automatically set to user
```

How it all fits together:
```
ForeignKey(...)    → tells SQLAlchemy the join condition
relationship(...)  → exposes navigation in Python
back_populates     → keeps both sides in sync on mutation
Registry           → knows the structure (class relationships, table mappings) — set up at class definition time
Session            → tracks instance state changes at runtime, generates SQL on commit()
```

The whole thing is a **Unit of Work** pattern — you mutate Python objects naturally, Session collects all dirty state, and on `commit()` it figures out the right INSERT/UPDATE/DELETE order and fires them in one transaction.

---

## INSERT — Core Way

```python
from sqlalchemy import insert

# Build the insert construct
stmt = insert(user_table).values(name="spongebob", fullname="Spongebob Squarepants")

# Print to see the parameterized SQL (values are separate, SQL injection safe)
print(stmt)
# INSERT INTO user_account (name, fullname) VALUES (:name, :fullname)

# Execute
with engine.connect() as conn:
    result = conn.execute(stmt)
    conn.commit()
    print(result.inserted_primary_key)  # (1,) — tuple since PK can be composite
```

### executemany — passing a list of dicts

```python
with engine.connect() as conn:
    conn.execute(
        insert(user_table),
        [
            {"name": "sandy", "fullname": "Sandy Cheeks"},
            {"name": "patrick", "fullname": "Patrick Star"},
        ]
    )
    conn.commit()
```

- SQLAlchemy looks at the **first dict only** to determine which columns to use (performance reason)
- Compiles the template **once**, reuses it per item
- Still individual inserts at the DB level, but cheaper — template compiled once, driver may batch wire traffic

### RETURNING

On PostgreSQL, `RETURNING` is used implicitly to get back the inserted PK (`inserted_primary_key`). You can also specify it explicitly:

```python
stmt = insert(address_table).returning(
    address_table.c.id,
    address_table.c.email
)
# INSERT INTO address (...) VALUES (...) RETURNING address.id, address.email
```

---

## Parameterization and SQL Injection

Always use bound parameters, never string interpolation:

```python
# Never do this — SQL injection risk
conn.execute(text(f"SELECT * FROM table WHERE y > {some_value}"))

# Always do this
conn.execute(text("SELECT * FROM table WHERE y > :y"), {"y": some_value})
```

SQLAlchemy abstracts the different DBAPI parameter formats (`:y`, `?`, `%(y)s`) into one unified named format. When using Core constructs or ORM, parameterization happens automatically.
