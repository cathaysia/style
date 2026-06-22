# Cathaysia Style

Reusable style hooks and maintenance commands for Cathaysia repositories.

## Pre-commit

Add the hook repository to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/cathaysia/style
    rev: v0.1.7
    hooks:
      - id: check-line-length
      - id: ast-grep-rules
      - id: move-module-mod
      - id: compact_workspace_deps
      - id: full-qualify-log
```

Hooks run from the consuming repository root.

## Commands

- `cathaysia-line-length`: fail when passed source files exceed the configured
  line limit.
- `cathaysia-ast-grep`: run the packaged ast-grep rules and apply rewrites.
- `cathaysia-move-module`: move passed `module.rs` files into `module/mod.rs`
  when the matching non-empty module directory exists.
- `cathaysia-compact-workspace-deps`: rewrite `name = { workspace = true }` to
  `name.workspace = true` in passed `Cargo.toml` files.
- `cathaysia-qualify-tracing-macros`: rewrite bare Rust tracing macro calls to
  `tracing::macro!` and remove redundant macro imports.

## Ast-grep Rules

Rules live under `src/cathaysia_style/ast_grep_rules/`. The root
`sgconfig.yml` loads that directory for local development; the packaged hook
uses the bundled `sgconfig.yml`.

- `rust-no-return`: convert an `if` block at the end of a Rust function to an
  early return.

## Development

```sh
PYTHONPATH=src python -m unittest discover -s tests
```
