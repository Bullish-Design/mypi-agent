# AGENTS

## Allium Spec Location

All `.allium` files are located under:

- `.scratch/specs`

Do not place `.allium` files outside this directory.
Specs may be nested in any subdirectory under `.scratch/specs`.
Always recursively search all directories under `.scratch/specs` for `.allium` files.

## Allium CLI Availability

`allium-cli` is available inside the `devenv` shell.

Use it via:

```bash
devenv shell -- allium --help
```

For validation, run `allium-cli` commands from within `devenv shell`.
