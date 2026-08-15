---
tags: colors, custom-properties
---

# color-mix() makes one accent colour into a palette

`color-mix()` blends two colours in a colour space of your choosing, which means
a theme can be derived from a single custom property instead of a dozen
hand-picked hex codes:

```css
:root {
  --accent: #9a3412;
  --accent-soft: color-mix(in oklab, var(--accent) 12%, white);
  --accent-strong: color-mix(in oklab, var(--accent) 80%, black);
  --accent-ghost: color-mix(in srgb, var(--accent) 15%, transparent);
}
```

Notes from using it:

* `in oklab` (or `oklch`) mixes perceptually, so a 50% blend actually looks
  halfway. `in srgb` matches what image editors do and is the right choice when
  mixing with `transparent`.
* The percentage attaches to a colour, not to the function. If both colours have
  one and they do not add up to 100%, the values are normalised.
* It composes with `light-dark()` and works anywhere a `<color>` is accepted,
  including inside gradients and shadows.

Handy for hover states that follow whatever accent the page happens to use:

```css
button:hover { background: color-mix(in oklab, var(--accent) 85%, black); }
```
