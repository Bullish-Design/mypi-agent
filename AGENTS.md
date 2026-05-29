# AGENTS

## Allium Spec Location

All `.allium` files are located under:

- `.scratch/specs`

Do not place `.allium` files outside this directory.
Specs may be nested in any subdirectory under `.scratch/specs`.
Always recursively search all directories under `.scratch/specs` for `.allium` files.

## Running Commands

All project commands must be run inside the devenv shell. Use the agent bootstrap script to run commands:

```bash
./agent-devboot.sh <command>
```

Examples:

```bash
./agent-devboot.sh mypi sync
./agent-devboot.sh mypi doctor
./agent-devboot.sh pytest
./agent-devboot.sh allium --help
```

Do not run `mypi`, `allium-cli`, `pytest`, or other project tools directly — they are only available inside the devenv shell.

## Allium CLI Availability

`allium-cli` is available inside the devenv shell.

For validation, run `allium-cli` commands via:

```bash
./agent-devboot.sh allium --help
```
