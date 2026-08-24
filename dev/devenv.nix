# Non-Allium development tooling for MYPI-Agent.
{ pkgs, ... }:

{
  packages = [
    pkgs.git
    pkgs.uv
  ];

  languages.python = {
    enable = true;
    package = pkgs.python313;
    venv.enable = true;

    uv = {
      enable = true;
      sync = {
        enable = true;
        allExtras = true;
      };
    };
  };

  # devman — the automation plane (CONCEPT.md §5). `base` alone: this repository
  # ships no scheduled work and writes none of its own files. Lives here, in the
  # dev-only layer, so consumers who `imports: - mypi-agent` never see it.
  devman = {
    enable = true;
    project = "mypi-agent";
    groups = [ "base" ];
  };

  # https://devenv.sh/tasks/
  #
  # The two task names the `base` group calls (groups/base/README.md). devenv
  # owns each implementation; Dagu owns the composition (§6). `uv run --extra
  # dev` rather than bare names: the venv bin is on the interactive shell's PATH
  # but not on the task runner's PATH (STAGE_7_LOG.md, wave 2b). `ruff check .`
  # is the repo's own full scope; the tree carries 16 findings today (recorded,
  # not repaired).
  tasks = {
    "mypi-agent:lint".exec = "uv run --extra dev ruff check .";
    "mypi-agent:test".exec = "uv run --extra dev pytest";

    "base:check".after = [ "mypi-agent:lint" ];
    "base:test".after = [ "mypi-agent:test" ];
  };
}
