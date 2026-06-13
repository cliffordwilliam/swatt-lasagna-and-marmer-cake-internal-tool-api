# SQLAlchemy

I have decided to use SQLAlchemy because I want to use its ORM. Its ORM solves the following business problem that I am interested in: Sending SQL query over the network from a worker to a cluster is simple to do in Python. So the problem lies in raw text file code organization management. As in if you were to write everything in raw SQL string to be sent over the network to a cluster all over the place, it is not wrong but it is really painful to manage in the long run. As in if one day you have a an update on a table or a column, then you have to hunt every SQL query you have written that is scattered in many many raw text files. With ORM, we change on how to interact with the cluster. Instead of writing raw text SQL and sending that over the network yourself, we instead use the ORM abstraction where you use Python object construct to describe your intent and let the ORM abstraction figure out what the SQL query is going to be.

With that said, this project is going to run my family business. And I am unsure how it will grow in the future. I can keep it simple with just sending raw SQL query string over the network but I do not see the issue with using ORM. Since I can always control and check what the underlying SQL query that is being sent over anyways at the cost of well more code in a worker.

The following is my plan on how I am going to use this tool. Here is how one worker looks like:
- One worker
    - One process
        - Its own stack
    - One thread per handler
        - Its own stack
    - One heap
        - This is where Session live
        - This is where Engine live
            - TCP Connections

And this is how a typical unit of work (UoW) looks like:
1. Request comes in, this is where one UoW is born.
2. If free thread exists we proceed otherwise this request gotta wait!
3. If connection pool is empty then also gotta wait!
4. One UoW on birth gets one new Session and one existing connection (Connection pool is lazy, it will create connection when it first needs it, not on startup).
5. Session starts PostgreSQL transaction implicitly.
6. Do the following multiple times in one transaction: Mutate mapped classes states, run query multiple times, `flush` to sync database with worker or `refresh` to do it the other way.
7. UoW dies from either a final `commit` or `rollback` sent to the cluster using Session.
8. Close transaction, close Session and clean up Connection state and return it back to pool (up for grabs again).

---

The following are notes that I have made from studying the SQLAlchemy official documentation.

SQLAlchemy has two components, Core and ORM.
I am using version 2.0 so the ORM uses Core `select` construct too, and they both share the same `transaction` syntax.

Core is the main API whereas the ORM API is the optional one built on top of it. Which means Core has the foundational base API to manage connection to cluster and means to interact with cluster, while ORM just puts more feature on top of it using Core abilities. Core API is also under sqlalchemy namespace. So you can use Core API alone as is, but you might be interested in ORM since it solves other business problem that you might need solving too.

ORM added feature is called Object Relational Mapping (ORM), where it allows us to write intent using Python classes to represent database tables and constructs and also provide Session as a means to manage database transaction, and within that transaction you change Python classes state and it is able to keep up database against Python class changes or vice versa. So instead of writing SQL, we describe intent with Python classes state changes, then ORM abstraction figures out the how as in the real SQL queries. Note that what ORM uses under the hood is still the same tools that Core API has and you also still have means to write SQL yourself even when using ORM, you still can peek also what SQL you get from ORM as well. ORM stuff are under sqlalchemy.orm namespace.

Engine is a Core API that allows us to connect to a target database by just passing a connection string (URL) and have it abstract away of managing connection. Engine is the thing that manages the database connection pool, since making one is expensive, we pool them so that if a transaction needs one, it can use existing from the pool, but note that it creates connection when it first needs to do a query, so by default its lazy. But note that transaction is one to one with borrowed connection. I want Engine object to be in heap so the worker threads all have access to it. The URL structure differ depending on what the target is and thus it has different info about said target, I guess we can say that the URL is target sensitive in nature. The URL also indicates which driver I am using for this target, they call driver `DBAPI` here, note that it has implicit default driver values for different database target. But the biggest takeaway is that Engine manages connection pool and both are in heap, read the docs on how to connect to your desired database and what other parameters it has, note that by default it is lazy it does not create connection upfront. Like it does not shake hands say 3 times when the app starts so first query that arrives sees that there are like 3 connection, it is lazy as in if this is the first ever query then it sees no connection at all, only when it attempts to send SQL query then it creates a connection there and populate the pool with that one connection.

This discusses the time when we want to do interactions to a cluster inside a thing such as a (worker/single-process)'s thread transaction. And this interaction involves Connection and Result provision from Engine. Or I can use Session which is a convenient abstraction over using Connection and Result directly.

Given that there is one incoming request, and given that the setup is that per handler delegate work to a thread:

One Worker/Single-Process
- Delegate this request work to one of its thread
    - One Session (Derived from Engine both from heap)
        - One transaction (started implicitly, may start from Engine method or Session)
        - One connection for one transaction (first created and stored in pool in very first query or borrowed from existing in pool)
        - Mutate mapped classes multiple times
        - Query multiple times (Read or Write)
        - `flushes` or `refreshes` multiple times
            - Uses `Connection` and `Result`
        - `commit` or `rollback` once to end the transaction
        - Ends the Session too


Documentation says that Session and Connection API are similar in pattern. This is because Session is just a convenient over the underlying direct usage of `Connection` Documentation also says that for this bit it will not use the SQLAlchemy Expression Language but uses the `text` construct instead. So you either we use Session or use the Connection and Result directly. This is a diagram of what is composed of what, or what derives from what:

- Session
    - Engine
        - Connection: context manager compliant, implicit transaction start, explicit commit and rollback needed (there is a means to config auto commit to be true)
        - Result: best used while Connection is open

You can use both Connection and Session using context manager protocol `with` keyword. That works since both has implicit start and needs to end when it is out of the indentation scope. But then using Session means you can control when it closes using a method call instead of the indentation, easier to then pass Session around multiple files when you want component based logic. Note that regardless you want to always do a final `commit` or `rollback` and then you close the Connection or Session. Its like streaming, where for example: You opened the stream (Session), executed queries within the same open transaction, got results back, and the stream closed at the end with a COMMIT sent to the database cluster. The connection stayed borrowed from the pool for the entire duration.

Note that the above is my design choice, to have 1 Session per transaction, since you can do it however you want.

You can use Connect to send commit to the cluster, in my design I think I'd stop the stream Session and transaction all together in a final commit but then it says that is a known pattern called `begin once`, whereas `commit as you go` is also a valid pattern where you commit multiple times in one transaction. It however mention that to make it a transaction that does an auto final commit and rollback with engine you should do `.begin` instead, where the only difference is that it automatically does either a `commit` or `rollback` for you at the end.

`commit as you go` vs `begin once` implementation:
- use `engine.connect()` — then you manually call `.commit()` whenever you want, can commit multiple times.
- use `engine.begin()` — then it auto commits at end of with block, auto rollbacks on exception.

So I think my session cannot even do this (the auto commits and auto rollback on exception at the end) since I am using the yield pattern and this engine.begin() one is more automatic in nature but it uses the with indentation. Documentation however also suggest that the begin once is a better pattern. And I have means to subscribe the cluster events later too say on the implicit BEGIN. It mentions that DDL (query that mutates schema like creating a table) should be in a transaction block when you want to do one, but then it also mentions that the SQLAlchemy can run DDL as higher level operation, it is referring to this:

```py
# For development only, here we hydrate the PostgreSQL cluster to be the same with the mapped classes here
Base.metadata.create_all(engine)
```

note that whenever you do engine.connect(), that resolves to a Connection object from the engine that you then use inside a context manager protocol `with` keyword. So the `engine` method starts a transaction implicitly, but in that transaction you interact using the `Connection` object method like `.execute` and uses construct like `text` in it. This is because each Connection execute is sending an SQL query over the network. Like so:

```py
with engine.connect() as conn:
    result = conn.execute(text("SELECT x, y FROM some_table"))
    for row in result:
        print(f"x: {row.x}  y: {row.y}")
```

Note that the Result object can be iterated!

Also note that the `Session.execute` does the same thing to, It uses the same Connection object to send the query as well. Likewise the result that you get back is also the same `Result` object you get when using Connection directly.

```py
@app.get("/testing")
def testing():
    # Use the engine (heap thing that manages connection to cluster)
    # To get a connection object, this is context manager protocol compliant to we can use the `with`
    # This one implicit start the PostgreSQL transaction in the indentation
    # And when it is out of scope if will close the transaction for you! With the rollback sent implicitly (so if you commit already, this auto rollback has nothing to 'undo')
    # Note that the connection here for this transaction may either come from the existing connection in pool
    # Or it just creates a new one here that will get used throughout the transaction and is also registered as a new pool member
    # Here we use the `text` construct in conjunction with the execute method to send SQL query over the wire
    # Note that its best to use the `Result` within an opened transaction like this!
    with engine.connect() as connection:
        result = connection.execute(text("select 'hello'"))
        # Returns all rows!
        print(result.all())
    return {"status": "ok"}
```

So the above example is simple it just returns to you a raw value. Here is another example where in one transaction we do two things! Where we first make a table using DDL then we put an item in there! This is ACID so we have to commit at the end to tell the database to make it permanent, otherwise the auto rollback will undo all this transaction work back to square one!

Note that the implicit transaction start is from the first `execute` you do! Also note here that there is a concept called `parameters`, but I will likely not use that since I rely on the mapped class and Session to figure out what the parameters are from the state changes I do on the mapped class instances:

```py
@app.get("/testing")
def testing():
    with engine.connect() as connection:
        connection.execute(text("CREATE TABLE some_table (x int, y int)"))
        connection.execute(text("INSERT INTO some_table (x, y) VALUES (:x, :y)"), [{"x": 1, "y": 1}, {"x": 2, "y": 4}])
        connection.commit()
        result = connection.execute(text("SELECT * FROM some_table"))
        print(result.all())
    return {"status": "ok"}
```

So the ORM way would look something like this:

```text
# ORM way - you never write parameters yourself
new_item = Item(x=1, y=2)
session.add(new_item)
session.commit()
# Session generates: INSERT INTO item (x, y) VALUES (%(x)s, %(y)s) with {'x': 1, 'y': 2}
```

So unless you ever decide to drop down and write it yourself, that is where you need to know how to use parameters. Which you wont since you rely on the Session and mapped class to figure that out for you!

Note that, when you `commit` or `rollback` like this, the next `execute` has the same implicit transaction start behavior like your first `execute` too!

```text
first execute()  → BEGIN (implicit)
execute()        → runs on same transaction
execute()        → runs on same transaction
commit()         → COMMIT sent, transaction closed

next execute()   → BEGIN (implicit) ← new transaction starts automatically!
execute()        → runs on same transaction
with block ends  → ROLLBACK (no commit was called)
```

Note that the whole `parameterization syntax` is referring to this:

```py
connection.execute(
    text("INSERT INTO some_table (x, y) VALUES (:x, :y)"),
    [{"x": 1, "y": 1}, {"x": 2, "y": 4}]
)
```

Specifically the :x and :y in the SQL string — those are named parameters.

So you can do this it works fine! But dont since this is dangerous and the reason why the `parameterization syntax` exists!

This raw string as is is fine but its dangerous! AKA its prone to SQL injection!
`INSERT INTO some_table (x, y) VALUES (1, 1)`

Parameterization is essentially the industry's answer to "humans are mean and will type anything into your input fields."


So anyways if you commit multiple times, this is a known fine pattern that is called `commit as you go`

There is another feature that the engine expose, this API does the exact same thing but it auto commit or rollback at the end for you! Here we use the `engine.begin` instead of the `engine.connect`. We call this pattern the `begin once`, where you `commit` once at the very end.

So the one where you commit multiple times looks like this

```bash
2026-06-13 15:06:10,029 INFO sqlalchemy.engine.Engine BEGIN (implicit)
2026-06-13 15:06:10,029 INFO sqlalchemy.engine.Engine CREATE TABLE some_table (x int, y int)
2026-06-13 15:06:10,029 INFO sqlalchemy.engine.Engine [generated in 0.00034s] {}
2026-06-13 15:06:10,092 INFO sqlalchemy.engine.Engine INSERT INTO some_table (x, y) VALUES (%(x)s, %(y)s)
2026-06-13 15:06:10,092 INFO sqlalchemy.engine.Engine [generated in 0.00039s] [{'x': 1, 'y': 1}, {'x': 2, 'y': 4}]
2026-06-13 15:06:10,093 INFO sqlalchemy.engine.Engine COMMIT
2026-06-13 15:06:10,096 INFO sqlalchemy.engine.Engine BEGIN (implicit)
2026-06-13 15:06:10,096 INFO sqlalchemy.engine.Engine SELECT * FROM some_table
2026-06-13 15:06:10,096 INFO sqlalchemy.engine.Engine [generated in 0.00023s] {}
[(1, 1), (2, 4)]
2026-06-13 15:06:10,098 INFO sqlalchemy.engine.Engine ROLLBACK
```

Whereas the other one where you commit once only looks like this, it auto commits but see it does not blindly always send rollback:

```bash
2026-06-13 15:46:03,654 INFO sqlalchemy.engine.Engine BEGIN (implicit)
2026-06-13 15:46:03,655 INFO sqlalchemy.engine.Engine CREATE TABLE some_table (x int, y int)
2026-06-13 15:46:03,655 INFO sqlalchemy.engine.Engine [generated in 0.00024s] {}
2026-06-13 15:46:03,657 INFO sqlalchemy.engine.Engine INSERT INTO some_table (x, y) VALUES (%(x)s, %(y)s)
2026-06-13 15:46:03,657 INFO sqlalchemy.engine.Engine [generated in 0.00017s] [{'x': 1, 'y': 1}, {'x': 2, 'y': 4}]
2026-06-13 15:46:03,689 INFO sqlalchemy.engine.Engine SELECT * FROM some_table
2026-06-13 15:46:03,689 INFO sqlalchemy.engine.Engine [generated in 0.00045s] {}
[(1, 1), (2, 4)]
2026-06-13 15:46:03,690 INFO sqlalchemy.engine.Engine COMMIT
```

The difference between the two styles is really just about who is responsible for committing:
`engine.connect()` → you are responsible, you call `connection.commit()` yourself, hence "commit as you go"
`engine.begin()` → SQLAlchemy is responsible, it commits or rolls back for you when the with block exits, hence "begin once"

You can use whichever one you want, but if you want longer transaction that guarantees one commit then just use the `begin`. Both has pros and cons.

Note that the result object that you get here is a = `iterable object of result row`.

```py
@app.get("/testing")
def testing():
    with engine.begin() as connection:
        result = connection.execute(text("SELECT x, y FROM some_table"))
        for row in result:
            print(f"x: {row.x}, y: {row.y}")
    return {"status": "ok"}
```

Here is the log for it see:

```bash
2026-06-13 15:53:24,402 INFO sqlalchemy.engine.Engine BEGIN (implicit)
2026-06-13 15:53:24,403 INFO sqlalchemy.engine.Engine SELECT x, y FROM some_table
2026-06-13 15:53:24,403 INFO sqlalchemy.engine.Engine [generated in 0.00029s] {}
x: 1, y: 1
x: 2, y: 4
2026-06-13 15:53:24,405 INFO sqlalchemy.engine.Engine COMMIT
```

There are many other methods that the `Result` object have. And when you use `Session.execute()`, this is what you get back too!
But then stuff inside is the mapped class instances instead of just tuples!

```py
result = session.execute(select(Item))
for item in result:
    print(item.x)  # row contains your mapped class instance
```

Note that you still need to know how to work with row that are tuple, and not instances of mapped classes, since if you ever want just some of the columns, then this is where it gives you row tuples. Here are some common ways to interact with row tuples, please check the docs yourself for more detail on what you can do to work with this:
- unwrap per row prop
- access prop using index
- use dot notation per row prop access
- turn a row into a dict

This is an example even in ORM when you only want certain column it gives you row tuples!
```py
# Selecting whole object → scalars() unwraps it nicely
result = session.execute(select(Item))
items = result.scalars().all()  # gives you list of Item objects

# Selecting specific columns → you get raw Row tuples back
result = session.execute(select(Item.name, Item.amount))
rows = result.all()  # gives you [('testing', 5), ('testing2', 10)]
```

Here is a better example:

```py
        # select(Item.name) → you asked for a column, so SQLAlchemy gives you a Row wrapping a tuple of the raw value Row[Tuple[str]]
        result = self.db.execute(select(Item.name))
        for tuple_row in result:
            # ('some name value',)
            print(tuple_row)

        # select(Item) → you asked for a whole mapped object, so SQLAlchemy gives you a Row wrapping a tuple of the Item instance Row[Tuple[Item]]
        result = self.db.execute(select(Item))
        for instanced_row in result:
            # (<app.domains.items.item_model.Item object at 0x7038b990ba10>,)
            print(instanced_row[0].amount)
        
        # Both are just rows either way, the differences are what is inside the tuple. AKA both are wrapped by tuple.
        # Either unwrap to get instance = instanced_row[0].amount
        # Or access tuple for desired column you asked for = tuple_row[0] <- you asked for 1 name column at index 0
        # You might wanna use `scalars` this if it has one stuff in it
        # So .scalars() is basically saying "I know each row only has one thing in it, just unwrap it for me across the whole result."
```

Note that:
- `.scalars()` → unwrapping instruction ("peel off the Row wrapper") - useful when you do not want to keep getting single item tuple!
- `.all()` → "now give me everything as a normal Python list" (otherwise you get this other type that you can iter once only...)
