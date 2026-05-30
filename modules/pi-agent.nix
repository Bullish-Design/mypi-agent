{ config, lib, pkgs, ... }:
let
  cfg = config.piAgent;
  cfgRootEscaped = lib.escapeShellArg cfg.root;
  cfgBootstrapModeEscaped = lib.escapeShellArg cfg.bootstrap.mode;
  mypiPkg = pkgs.callPackage ../packages/mypi-agent-cli.nix { };
  mypiBin = pkgs.writeShellScriptBin "mypi" ''
    set -euo pipefail
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
    export MYPI_ALLOW_FLOATING_PI_VERSION=${lib.boolToString cfg.allowFloatingPiVersion}
    if [ -n "''${DEVENV_ROOT:-}" ]; then
      cd "$DEVENV_ROOT"
    fi
    export MYPI_AGENT_ROOT="$root_rel"
    exec ${mypiPkg}/bin/mypi "$@"
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
    export MYPI_ALLOW_FLOATING_PI_VERSION=${lib.boolToString cfg.allowFloatingPiVersion}
  '';

  bootstrapCmd = if cfg.bootstrap.mode == "manual_only" then "" else ''
    if [ ${cfgBootstrapModeEscaped} = "every_entry" ] || mypi needs-sync --trigger shell; then
      if ! mypi sync --trigger shell; then
        echo "warning: mypi bootstrap failed; run: mypi doctor" >&2
      fi
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
      default = "1.2.3";
      description = "Pinned Pi package version for reproducible installs.";
    };

    npmInstallFlags = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ "--ignore-scripts" "--no-audit" "--no-fund" ];
      description = "Additional flags passed to npm install for Pi package installation.";
    };

    allowFloatingPiVersion = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Allow floating (unpinned) Pi package version. Set to true to use latest from npm.";
    };

    bootstrap.mode = lib.mkOption {
      type = lib.types.enum [ "first_entry_only" "manual_only" "every_entry" ];
      default = "first_entry_only";
      description = "Bootstrap sync policy on shell entry.";
    };
  };

  config = lib.mkIf cfg.enable {
    packages = [ mypiBin cfg.nodePackage ];

    enterShell = lib.mkAfter ''
      ${npmEnvCmd}
      export MYPI_AGENT_ROOT=${cfgRootEscaped}
      export PATH="''${DEVENV_ROOT:-$PWD}/$MYPI_AGENT_ROOT/node_modules/.bin:$PATH"
      ${bootstrapCmd}
    '';
  };
}
