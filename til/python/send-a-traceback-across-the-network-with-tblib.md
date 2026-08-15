---
tags: tblib, pickle, loguru, exceptions
date: 2026-08-15
---

# Send a traceback across the network with tblib

Our server has no route to the Elastic cluster, but the client that calls it
does. So the server has to hand its failures to the client and let the client do
the logging — which means an exception has to survive a trip over the wire with
its traceback still attached.

Pickle alone does not manage that. `BaseException.__reduce__` only stores the
class and `args`, so `__traceback__`, `__cause__` and `__context__` all come
back empty:

```python
import pickle

try:
    try:
        raise ValueError("low")
    except ValueError as e:
        raise RuntimeError("high") from e
except Exception as exc:
    restored = pickle.loads(pickle.dumps(exc))

print(restored.__traceback__, restored.__cause__)   # None None
```

You get the *what* and lose the *where*, which is the half that matters at 3am.

## tblib fills in the gap

[tblib](https://github.com/ionelmc/python-tblib) registers `copyreg` reducers
that flatten a traceback into plain data — filename, line number, function name,
and a link to the next frame — and rebuild a real traceback object on the far
side. Install it on **both** ends.

Server, at the edge where the request fails:

```python
import pickle

from tblib import pickling_support

from myapp.errors import AppError  # import the exception classes first, see below

pickling_support.install()


def handle_request():
    try:
        query_db()
    except AppError as exc:
        raise RuntimeError("request failed") from exc


try:
    handle_request()
except Exception as exc:
    return_to_client(pickle.dumps(exc))   # ~750 bytes for a short stack
```

Client, which can reach Elastic:

```python
import pickle

from tblib import pickling_support

pickling_support.install()

from loguru import logger

restored = pickle.loads(blob)
logger.opt(exception=restored).error("Server-side failure")
```

`logger.opt(exception=...)` takes the exception object directly, so there is no
need for the `raise restored.with_traceback(...)` dance inside a `try` block
just to give the logger something to read from `sys.exc_info()`. Re-raising also
appends the re-raise line as an extra frame; `opt` does not.

What lands in Elastic is the server's stack, cause chain and all:

```
Traceback (most recent call last):
  File ".../app.py", line 15, in handle_request
    query_db()
  File ".../app.py", line 11, in query_db
    raise AppError("connection refused")
myapp.errors.AppError: connection refused

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File ".../app.py", line 17, in handle_request
    raise RuntimeError("request failed") from exc
RuntimeError: request failed
```

## Four things that bit me

**`install()` snapshots the exception classes that exist right now.** With no
arguments it walks `BaseException.__subclasses__()` once and registers a reducer
for each. Any exception class imported *after* that call falls back to the
default reducer and quietly loses its traceback — which showed up as a cause
chain where the outer exception had a stack and the inner one did not. Either
import your error modules before calling `install()`, or scope it per exception
right before pickling:

```python
pickling_support.install(exc)   # follows __cause__/__context__ and the group members
```

**The client has to be able to import the exception class**, under the same
module path. `pickle.loads` of a server-only `AppError` dies with
`ModuleNotFoundError` before you ever get to log it. Shared error types belong
in a package both sides install; anything else should be converted to a builtin
exception on the server before it goes out.

**Source lines are read locally at render time.** The pickle carries file paths
and line numbers, not code. If the client has no copy of the server's source the
traceback prints frames with no code under them, and if it has a *different
version* checked out at that path, it cheerfully prints the wrong line. Line
numbers plus function names are the trustworthy part.

**Locals are dropped**, so loguru's `diagnose=True` annotations are empty for
the server frames. `install` can capture them, as long as you reduce them to
something safely picklable:

```python
pickling_support.install(get_locals=lambda frame: {k: repr(v) for k, v in frame.f_locals.items()})
```

Reprs only — do not ship live objects, and remember that locals are exactly
where connection strings and tokens hang out.

One cosmetic note: loguru's default `backtrace=True` walks `f_back` from the
rebuilt frames and ends up printing two `tblib/pickling_support.py` frames in
the middle of the trace. `logger.add(sink, backtrace=False, diagnose=False)` on
the client sink gives a clean stack.

## When not to bother

This is `pickle`, so it is only safe on a trusted internal channel — never
`loads` a blob from anywhere you would not run code from. If the boundary is not
trusted, or the client is not Python, send
`"".join(traceback.format_exception(exc))` as a string field instead. You lose
the ability to re-raise and inspect, but a preformatted stack in an Elastic
document reads exactly the same.
