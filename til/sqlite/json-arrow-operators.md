---
tags: json, queries
---

# SQLite has JSON arrow operators

SQLite 3.38.0 (February 2022) added the two operators PostgreSQL users already
know, so `json_extract()` calls get much shorter:

```sql
SELECT
  payload -> '$.user'        AS user_json,   -- returns JSON
  payload ->> '$.user.name'  AS name         -- returns TEXT/INTEGER/REAL/NULL
FROM events;
```

The rule is short: `->` always gives you back JSON (a quoted string stays
quoted), `->>` gives you a plain SQL value. Comparing with `->` is the classic
mistake:

```sql
WHERE payload -> '$.status' = 'active'    -- never matches: left side is '"active"'
WHERE payload ->> '$.status' = 'active'   -- works
```

The right-hand side may also be a bare key or an array index, which is expanded
to a path for you:

```sql
SELECT payload -> 'user' ->> 'name', tags ->> 0 FROM events;
```

To make these queries fast, index the expression directly:

```sql
CREATE INDEX events_status ON events (payload ->> '$.status');
```

Check your version with `SELECT sqlite_version();` — the system SQLite on older
distributions predates 3.38 and will report a syntax error.
