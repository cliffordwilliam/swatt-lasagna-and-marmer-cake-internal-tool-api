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

Engine is a Core API that allows us to connect to a target database by just passing a connection string (URL) and have it abstract away of managing connection. Engine is the thing that manages the database connection pool, since making one is expensive, we pool them so that if a transaction needs one, it can use existing from the pool, but note that it creates connection when it first needs to do a query, so by default its lazy. I want Engine object to be in heap so the worker threads all have access to it. The URL structure differ depending on what the target is and thus it has different info about said target, I guess we can say that the URL is target sensitive in nature. The URL also indicates which driver I am using for this target, they call driver `DBAPI` here, note that it has implicit default driver values for different database target. But the biggest takeaway is that Engine manages connection pool, read the docs on how to connect to your desired database and what other parameters it has, note that by default it is lazy it does not create connection upfront.

This discusses the time when we want to do interactions to a cluster inside a worker thread transaction. And this interaction involves Connection and Result. Or I can use Session which is a convenient abstraction over using Connection and Result directly.

One Worker
- One request handler
    - One thread
        - One Session (Derived from Engine both from heap)
            - One transaction (started implicitly, closed explicitly)
            - One connection (first created in first query or borrowed existing)
            - Mutate mapped classes multiple times
            - Query multiple times
            - `flushes` or `refreshes` multiple times
                - Uses `Connection` and `Result`


Documentation says that Session and Connection API are similar in pattern. This is because Session is just a convenient over the underlying direct usage of `Connection` Documentation also says that for this bit it will not use the SQLAlchemy Expression Language but uses the text construct instead. So you either we use Session or use the Connection and Result directly. This is composed of what:

- Session
    - Engine
        - Connection: context manager compliant, implicit transaction start, explicit commit and rollback needed (there is a means to config auto commit to be true)
        - Result: best used while Connection is open

You can use both Connection and Session using context manager protocol `with` keyword. That works since both has implicit start and needs to end when it is out of the indentation scope. But then using Session means you can control when it closes using a method call instead of the indentation, easier to then pass Session around multiple files when you want component based logic. Note that regardless you want to always do a final `commit` or `rollback` and then you close the Connection or Session. Its like streaming, where for example: You opened the stream (Session), executed queries within the same open transaction, got results back, and the stream closed at the end with a COMMIT sent to the database cluster. The connection stayed borrowed from the pool for the entire duration.

Note that the above is my design choice, to have 1 Session per transaction, since you can do it however you want.

You can use Connect to send commit to the cluster, in my design I think I'd stop the stream Session and transaction all together in a final commit but then it says that is a known pattern called `begin once`, whereas `commit as you go` is also a valid pattern where you commit multiple times in one transaction. It however mention that to make it a transaction that does an auto final commit and rollback with engine you should do `.begin` instead, where the only difference is that it automatically does either a `commit` or `rollback` for you at the end.

`commit as you go` vs `begin once` implementation:
- use engine.connect() — then you manually call .commit() whenever you want, can commit multiple times.
- use engine.begin() — then it auto commits at end of with block, auto rollbacks on exception.

So I think my session cannot even do this since I am using the yield pattern and this one is more automatic in nature but it uses the with indentation. Documentation however also suggest that the begin once is a better pattern. And I have means to subscribe the cluster events later too say on the implicit BEGIN. It mentions that DDL (query that mutates schema like creating a table) should be in a transaction block when you want to do one, but then it also mentions that the SQLAlchemy can run DDL as higher level operation, it is referring to this:

```py
# For development only, here we hydrate the PostgreSQL cluster to be the same with the mapped classes here
Base.metadata.create_all(engine)
```
