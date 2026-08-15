---
tags: browser, node
---

# structuredClone() for real deep copies

`JSON.parse(JSON.stringify(value))` is the deep-copy trick everyone reaches for,
and it quietly destroys `Date`, `Map`, `Set`, `BigInt`, `undefined` and cyclic
references. `structuredClone()` is a global in every modern browser and in
Node 17+:

```js
const original = {
  when: new Date(),
  seen: new Set([1, 2, 3]),
  nested: { deep: [1, 2, 3] },
};
original.self = original;

const copy = structuredClone(original);
copy.nested.deep.push(4);
original.nested.deep; // [1, 2, 3] — untouched
copy.when instanceof Date; // true
copy.self === copy; // true, the cycle survived
```

What it cannot do:

* Functions, DOM nodes and symbols throw `DataCloneError`.
* Prototypes are not preserved — a class instance comes back as a plain object
  with the same own properties.
* Property descriptors (getters, `writable: false`) are lost; getters are
  evaluated and stored as plain values.

It also takes a `transfer` list for handing an `ArrayBuffer` over without
copying it:

```js
const buffer = new ArrayBuffer(1024);
const moved = structuredClone({ buffer }, { transfer: [buffer] });
buffer.byteLength; // 0 — the original is detached
```
