---
tags: cli, csv
---

# Import a CSV into SQLite from the shell

The `sqlite3` CLI can create a table from a CSV header row in two lines:

```
$ sqlite3 data.db
sqlite> .mode csv
sqlite> .import measurements.csv measurements
```

If the table does not exist yet, the first row of the file becomes the column
names (all typed `TEXT`). If it *does* exist, every row of the file — including
the header — is inserted as data, which is why imports so often end up with a
literal `"id","name"` row at the top. Skip it explicitly:

```
sqlite> .import --skip 1 measurements.csv measurements
```

Doing it in one shot from a normal shell:

```bash
sqlite3 data.db '.mode csv' '.import measurements.csv measurements' \
  'SELECT count(*) FROM measurements;'
```

Two things worth knowing afterwards:

* Everything arrives as text, so `SELECT max(value)` sorts lexicographically.
  Create the table with real types first, then `.import --skip 1`.
* `.mode csv` also changes how query *output* is formatted, so run
  `.mode box` (or `.mode column`) afterwards if you want readable results.
