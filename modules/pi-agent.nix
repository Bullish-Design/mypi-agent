{ config, lib, pkgs, ... }:
let
  cfg = config.piAgent;
  cfgRootEscaped = lib.escapeShellArg cfg.root;
  cfgBootstrapModeEscaped = lib.escapeShellArg cfg.bootstrap.mode;
  mypiPkg = pkgs.callPackage ../packages/mypi-agent-cli.nix { };
  mypiBin = pkgs.writeShellScriptBin "mypi" ''
    set -euo pipefail
    root_rel=${cfgRootEscaped}
    if [ -n "''${DEVENV_ROOT:-}" ]; then
      cd "$DEVENV_ROOT"
    fi
    export MYPI_AGENT_ROOT="$root_rel"
    exec ${mypiPkg}/bin/mypi "$@"
  '';
  piAgentBin = pkgs.writeShellScriptBin "pi-agent" ''
    set -euo pipefail
    root_rel=${cfgRootEscaped}
    project_root="''${DEVENV_ROOT:-$PWD}"
    launcher="$project_root/$root_rel/bin/pi-agent"
    if [ ! -x "$launcher" ]; then
      echo "pi-agent is not installed yet; run: mypi sync" >&2
      exit 1
    fi
    exec "$launcher" "$@"
  '';

  npmEnvCmd = ''
    root_rel=${cfgRootEscaped}
    project_root="''${DEVENV_ROOT:-$PWD}"
    export MYPI_PROJECT_ROOT="$project_root"
    export NPM_CONFIG_PREFIX="$MYPI_PROJECT_ROOT/$root_rel/npm-global"
    export NPM_CONFIG_CACHE="$MYPI_PROJECT_ROOT/$root_rel/.npm-cache"
    export NPM_CONFIG_AUDIT="false"
    export NPM_CONFIG_FUND="false"
    export MYPI_PI_PACKAGE_NAME=${lib.escapeShellArg cfg.piPackageName}
    export MYPI_PI_PACKAGE_VERSION=${lib.escapeShellArg (if cfg.piPackageVersion == null then "" else cfg.piPackageVersion)}
    export MYPI_NPM_INSTALL_FLAGS=${lib.escapeShellArg (builtins.toJSON cfg.npmInstallFlags)}
  '';

  bootstrapCmd = if cfg.bootstrap.mode == "manual_only" then "" else ''
    project_root="''${DEVENV_ROOT:-$PWD}"
    if [ ! -f "$project_root/.pi/settings.json" ] || [ ${cfgBootstrapModeEscaped} = "every_entry" ]; then
      mypi sync >/dev/null 2>&1 || true
    fi
  '';
in
{
  options.piAgent = {
    enable = lib.mkEnableOption "MYPI agent tooling";

    root = lib.mkOption {
      type = lib.types.str;
      default = ".agents/pi";
      description = "Project-relative root for MYPI agent artifacts.";
    };

    nodePackage = lib.mkOption {
      type = lib.types.package;
      default = pkgs.nodejs_22;
      description = "Node.js package for Pi/npm installation and operations.";
    };

    piPackageName = lib.mkOption {
      type = lib.types.str;
      default = "@earendil-works/pi-coding-agent";
      description = "NPM package name for the Pi coding agent.";
    };

    piPackageVersion = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "Pinned Pi package version. Required for reproducible pinned installs.";
    };

    npmInstallFlags = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ "--ignore-scripts" "--no-audit" "--no-fund" ];
      description = "Additional flags passed to npm install for Pi package installation.";
    };

    bootstrap.mode = lib.mkOption {
      type = lib.types.enum [ "first_entry_only" "manual_only" "every_entry" ];
      default = "first_entry_only";
      description = "Bootstrap sync policy on shell entry.";
    };
  };

  config = lib.mkIf cfg.enable {
    packages = [ mypiPkg mypiBin piAgentBin cfg.nodePackage ];

    enterShell = lib.mkAfter ''
      ${npmEnvCmd}
      ${bootstrapCmd}
    '';
  };
}
