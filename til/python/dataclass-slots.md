---
tags: dataclasses, performance
---

# Dataclasses can generate `__slots__` for you

Since Python 3.10, `@dataclass` takes a `slots=True` argument. It builds
`__slots__` from the annotated fields, which drops the per-instance `__dict__`:
attribute access gets a little faster and instances get noticeably smaller.

```python
from dataclasses import dataclass

@dataclass(slots=True)
class Point:
    x: float
    y: float

p = Point(1.0, 2.0)
p.z = 3.0  # AttributeError: 'Point' object has no attribute 'z'
```

A quick size comparison:

```python
import sys
from dataclasses import dataclass

@dataclass
class Wide:
    x: float
    y: float

@dataclass(slots=True)
class Slim:
    x: float
    y: float

sys.getsizeof(Wide(1.0, 2.0)) + sys.getsizeof(Wide(1.0, 2.0).__dict__)  # 152
sys.getsizeof(Slim(1.0, 2.0))                                          # 48
```

## The catch

`slots=True` cannot add `__slots__` to the class in place, so the decorator
builds and returns a **brand new class**. Anything holding a reference to the
original class object before decoration — a registry, a previously applied
decorator, a `super()` call compiled against the old class — still points at the
class that got thrown away.

Two consequences worth remembering:

* Weak references stop working unless you also pass `weakref_slot=True`
  (Python 3.11+).
* Decorators listed *below* `@dataclass(slots=True)` run against the old class,
  so ordering matters more than usual.
