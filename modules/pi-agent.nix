{ config, lib, pkgs, ... }:
let
  cfg = config.piAgent;
  mypiPkg = pkgs.callPackage ../packages/mypi-agent-cli.nix { };
  mypiBin = pkgs.writeShellScriptBin "mypi" ''
    set -euo pipefail
    export MYPI_AGENT_ROOT="${cfg.root}"
    exec ${mypiPkg}/bin/mypi "$@"
  '';
  piAgentBin = pkgs.writeShellScriptBin "pi-agent" ''
    set -euo pipefail
    launcher="${cfg.root}/bin/pi-agent"
    if [ ! -x "$launcher" ]; then
      echo "pi-agent is not installed yet; run: mypi sync" >&2
      exit 1
    fi
    exec "$launcher" "$@"
  '';

  bootstrapCmd = if cfg.bootstrap.mode == "manual_only" then "" else ''
    if [ ! -f .pi/settings.json ] || [ "${cfg.bootstrap.mode}" = "every_entry" ]; then
      mypi sync >/dev/null 2>&1 || true
    fi
  '';
in
{
  options.piAgent = {
    enable = lib.mkEnableOption "MYPI agent tooling";

    sourceRoot = lib.mkOption {
      type = lib.types.str;
      default = toString ../.;
      description = "Reserved for future source overrides.";
    };

    root = lib.mkOption {
      type = lib.types.str;
      default = ".agents/pi";
      description = "Project-relative root for MYPI agent artifacts.";
    };

    bootstrap.mode = lib.mkOption {
      type = lib.types.enum [ "first_entry_only" "manual_only" "every_entry" ];
      default = "first_entry_only";
      description = "Bootstrap sync policy on shell entry.";
    };
  };

  config = lib.mkIf cfg.enable {
    packages = [ mypiPkg mypiBin piAgentBin ];

    enterShell = lib.mkAfter ''
      ${bootstrapCmd}
    '';
  };
}
