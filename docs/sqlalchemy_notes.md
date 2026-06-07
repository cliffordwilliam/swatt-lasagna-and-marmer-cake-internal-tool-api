# SQLAlchemy

I have decided to use SQLAlchemy because I want to use its ORM. Its ORM solves the following business problem that I am interested in: Sending SQL query over the network from a worker to a cluster is simple to do in Python. So the problem lies in raw text file code management. As in if you were to write everything in raw string to be sent over the network to a cluster all over the place, it is not wrong but really painful to manage in the long run. As in if one day you have a an update on a table or a column, then you have to hunt every SQL query you have written that is scattered in many many raw text files. With ORM, we change on how to interact with the cluster. Instead of writing raw text SQL and sending that over the network yourself, we instead use the ORM abstraction where you use Python object construct to describe your intent and let the ORM abstraction figure out what the SQL query is going to be.

With that said, this project is going to run my family business. And I am unsure how it will grow in the future. I can keep it simple with just sending raw SQL query string over the network but I do not see the issue with using ORM. Since I can always control and check what the underlying SQL query that is being sent over anyways at the cost of well more code in a worker.

The following is my plan on how I am going to use this tool. Here is how one worker looks like:
- Worker
    - One process
        - Its own stack
    - One thread per handler
        - Its own stack
    - One heap
        - This is where Session live
        - This is where Engine live
            - TCP Connections

And this is how a typical unit of work (UoW) looks like:
1. Request comes in, this is where one UoW is born
2. If free thread exists we proceed otherwise this request gotta wait!
3. If connection pool is empty then also gotta wait!
4. One UoW on birth gets one new Session and one existing connection (Connection pool was populated once on startup)
5. Session starts PostgreSQL transaction
6. Session has states on constructs such as the mapped classes
7. UoW mutates constructs and send real query to the cluster
8. UoW flushes multiple times to sync construct state using cluster state
9. UoW dies from either a final commit or rollback sent to the cluster
10. Close transaction, close Session and clean up Connection and return it back to pool (up for grabs again)

---

The following are notes that I have made from studying the SQLAlchemy official documentation.

SQLAlchemy has two components, Core and ORM.
I am using version 2.0 so the ORM uses Core `select` construct too, and they both share the same `transaction` syntax.

Core is the main API where as the ORM API is the optional one built on top of it. Which means Core has the foundational base API to manage connection to cluster and means to interact with cluster and ORM just puts more feature on top. Core API is also under sqlalchemy namespace. So you can use Core API alone as is, but you might be interested in ORM since it solves other business problem that you might need solving too.

ORM added feature is called Object Relational Mapping (ORM), where it allows us to write intent using Python classes to represent database tables and constructs and also provide Session as a means to manage database transaction, and within that transaction you change Python classes state and it is able to keep up database against Python class changes or vice versa. So instead of writing SQL, we describe intent with Python classes state changes, then ORM abstraction figures out the how as in the real SQL queries. Note that what ORM uses under the hood is still the same tools that Core API has and you also still have means to write SQL yourself even when using ORM, you still can peek also what SQL you get from ORM as well. ORM stuff are under sqlalchemy.orm namespace.

Engine is a Core API that allows us to connect to a target database by just passing a connection string (URL) and have it abstract away of managing connection. Engine is the thing that manages the database connection pool, since making one is expensive, we pool them so that if a transaction needs one, it can use existing from the pool, but note that it creates connection when it first needs to do a query, so by default its lazy. I want Engine object to be in heap so the worker threads all have access to it. The URL structure differ depending on what the target is and thus it has different info about said target, I guess we can say that the URL is target sensitive in nature. The URL also indicates which driver I am using for this target, they call driver DBAPI here, note that it has implicit default driver values for different database target. But the biggest takeaway is that Engine manages connection pool, read the docs on how to connect to your desired database and what other parameters it has, note that by default it is lazy it does not create connection upfront.