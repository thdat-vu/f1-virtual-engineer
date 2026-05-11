# Redis — what it is, and why we'd add it to this project

Written as a prep note: half a Redis primer for a backend-engineer interview,
half a design rationale for slice D of issue #100 in this repo.

---

## 1. Mental model

**Redis = in-memory key-value store with a single-threaded command loop.**
Three things to internalise:

1. **In-memory.** Data lives in RAM, so every operation (`GET`, `SET`, `INCR`)
   is sub-millisecond. Disk is only used to persist (RDB snapshots + AOF
   append-only log), not to serve reads/writes.
2. **Single-threaded command execution.** From Redis 6 there are I/O threads
   for the network layer, but commands themselves still run one-at-a-time.
   The consequence is that **every single command is atomic** — no locks
   required. `INCR counter` is safe under concurrency, no `SELECT … FOR
   UPDATE` dance like in SQL.
3. **Data structures are first-class.** Not "value is a blob, parse it
   client-side" — Redis understands String, Hash, List, Set, Sorted Set,
   Stream, HyperLogLog, Geo, and ships purpose-built ops (`ZADD`/`ZRANGE`,
   `XADD`/`XREAD`, `PFCOUNT`, …).

In an interview, do not stop at "Redis is a cache". Show you know when to
pick Redis vs Postgres vs Kafka, and what its failure modes look like.

---

## 2. Core features and the canonical use cases

### 2.1 String + TTL → distributed cache

`SET key value EX 3600` — store with a TTL. This is ~80% of Redis usage in
the real world.

- **Cache-aside (lazy load)**: app checks cache → miss → query the source of
  truth → write to cache → return.
- **Write-through / write-behind**: more complex, less common for plain
  caching.
- **Cache invalidation is the hard part.** TTL is the *lazy* approach
  (accept staleness); explicit `DEL` is the *correct* approach (requires
  knowing when source-of-truth data changed).

### 2.2 INCR / INCRBY → counters and rate limiters

`INCR user:123:requests` + `EXPIRE` → an atomic counter. Token-bucket and
fixed-window limiters are just a handful of commands plus a Lua script to
make the whole thing atomic.

### 2.3 SETNX / `SET … NX` → distributed lock

`SET lock:job-42 worker-id NX EX 30` — sets only if absent. Pattern is used
for:

- **Single-flight cache miss.** When 100 users request the same uncached
  key, only one worker actually computes; the rest wait or retry on the
  warmed cache. Prevents "thundering herd" / "cache stampede".
- **Job de-duplication.** Cron fires every 5 minutes; only the first
  instance to acquire the lock actually runs.
- **Correctness warning.** Naive SETNX is *not* perfectly safe — the token
  must be unique so a worker doesn't release someone else's lock after its
  own expired. Production uses **Redlock** (multi-node) or accepts the risk
  with careful design.

### 2.4 Hash → object / struct storage

`HSET user:123 name "Dat" email "..."` — dict-like. Use when you want to
update individual fields instead of rewriting the whole JSON blob. Smaller
memory footprint than `String` for many small fields thanks to ziplist /
listpack encoding.

### 2.5 Sorted Set (ZSET) → ranking, leaderboard, time-series index

`ZADD leaderboard 1500 user:123` + `ZREVRANGE leaderboard 0 9` → top 10.
O(log N) insert, O(log N + M) range query.

- **Leaderboards** (driver ratings, game scores)
- **Time-bucketed feeds** (score = timestamp)
- **Delayed job queue** (score = `run_at_unix`; poller does
  `ZRANGEBYSCORE 0 now`)

### 2.6 Stream (XADD / XREAD / XGROUP) → durable message queue

Since Redis 5. An append-only log, like Kafka miniature. Supports consumer
groups, ack, replay. Use for:

- Background job queues (Celery + RabbitMQ replacement at small-to-medium
  scale)
- Lightweight event sourcing
- Fan-out to multiple independent consumers

### 2.7 Pub/Sub

`PUBLISH channel msg` + `SUBSCRIBE channel`. **Fire-and-forget.** No
persistence — an offline subscriber misses the message. Totally different
from Streams. Use for real-time notifications, never for job queues.

### 2.8 Expiration + LRU / LFU eviction

When memory hits the configured limit, Redis evicts according to your
policy (`noeviction`, `allkeys-lru`, `volatile-lru`, `allkeys-lfu`, …).
This is what makes Redis behave like a *bounded* cache instead of an
infinite store.

### 2.9 Lua scripting (`EVAL`) / Functions (Redis 7+)

Server-side scripts run atomically — they let you combine multiple
commands into a single atomic op. The classic example is a **precise
token-bucket rate limiter**: read the bucket, check capacity, decrement,
write it back, all inside one `EVAL`.

### 2.10 HyperLogLog (PFADD / PFCOUNT)

Approximate cardinality with **~12KB of memory regardless of set size**.
Error ~0.81%. Use for "unique users today", "unique searches per query",
anywhere you need rates rather than exact counts.

---

## 3. Production patterns that show up in interviews

| Pattern | Problem solved | Risk / trade-off |
| --- | --- | --- |
| Cache-aside (lazy loading) | Reduce DB load | May serve stale data; stampede risk without a lock |
| Write-through | Cache is always fresh | Higher write latency; more complex |
| Distributed lock | Single-flight, dedup | Lock leak on worker crash; needs unique token + expiry |
| Rate limit (token bucket) | Protect backend / enforce quota | Needs Lua for atomicity; single-cell vs global trade-off |
| Idempotency key | Avoid double-charge on client retry | TTL sizing, key design |
| Session store | Stateless app servers | SPOF without HA (Sentinel / Cluster) |
| Job queue (Stream / List) | Async tasks | Retry, dead-letter, idempotent workers |

---

## 4. When Redis is the *wrong* choice

- **Source of truth for valuable data.** RDB/AOF are not on par with
  Postgres for durability; memory is bounded.
- **Dataset >> RAM.** Redis is not a disk-backed store. Cluster sharding
  helps but the cost climbs fast.
- **Complex queries.** No joins, no natural secondary indexes. If you find
  yourself reaching for `KEYS pattern:*`, you're using Redis wrong (and
  `KEYS` blocks the command loop).
- **Strong consistency across multiple keys.** Replication is async; a
  failover can lose writes. Do not use Redis for a payment ledger.
- **Long-running operation in a single command.** Because of the
  single-threaded loop, a `KEYS *` on 10 M keys stalls every other request
  behind it.

---

## 5. Applied to this project — slice D options

Concrete uses for Redis in this codebase, ordered most practical →
most ambitious.

### Option A — Replace the in-process TTLCache with Redis (the literal slice D)

- **Today's problem.** The cache from slice B is per-process. Run multiple
  uvicorn workers (`--workers 4`) or multiple pods and each process keeps
  its own cache → the same query hits FastF1 several times in parallel.
- **With Redis.** `SET fastf1:telemetry:<sha> <json> EX 3600`. All workers
  share one cache, restarts don't wipe warmup (Redis owns the lifecycle).
- **Effort.** ~1 day. Refactor `_ttl_cached` to take a pluggable backend,
  fall back to the in-process cache when Redis is unreachable.
- **Demo value.** Clear story for interviews: "scaled from 1 worker to N
  with shared cache; hit rate climbed from 40% to 90%."

### Option B — Distributed rate limiter

- **Today's problem.** `slowapi` uses an in-memory store. With 4 workers
  the hard limit `3/10s` effectively becomes `12/10s`.
- **With Redis.** `slowapi` ships a `RedisStore`; or hand-roll a Lua-based
  token bucket for exact semantics.
- **Effort.** A few hours.
- **Demo value.** Strong interview material — concrete race condition,
  atomicity, Lua scripting. "I moved the limiter from in-memory to a
  Redis backend with an atomic Lua script."

### Option C — Single-flight lock against cache stampede

- **Problem.** Five users requesting `/telemetry 2024 Monza R VER` on a
  cold cache all hit FastF1 (5–30 s each).
- **Pattern.** `SET lock:telemetry:<key> 1 NX EX 60`. Whoever acquires the
  lock fetches; others retry after ~1s and find the warmed cache.
- **Effort.** Half a day.
- **Demo value.** Excellent interview material — the textbook "thundering
  herd" problem.

### Option D — Background worker via Redis Streams

- Issue #100 literally says: *"Web handlers do not import fastf1 at all."*
  The faithful interpretation is a separate worker process.
- **Pattern.** Handler `XADD jobs:fastf1 *` to enqueue → worker process
  `XREADGROUP` consumes → result lands in cache → handler polls the cache
  or pushes via SSE/WebSocket.
- **Effort.** 2–3 days, lots of moving parts.
- **Risk.** Complexity spike for an indie MVP. May read as
  "over-engineering" in an interview if user count is still zero.

### Option E — Idempotency key for `/analyze`

- A double-click on "Analyze" today triggers two LLM calls — cost waste +
  rate-limit risk.
- **Pattern.** Client sends `Idempotency-Key: <uuid>` header. Server
  `SETNX idem:<key> <response> EX 600`. Subsequent calls with the same key
  return the stored response.
- **Effort.** Half a day.
- **Demo value.** Very "production-engineer" — Stripe and payment APIs at
  Grab all do this. Worth talking about in an interview.

---

## 6. Recommendation for slice D

For **this project** (indie MVP, primarily one user — me): **Option A** is
the literal slice D and the cleanest scope. Combining it with **B + C**
produces the most interview-friendly PR.

For an **interview** I plan to tell three stories from the existing slices:

1. *Why I measured first, optimised second* — slice A (timing middleware)
   before slice B.
2. *Why I refuse to cache fallback results* — slice B's `is_good` predicate.
   This is the kind of detail juniors miss.
3. *Why I picked gzipped JSON over parquet for slice C* — match format to
   data shape, avoid unnecessary deps on the import path.

Adding slice D with Redis (A + B + C) lets me add a fourth story:

- *Why a single-flight distributed lock needs a unique token plus an
  expiry* — a classic interview question about distributed lock
  correctness.

---

## 7. References (further reading)

- Redis docs — [Data types](https://redis.io/docs/data-types/)
- Redis docs — [Distributed locks](https://redis.io/docs/manual/patterns/distributed-locks/)
- "Designing Data-Intensive Applications", ch. 7 (transactions) and ch. 8
  (the trouble with distributed systems) — the right lens for the Redlock
  debate.
- Martin Kleppmann vs antirez: [How to do distributed locking](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html)
  and [Is Redlock safe?](http://antirez.com/news/101) — read both, that's
  the actual interview-grade depth on this topic.
