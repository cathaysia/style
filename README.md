# Cathaysia Style

Reusable style hooks and maintenance commands for Cathaysia repositories.

## Pre-commit

Add the hook repository to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/cathaysia/style
    rev: v0.1.1
    hooks:
      - id: check-line-length
      - id: move-module-mod
      - id: compact_workspace_deps
      - id: full-qualify-log
```

Hooks run from the consuming repository root. Commands that scan files use the
current working directory as the default root.

## Commands

- `cathaysia-line-length`: fail when passed source files exceed the configured
  line limit.
- `cathaysia-move-module`: move `module.rs` into `module/mod.rs` when both the
  sibling file and non-empty module directory exist.
- `cathaysia-compact-workspace-deps`: rewrite `name = { workspace = true }` to
  `name.workspace = true` in `Cargo.toml` files.
- `cathaysia-qualify-tracing-macros`: rewrite bare Rust tracing macro calls to
  `tracing::macro!` and remove redundant macro imports.

## Development

```sh
PYTHONPATH=src python -m unittest discover -s tests
```
