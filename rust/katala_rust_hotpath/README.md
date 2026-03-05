# katala_rust_hotpath

Hot-path Rust extension (PyO3) for KQ/inf math-logic runtime.

## Build (maturin)

```bash
cd rust/katala_rust_hotpath
maturin develop --release
```

If the extension is not installed, Python automatically falls back to pure-Python implementations.

## Exposed functions

- `invariant_preservation_score(...)`
- `dense_dependency_edges(...)`
