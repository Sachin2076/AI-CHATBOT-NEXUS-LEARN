"""Run once to populate ChromaDB with CS knowledge chunks."""

from rag import embed_documents

DOCS = [
    # ── Python ────────────────────────────────────────────────────────────────
    {
        "id": "python_variables",
        "topic": "Python",
        "text": (
            "Python variables are dynamically typed, meaning you do not declare a type explicitly. "
            "The interpreter infers the type at runtime. Python supports integers, floats, strings, "
            "booleans, lists, tuples, sets, and dictionaries as built-in data types. Variable names "
            "are case-sensitive and must start with a letter or underscore. Python uses duck typing: "
            "if an object supports the required operations, it is used regardless of its class. "
            "Multiple assignment is possible in one line: a, b, c = 1, 2, 3. "
            "Constants are conventionally written in ALL_CAPS but Python does not enforce immutability. "
            "Use type hints (PEP 484) to annotate expected types without runtime enforcement."
        ),
    },
    {
        "id": "python_functions",
        "topic": "Python",
        "text": (
            "Python functions are first-class objects: they can be assigned to variables, passed as "
            "arguments, and returned from other functions. Define a function with the def keyword. "
            "Default arguments allow optional parameters. *args and **kwargs collect positional and "
            "keyword arguments respectively. Decorators are functions that wrap another function to "
            "add behavior without modifying its source. The @decorator syntax is syntactic sugar for "
            "func = decorator(func). Common built-in decorators include @staticmethod, @classmethod, "
            "and @property. Lambda expressions create anonymous single-expression functions. "
            "Closures capture variables from the enclosing scope, enabling factory patterns."
        ),
    },
    {
        "id": "python_list_comprehensions",
        "topic": "Python",
        "text": (
            "List comprehensions provide a concise way to create lists in Python. "
            "The syntax is [expression for item in iterable if condition]. "
            "They are generally faster than equivalent for-loops because the iteration is implemented "
            "in C internally. Dictionary comprehensions use {key: value for item in iterable} and "
            "set comprehensions use {expression for item in iterable}. Generator expressions are "
            "similar but use parentheses and produce values lazily, saving memory for large datasets. "
            "Nested comprehensions can replace nested loops. Example: "
            "squares = [x**2 for x in range(10) if x % 2 == 0] produces [0, 4, 16, 36, 64]. "
            "Avoid deeply nested comprehensions as they hurt readability."
        ),
    },
    # ── Java ──────────────────────────────────────────────────────────────────
    {
        "id": "java_oop_basics",
        "topic": "Java",
        "text": (
            "Java is a statically typed, object-oriented language that runs on the Java Virtual Machine "
            "(JVM). Every program starts with a class containing a public static void main(String[] args) "
            "method. Java enforces strict type declarations: int, double, boolean, char are primitives; "
            "everything else is an object reference. Classes define state (fields) and behavior (methods). "
            "Access modifiers — public, protected, private, package-private — control visibility. "
            "Java is pass-by-value for primitives and pass-by-value-of-reference for objects. "
            "The new keyword allocates heap memory and calls the constructor. "
            "Garbage collection automatically reclaims memory from unreachable objects, "
            "eliminating manual memory management errors like dangling pointers."
        ),
    },
    {
        "id": "java_interfaces_abstract",
        "topic": "Java",
        "text": (
            "An interface in Java declares a contract — method signatures without implementations "
            "(before Java 8). Since Java 8, interfaces can have default and static methods. "
            "Since Java 9, private methods are also allowed. A class can implement multiple interfaces, "
            "enabling a form of multiple inheritance. An abstract class can have both abstract methods "
            "(no body) and concrete methods (with body). A class can extend only one abstract class "
            "but can implement many interfaces. Use an abstract class when sharing state or common logic; "
            "use an interface when defining a capability contract. Functional interfaces have exactly one "
            "abstract method and can be used with lambda expressions (e.g., Runnable, Comparator). "
            "The @FunctionalInterface annotation enforces this constraint at compile time."
        ),
    },
    # ── Algorithms ────────────────────────────────────────────────────────────
    {
        "id": "algorithms_big_o",
        "topic": "algorithms",
        "text": (
            "Big O notation describes the upper bound of an algorithm's time or space complexity as "
            "input size n grows. O(1) is constant time — the operation takes the same time regardless "
            "of input size (e.g., array index access). O(log n) grows slowly — typical of binary search "
            "or balanced tree operations. O(n) is linear — you inspect each element once. "
            "O(n log n) is common for efficient sorting algorithms like merge sort and quicksort. "
            "O(n²) is quadratic — seen in nested loops like bubble sort. O(2^n) is exponential, "
            "typical of naive recursive solutions for problems like the Fibonacci sequence. "
            "When comparing algorithms, focus on the dominant term and drop constants: "
            "3n² + 100n simplifies to O(n²). Analyze worst-case unless specified otherwise."
        ),
    },
    {
        "id": "algorithms_quicksort",
        "topic": "algorithms",
        "text": (
            "Quicksort is a divide-and-conquer sorting algorithm with average time complexity O(n log n). "
            "It selects a pivot element and partitions the array so all elements less than the pivot "
            "come before it and all greater elements come after. It then recursively sorts each partition. "
            "The choice of pivot affects performance: a bad pivot (always the smallest or largest element) "
            "degrades performance to O(n²). Common pivot strategies are random selection or the median-of-three. "
            "Quicksort sorts in-place, using O(log n) stack space for recursion. "
            "It is cache-friendly because it accesses contiguous memory. In practice, quicksort outperforms "
            "merge sort on most real-world data despite the same average complexity. "
            "Many standard library sort functions use an introspective sort (introsort) combining "
            "quicksort, heapsort, and insertion sort."
        ),
    },
    {
        "id": "algorithms_binary_search",
        "topic": "algorithms",
        "text": (
            "Binary search finds a target value in a sorted array in O(log n) time. "
            "It works by repeatedly halving the search space: compare the target to the middle element; "
            "if equal, return the index; if target is smaller, search the left half; otherwise search the right. "
            "The array must be sorted for binary search to work. It can also find the leftmost or rightmost "
            "occurrence of a value by adjusting the termination condition. Binary search applies to any "
            "monotonic function, not just arrays — for example, finding the smallest x where f(x) is true. "
            "Overflow pitfall: use mid = left + (right - left) / 2 instead of (left + right) / 2 "
            "to avoid integer overflow in languages without arbitrary precision integers."
        ),
    },
    {
        "id": "algorithms_dynamic_programming",
        "topic": "algorithms",
        "text": (
            "Dynamic programming (DP) solves problems by breaking them into overlapping subproblems and "
            "storing results to avoid redundant computation (memoization or tabulation). "
            "It applies when a problem has optimal substructure — the optimal solution contains optimal "
            "solutions to subproblems — and overlapping subproblems. Classic DP problems include "
            "Fibonacci numbers, longest common subsequence, 0/1 knapsack, and shortest path (Bellman-Ford). "
            "Top-down DP uses recursion with memoization (a cache). Bottom-up DP fills a table iteratively "
            "from base cases. Bottom-up is often faster due to no recursion overhead and better cache locality. "
            "DP reduces exponential brute-force to polynomial time — for example, Fibonacci goes from O(2^n) "
            "recursive to O(n) with memoization, and further to O(1) space with two variables."
        ),
    },
    # ── Data structures ───────────────────────────────────────────────────────
    {
        "id": "ds_linked_lists",
        "topic": "data structures",
        "text": (
            "A linked list is a linear data structure where each element (node) stores a value and a "
            "pointer to the next node. Unlike arrays, nodes are not stored contiguously in memory, so "
            "random access is O(n). Insertion and deletion at the head or a known node are O(1). "
            "Singly linked lists have one pointer per node; doubly linked lists have two (next and prev), "
            "enabling O(1) removal of a node given a direct reference. Circular linked lists connect the "
            "tail back to the head. Common interview operations: reversing a list, detecting a cycle "
            "(Floyd's two-pointer algorithm), finding the middle node, and merging two sorted lists. "
            "Use a linked list when you need frequent insertions/deletions and do not need random access."
        ),
    },
    {
        "id": "ds_hash_tables",
        "topic": "data structures",
        "text": (
            "A hash table maps keys to values using a hash function that converts a key to an array index. "
            "Average-case time complexity for insert, delete, and lookup is O(1). "
            "Collisions occur when two keys hash to the same index; resolved by chaining "
            "(each slot holds a linked list) or open addressing (probing nearby slots). "
            "Load factor = number of entries / number of slots; rehashing occurs when load factor "
            "exceeds a threshold (typically 0.7–0.75), copying all entries to a larger table in O(n). "
            "A good hash function distributes keys uniformly to minimize collisions. "
            "Python dictionaries and Java HashMaps are hash table implementations. "
            "Hash tables are ideal for frequency counting, caching (LRU cache), and deduplication. "
            "Worst-case O(n) occurs with pathological inputs that all collide."
        ),
    },
    {
        "id": "ds_binary_search_tree",
        "topic": "data structures",
        "text": (
            "A binary search tree (BST) is a binary tree where each node satisfies the BST property: "
            "all values in the left subtree are less than the node's value, and all values in the "
            "right subtree are greater. This enables O(log n) average-case search, insert, and delete. "
            "In-order traversal of a BST produces a sorted sequence. A degenerate BST (all nodes in "
            "one line) degrades to O(n) for all operations. Self-balancing variants like AVL trees "
            "and Red-Black trees maintain O(log n) height guarantees. "
            "BSTs are the foundation for ordered maps and sets (Java TreeMap, C++ std::map). "
            "Common operations: find minimum/maximum (leftmost/rightmost node), successor, predecessor, "
            "and range queries. Deletion is the trickiest: replace with in-order successor or predecessor."
        ),
    },
    {
        "id": "ds_stacks_queues",
        "topic": "data structures",
        "text": (
            "A stack is a Last-In First-Out (LIFO) structure supporting push (add to top) and pop "
            "(remove from top) in O(1). Applications: function call stack, expression evaluation, "
            "undo/redo, balanced parentheses checking, and depth-first search (DFS). "
            "A queue is a First-In First-Out (FIFO) structure supporting enqueue (add to back) and "
            "dequeue (remove from front) in O(1). Applications: breadth-first search (BFS), task "
            "scheduling, and message buffers. A deque (double-ended queue) supports O(1) operations "
            "at both ends. A priority queue returns the minimum (or maximum) element in O(log n); "
            "it is typically implemented with a heap. Python provides collections.deque for O(1) "
            "append/popleft and heapq for min-heap operations."
        ),
    },
    # ── Web Development ───────────────────────────────────────────────────────
    {
        "id": "web_http_basics",
        "topic": "web development",
        "text": (
            "HTTP (HyperText Transfer Protocol) is the foundation of data exchange on the web. "
            "It is a stateless request-response protocol over TCP. Common methods: GET retrieves "
            "a resource; POST submits data; PUT replaces a resource; PATCH partially updates it; "
            "DELETE removes it. Status codes: 2xx success (200 OK, 201 Created), 3xx redirection "
            "(301 Moved Permanently, 302 Found), 4xx client errors (400 Bad Request, 401 Unauthorized, "
            "403 Forbidden, 404 Not Found), 5xx server errors (500 Internal Server Error). "
            "HTTP/1.1 added persistent connections and chunked transfer encoding. "
            "HTTP/2 multiplexes requests over a single connection and uses header compression. "
            "HTTPS wraps HTTP in TLS for encrypted communication, verified by digital certificates."
        ),
    },
    {
        "id": "web_rest_apis",
        "topic": "web development",
        "text": (
            "REST (Representational State Transfer) is an architectural style for designing networked "
            "APIs using HTTP. Key constraints: stateless — each request contains all needed context; "
            "uniform interface — resources identified by URIs; client-server separation; layered system. "
            "Resources are nouns (/users, /products/42), never verbs. HTTP methods express actions: "
            "GET /users retrieves a list, POST /users creates one, PUT /users/42 replaces, "
            "DELETE /users/42 removes. Responses use standard status codes and typically return JSON. "
            "Versioning strategies: URI path (/v1/users), query param, or Accept header. "
            "Pagination prevents huge payloads: use limit/offset or cursor-based pagination. "
            "HATEOAS (Hypermedia as the Engine of Application State) links related resources in responses."
        ),
    },
    {
        "id": "web_html_css",
        "topic": "web development",
        "text": (
            "HTML (HyperText Markup Language) defines the structure and content of web pages using elements "
            "enclosed in tags. Semantic tags like <header>, <main>, <section>, <article>, <nav>, and <footer> "
            "describe meaning, improving accessibility and SEO. The DOM (Document Object Model) is a tree "
            "representation of the HTML that JavaScript can manipulate. CSS (Cascading Style Sheets) controls "
            "presentation: colors, layout, fonts, and animation. The cascade determines which rules apply "
            "based on specificity, inheritance, and source order. The box model: every element has content, "
            "padding, border, and margin. Flexbox aligns items in one dimension; CSS Grid handles two dimensions. "
            "Media queries enable responsive design by applying different styles at different viewport widths."
        ),
    },
    # ── Databases ─────────────────────────────────────────────────────────────
    {
        "id": "db_sql_basics",
        "topic": "databases",
        "text": (
            "SQL (Structured Query Language) is the standard language for relational databases. "
            "Core statements: SELECT retrieves rows; INSERT adds rows; UPDATE modifies rows; "
            "DELETE removes rows; CREATE TABLE defines a schema; DROP TABLE removes it. "
            "WHERE filters rows, ORDER BY sorts, GROUP BY aggregates, HAVING filters groups. "
            "JOIN combines rows from two tables: INNER JOIN returns matching rows; LEFT JOIN "
            "returns all left rows plus matching right rows; RIGHT JOIN is the mirror. "
            "Aggregate functions: COUNT, SUM, AVG, MIN, MAX. Subqueries nest one SELECT inside another. "
            "Transactions group statements so they succeed or fail together (ACID properties). "
            "Indexes speed up SELECT queries but slow INSERT/UPDATE because the index must be maintained."
        ),
    },
    {
        "id": "db_normalization",
        "topic": "databases",
        "text": (
            "Database normalization eliminates redundancy and prevents update anomalies by organizing "
            "data into related tables. First Normal Form (1NF): each column holds atomic values; no "
            "repeating groups. Second Normal Form (2NF): 1NF plus every non-key column is fully "
            "functionally dependent on the entire primary key (relevant for composite keys). "
            "Third Normal Form (3NF): 2NF plus no transitive dependency — non-key columns depend "
            "only on the primary key, not on other non-key columns. Boyce-Codd Normal Form (BCNF) "
            "strengthens 3NF for rare edge cases. Normalization reduces storage and keeps data consistent; "
            "denormalization deliberately reintroduces redundancy for read performance. "
            "Most production databases normalize to 3NF and denormalize only where profiling shows need."
        ),
    },
    {
        "id": "db_indexing",
        "topic": "databases",
        "text": (
            "A database index is a data structure (typically a B-Tree or Hash) that speeds up row "
            "retrieval without scanning the full table. Without an index, a SELECT with a WHERE clause "
            "performs a full table scan O(n). With a B-Tree index, lookups are O(log n). "
            "A primary key index is created automatically. Additional indexes are added on frequently "
            "queried columns. Composite indexes cover multiple columns; column order matters — the index "
            "can only be used left-to-right (leftmost prefix rule). A covering index includes all columns "
            "needed by the query, avoiding a table lookup. Indexes consume disk space and slow writes "
            "because every insert/update/delete must update the index. "
            "Use EXPLAIN (PostgreSQL/MySQL) to see whether queries use indexes and identify bottlenecks."
        ),
    },
    # ── Networking ────────────────────────────────────────────────────────────
    {
        "id": "networking_tcp_ip",
        "topic": "networking",
        "text": (
            "The TCP/IP model is the backbone of internet communication, organized in four layers. "
            "The Network Access layer handles physical transmission (Ethernet, Wi-Fi). "
            "The Internet layer routes packets between networks using IP addresses (IPv4 or IPv6); "
            "IP is connectionless and best-effort — it does not guarantee delivery or order. "
            "The Transport layer adds reliability: TCP provides ordered, error-checked delivery with "
            "a three-way handshake (SYN, SYN-ACK, ACK), flow control, and congestion control; "
            "UDP is lightweight, connectionless, and faster — suitable for streaming and gaming. "
            "The Application layer defines protocols like HTTP, DNS, FTP, and SMTP. "
            "A TCP connection is identified by a 4-tuple: source IP, source port, destination IP, "
            "destination port. Ports 0–1023 are well-known (80 HTTP, 443 HTTPS, 22 SSH, 53 DNS)."
        ),
    },
    {
        "id": "networking_dns",
        "topic": "networking",
        "text": (
            "DNS (Domain Name System) translates human-readable domain names (e.g., example.com) into "
            "IP addresses that computers use to route traffic. It is a hierarchical, distributed system. "
            "Resolution starts at the root DNS servers, then top-level domain (TLD) servers (.com, .org), "
            "then authoritative name servers for the specific domain. Recursive resolvers (your ISP or "
            "public resolvers like 8.8.8.8) cache responses to reduce latency; TTL (Time to Live) "
            "controls how long a record is cached. Record types: A maps a name to an IPv4 address; "
            "AAAA maps to IPv6; CNAME creates an alias; MX specifies mail servers; TXT stores "
            "arbitrary text (used for SPF, DKIM email authentication). DNS uses UDP port 53 "
            "for most queries and TCP for large responses or zone transfers."
        ),
    },
    # ── OOP Concepts ──────────────────────────────────────────────────────────
    {
        "id": "oop_encapsulation",
        "topic": "OOP",
        "text": (
            "Encapsulation bundles data (fields) and the methods that operate on it into a single unit "
            "(class) and restricts direct access to internal state. In Java, fields are typically marked "
            "private and accessed through public getter and setter methods, allowing validation logic "
            "before state changes. In Python, a single underscore prefix (_name) is a convention for "
            "'internal use'; double underscore (__name) triggers name mangling. Encapsulation provides "
            "three benefits: it hides implementation details so callers depend only on the public interface; "
            "it prevents unintended external modification of state; it allows internal refactoring without "
            "breaking callers. A well-encapsulated class exposes a minimal, stable API while keeping "
            "its internal representation free to change."
        ),
    },
    {
        "id": "oop_inheritance",
        "topic": "OOP",
        "text": (
            "Inheritance lets a subclass acquire fields and methods of a parent (superclass), promoting "
            "code reuse. The subclass can override methods to provide specialized behavior and can add "
            "new fields or methods. In Java, a class extends exactly one parent (single inheritance). "
            "In Python, a class can inherit from multiple parents (multiple inheritance); the Method "
            "Resolution Order (MRO) via C3 linearization determines which method is called. "
            "Calling super() invokes the parent's implementation within an overriding method. "
            "Inheritance represents an 'is-a' relationship (a Dog is an Animal). Overuse of deep "
            "inheritance hierarchies creates tight coupling; prefer composition ('has-a') when the "
            "relationship is not clearly an 'is-a'. The Liskov Substitution Principle states that "
            "subclass instances must be substitutable for parent instances without altering correctness."
        ),
    },
    {
        "id": "oop_polymorphism",
        "topic": "OOP",
        "text": (
            "Polymorphism allows objects of different classes to be treated as instances of a common "
            "supertype, with method calls resolved at runtime based on the actual object type. "
            "This is called dynamic dispatch or runtime polymorphism. Example: an Animal reference "
            "pointing to a Dog object calls Dog's speak() method, not Animal's. "
            "Compile-time polymorphism (method overloading) allows multiple methods with the same name "
            "but different parameter lists in languages like Java. Python does not support true "
            "overloading but achieves it with default arguments. Polymorphism enables the Open/Closed "
            "Principle: code is open for extension (add new subclasses) but closed for modification. "
            "Duck typing in Python is an informal form of polymorphism: if an object has the right "
            "methods, it works regardless of its actual type."
        ),
    },
    {
        "id": "oop_abstraction",
        "topic": "OOP",
        "text": (
            "Abstraction hides complex implementation details and exposes only what is necessary for "
            "the caller. It separates what an object does from how it does it. Abstract classes and "
            "interfaces are the primary tools: they define method contracts that concrete subclasses "
            "must fulfill. Python's abc module provides ABC (Abstract Base Class) and @abstractmethod "
            "to enforce this. A well-designed abstraction reduces cognitive load — a developer using "
            "a List does not need to know whether it is implemented as an array or linked list. "
            "Abstraction also appears at the system level: a REST API abstracts a database; a database "
            "abstracts disk I/O. Good abstractions are stable over time; leaky abstractions expose "
            "implementation details, creating hidden dependencies that break when internals change."
        ),
    },
    # ── JavaScript ───────────────────────────────────────────────────────────
    {
        "id": "js_closures",
        "topic": "JavaScript",
        "text": (
            "A closure is a function that retains access to variables from its enclosing lexical scope "
            "even after the outer function has returned. In JavaScript, every function forms a closure. "
            "This enables powerful patterns: factory functions that produce customised functions, "
            "data hiding by keeping variables out of global scope, and memoization caches. "
            "Example: a counter factory returns an increment function that closes over a private count variable. "
            "Closures are the mechanism behind module patterns (IIFE) that were common before ES6 modules. "
            "A common pitfall is closures inside loops: all iterations share the same variable reference, "
            "so using var in a for loop captures the final value. Fix with let (block-scoped) or an IIFE."
        ),
    },
    {
        "id": "js_promises_async",
        "topic": "JavaScript",
        "text": (
            "A Promise represents the eventual result of an asynchronous operation. It is in one of three "
            "states: pending, fulfilled, or rejected. .then() chains handle fulfillment; .catch() handles "
            "rejection; .finally() runs regardless. async/await is syntactic sugar over Promises: an "
            "async function always returns a Promise; await pauses execution until the Promise settles. "
            "Error handling with async/await uses try/catch blocks. Promise.all() runs multiple Promises "
            "in parallel and resolves when all resolve (or rejects at the first rejection). "
            "Promise.allSettled() waits for all regardless of outcome. "
            "Promise.race() resolves or rejects as soon as the first Promise settles. "
            "Avoid callback hell by converting nested callbacks to Promise chains or async/await."
        ),
    },
    {
        "id": "js_event_loop",
        "topic": "JavaScript",
        "text": (
            "JavaScript is single-threaded: only one piece of code executes at a time. The event loop "
            "enables non-blocking behaviour. When a script runs, synchronous code executes on the call stack. "
            "Asynchronous operations (setTimeout, fetch, I/O) are offloaded to Web APIs. When they complete, "
            "their callbacks enter the task queue (macrotask queue). The event loop moves a callback to the "
            "call stack only when the stack is empty. Microtasks (Promise callbacks, queueMicrotask) have "
            "higher priority than macrotasks and are processed before the next macrotask. "
            "This explains why a resolved Promise's .then() callback runs before a setTimeout(fn, 0) callback. "
            "Understanding the event loop is essential for debugging race conditions and ordering issues."
        ),
    },
    {
        "id": "js_es6_features",
        "topic": "JavaScript",
        "text": (
            "ES6 (ECMAScript 2015) introduced major language features. let and const provide block scoping "
            "unlike var's function scoping. Arrow functions (=>) inherit the enclosing this instead of "
            "defining their own, solving common this binding bugs. Template literals use backticks and ${} "
            "for string interpolation and multiline strings. Destructuring extracts values from arrays "
            "and objects: const {name, age} = person. Rest (...args) collects remaining elements; "
            "spread (...array) expands an iterable. Default parameters: function greet(name = 'Student'). "
            "Modules: export named values or a default; import them with import. "
            "Classes provide syntactic sugar over prototype-based inheritance. "
            "Map and Set offer better keyed collection alternatives to plain objects."
        ),
    },
    # ── SQL (expanded) ────────────────────────────────────────────────────────
    {
        "id": "sql_joins_deep",
        "topic": "SQL",
        "text": (
            "SQL JOINs combine rows from two tables based on a related column. "
            "INNER JOIN returns only rows where the join condition matches in both tables. "
            "LEFT JOIN (LEFT OUTER JOIN) returns all rows from the left table plus matched rows "
            "from the right; unmatched right columns are NULL. RIGHT JOIN is the mirror. "
            "FULL OUTER JOIN returns all rows from both tables, with NULLs where there is no match. "
            "CROSS JOIN returns the Cartesian product — every left row combined with every right row. "
            "SELF JOIN joins a table to itself, useful for hierarchical data (e.g., employee-manager). "
            "Join conditions use ON for explicit column matching or USING when column names are identical. "
            "Multiple JOINs chain left-to-right. Index the foreign key columns to make JOINs fast. "
            "Avoid SELECT * in JOINs — list only needed columns to prevent ambiguous column names."
        ),
    },
    {
        "id": "sql_aggregates_groupby",
        "topic": "SQL",
        "text": (
            "Aggregate functions compute a single result from a set of rows. COUNT(*) counts all rows; "
            "COUNT(column) counts non-NULL values. SUM, AVG, MIN, MAX work on numeric columns. "
            "GROUP BY groups rows sharing a value so aggregates apply per group: "
            "SELECT department, AVG(salary) FROM employees GROUP BY department. "
            "Every column in SELECT must either be in GROUP BY or wrapped in an aggregate function. "
            "HAVING filters groups after aggregation, unlike WHERE which filters rows before. "
            "Example: HAVING AVG(salary) > 50000 keeps only departments with high average pay. "
            "Window functions (OVER clause) apply aggregates without collapsing rows: "
            "ROW_NUMBER(), RANK(), LAG(), LEAD(), SUM() OVER (PARTITION BY ... ORDER BY ...). "
            "These are powerful for running totals, rankings, and time-series comparisons."
        ),
    },
    {
        "id": "sql_transactions_acid",
        "topic": "SQL",
        "text": (
            "A transaction groups multiple SQL statements so they either all succeed (COMMIT) "
            "or all fail (ROLLBACK), preserving data integrity. ACID properties define reliable transactions. "
            "Atomicity: all operations complete or none do. "
            "Consistency: the database moves from one valid state to another. "
            "Isolation: concurrent transactions do not see each other's intermediate state. "
            "Durability: committed changes survive system failures (written to disk). "
            "Isolation levels trade concurrency for safety: READ UNCOMMITTED (dirty reads allowed), "
            "READ COMMITTED (no dirty reads), REPEATABLE READ (no phantom rows in MySQL InnoDB), "
            "SERIALIZABLE (full isolation, lowest concurrency). "
            "Deadlocks occur when two transactions wait for each other's locks; databases detect and "
            "resolve them by rolling back one transaction. Keep transactions short to reduce lock contention."
        ),
    },
    # ── Operating Systems ─────────────────────────────────────────────────────
    {
        "id": "os_processes_threads",
        "topic": "operating systems",
        "text": (
            "A process is an instance of a running program with its own memory space, file handles, "
            "and OS resources. A thread is a unit of execution within a process; threads share the "
            "process's memory and resources but have their own stack and registers. "
            "Context switching between processes is expensive (full state save/restore); "
            "switching between threads of the same process is cheaper because memory mappings are shared. "
            "Concurrency with threads requires synchronisation: mutexes (mutual exclusion locks) prevent "
            "simultaneous access to shared data; semaphores control access to a pool of resources. "
            "Race conditions occur when output depends on non-deterministic thread scheduling. "
            "Deadlock: two threads each hold a lock the other needs and neither can proceed. "
            "Python's GIL (Global Interpreter Lock) prevents true parallel execution of Python threads; "
            "use multiprocessing for CPU-bound parallelism or asyncio for I/O-bound concurrency."
        ),
    },
    {
        "id": "os_memory_management",
        "topic": "operating systems",
        "text": (
            "Virtual memory gives each process the illusion of a large, private address space. "
            "The OS and hardware (MMU) translate virtual addresses to physical RAM addresses using "
            "page tables. Memory is divided into fixed-size pages (typically 4KB). "
            "When a process accesses a page not in RAM, a page fault occurs and the OS loads it from disk. "
            "Swapping moves entire processes to disk; paging moves individual pages. "
            "Memory allocation strategies: first fit, best fit, worst fit for variable-size segments. "
            "The heap is dynamically allocated (malloc/free in C, new/delete in C++); fragmentation "
            "wastes space over time. Garbage collectors (Java, Python) automate deallocation using "
            "reference counting, mark-and-sweep, or generational collection. "
            "Stack memory is automatically managed: function frames are pushed on call and popped on return."
        ),
    },
    # ── Design Patterns ───────────────────────────────────────────────────────
    {
        "id": "patterns_singleton",
        "topic": "design patterns",
        "text": (
            "The Singleton pattern ensures a class has only one instance and provides a global access point. "
            "Implementation: make the constructor private, store the instance in a static field, "
            "and provide a static getInstance() method that creates the instance on first call. "
            "Thread safety requires double-checked locking or an initialisation-on-demand holder. "
            "In Python, module-level objects are singletons by nature (module imported once, cached). "
            "Singletons are useful for logging, configuration, and connection pools but are often "
            "considered an anti-pattern because they introduce global state and make unit testing harder "
            "(hard to mock or replace). Dependency injection is a cleaner alternative in most cases: "
            "pass the shared instance as a constructor parameter rather than accessing it globally."
        ),
    },
    {
        "id": "patterns_observer",
        "topic": "design patterns",
        "text": (
            "The Observer pattern defines a one-to-many dependency: when a subject (publisher) changes "
            "state, all registered observers (subscribers) are notified automatically. "
            "Components: Subject (maintains observer list, attach/detach/notify methods), "
            "Observer (interface with update() method), ConcreteObserver (implements update). "
            "This decouples the subject from its observers — the subject does not know observer details. "
            "Applications: GUI event systems, model-view architectures (MVC), pub/sub messaging, "
            "real-time dashboards, and reactive programming (RxJS, Python asyncio). "
            "Push model: subject sends data with the notification. "
            "Pull model: subject sends only a reference; observers fetch needed data. "
            "Avoid update storms: an observer's update triggering further notifications can cascade."
        ),
    },
    {
        "id": "patterns_factory",
        "topic": "design patterns",
        "text": (
            "The Factory Method pattern defines an interface for creating an object but lets subclasses "
            "decide which class to instantiate, deferring object creation to subclasses. "
            "The Abstract Factory pattern provides an interface for creating families of related objects "
            "without specifying their concrete classes. "
            "Benefits: decouples the client from concrete implementations; easy to extend with new types "
            "by adding a new subclass without changing existing code (Open/Closed Principle). "
            "A simple factory (not GoF) is a helper class or method that centralises object creation logic, "
            "choosing the right class based on a parameter. "
            "Use factories when: the exact type is not known until runtime; object creation is complex "
            "or involves multiple steps; you want to enforce a common creation interface across a family."
        ),
    },
    # ── Git / Version Control ─────────────────────────────────────────────────
    {
        "id": "git_basics",
        "topic": "Git",
        "text": (
            "Git is a distributed version control system where every developer has a full copy of the "
            "repository history. Core concepts: working directory (files on disk), staging area (index, "
            "what will be in the next commit), repository (.git folder with all history). "
            "Key commands: git init creates a repo; git clone copies a remote repo; git add stages changes; "
            "git commit saves a snapshot with a message; git status shows current state; "
            "git log shows commit history; git diff compares changes. "
            "Branching: git branch creates; git checkout or git switch changes branch; "
            "git merge integrates another branch. Rebasing rewrites commit history onto a new base. "
            "git stash temporarily shelves uncommitted changes. git remote manages connections to "
            "remote repositories; git push sends commits; git pull fetches and merges remote changes."
        ),
    },
    {
        "id": "git_branching_workflow",
        "topic": "Git",
        "text": (
            "Git Flow is a branching model with two permanent branches: main (production) and develop "
            "(integration). Feature branches branch off develop and merge back via pull requests. "
            "Release branches freeze a version for testing. Hotfix branches fix production bugs off main. "
            "GitHub Flow is simpler: only main is permanent; all work happens on short-lived feature "
            "branches that merge to main via pull requests after code review. "
            "Trunk-based development pushes small commits directly to main (or short-lived branches "
            "merged within a day), relying on feature flags to hide incomplete work. "
            "Commit messages: use imperative mood ('Add feature' not 'Added'), keep the subject under "
            "72 characters, and use the body to explain why not what. "
            "Interactive rebase (git rebase -i) squashes, reorders, or edits commits before merging."
        ),
    },
    # ── Python (additional) ───────────────────────────────────────────────────
    {
        "id": "python_oop",
        "topic": "Python",
        "text": (
            "Python classes are defined with the class keyword. __init__ is the constructor. "
            "self is the first parameter of every instance method, referring to the instance. "
            "Class variables are shared across all instances; instance variables are per-object. "
            "Python supports multiple inheritance; the MRO (C3 linearization) defines method resolution order. "
            "__str__ returns a human-readable string; __repr__ returns a developer-facing representation. "
            "Properties (@property, @setter) provide controlled attribute access. "
            "__dunder__ (magic/dunder) methods enable operator overloading: __add__, __len__, __eq__. "
            "Abstract base classes (abc.ABC, @abstractmethod) enforce interface contracts. "
            "Dataclasses (@dataclass) auto-generate __init__, __repr__, and __eq__ from field definitions, "
            "reducing boilerplate significantly for data-holding classes."
        ),
    },
    {
        "id": "python_error_handling",
        "topic": "Python",
        "text": (
            "Python uses try/except/else/finally for error handling. except catches specific exception types; "
            "always catch the most specific exception first. except Exception as e captures the exception object. "
            "Use else after try to run code only when no exception was raised. "
            "finally always runs — use it to release resources (close files, release locks). "
            "raise re-raises the current exception or raises a new one. "
            "Custom exceptions subclass Exception (or a more specific base). "
            "Context managers (with statement) use __enter__ and __exit__ to guarantee cleanup — "
            "file objects and database connections should always use with. "
            "The contextlib.contextmanager decorator lets you write generators as context managers. "
            "Never use bare except: — it catches everything including SystemExit and KeyboardInterrupt."
        ),
    },
    # ── Computer Science Fundamentals ─────────────────────────────────────────
    {
        "id": "cs_recursion",
        "topic": "computer science",
        "text": (
            "Recursion is when a function calls itself to solve a smaller instance of the same problem. "
            "Every recursive function needs a base case (termination condition) and a recursive case "
            "that moves toward it. Classic examples: factorial(n) = n * factorial(n-1), base case n=0; "
            "Fibonacci; tree/graph traversal; merge sort; quicksort. "
            "Each call adds a frame to the call stack; deep recursion risks a stack overflow. "
            "Tail recursion: the recursive call is the very last operation — some compilers optimise "
            "it to a loop (Python does not). "
            "Memoization (caching results of subproblems) converts naive exponential recursion to linear. "
            "Mutual recursion: function A calls B, B calls A — valid if both have reachable base cases. "
            "Recursive thinking: trust that the recursive call solves the smaller problem, then build the "
            "full solution using that result."
        ),
    },
    {
        "id": "cs_graph_theory",
        "topic": "computer science",
        "text": (
            "A graph G = (V, E) consists of vertices (nodes) and edges (connections). "
            "Directed graphs (digraphs) have one-way edges; undirected graphs have two-way edges. "
            "Weighted graphs assign a cost to each edge. "
            "Representations: adjacency matrix (O(V²) space, O(1) edge lookup); "
            "adjacency list (O(V+E) space, efficient for sparse graphs). "
            "Breadth-First Search (BFS) explores level by level using a queue — finds shortest path in "
            "unweighted graphs. Depth-First Search (DFS) explores as deep as possible using a stack "
            "or recursion — used for cycle detection, topological sort, connected components. "
            "Dijkstra's algorithm finds shortest paths in weighted graphs with non-negative edges O((V+E) log V). "
            "Topological sort orders vertices so all directed edges point forward — only possible in DAGs. "
            "Minimum spanning tree (Kruskal's, Prim's) connects all vertices with minimum total edge weight."
        ),
    },
]


if __name__ == "__main__":
    print(f"Seeding {len(DOCS)} knowledge chunks into ChromaDB...")
    embed_documents(DOCS)
    print("Done. ChromaDB collection 'nexus_knowledge' is ready.")