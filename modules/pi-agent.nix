{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.piAgent;
  cfgBootstrapModeEscaped = lib.escapeShellArg cfg.bootstrap.mode;
  mypiPkg = pkgs.callPackage ../packages/mypi-agent-cli.nix { };

  bootstrapCmd =
    if cfg.bootstrap.mode == "manual_only" then
      ""
    else
      ''
        if [ ${cfgBootstrapModeEscaped} = "every_entry" ] || mypi needs-sync --trigger shell; then
          if ! mypi sync --trigger shell; then
            echo "warning: mypi bootstrap failed; run: mypi doctor" >&2
          fi
        fi
      '';

  secretspecSetupCmd =
    if cfg.secrets.enable then
      ''
        if ! mypi secretspec-setup; then
          echo "warning: mypi secretspec-setup had errors" >&2
        fi
      ''
    else
      "";

  usageCheckCmd =
    if cfg.showUsageOnEntry then
      ''
        # Check configuration and print usage instructions
        if mypi doctor >/dev/null 2>&1; then
          echo ""
          echo "  ✓ MYPI agent is configured and ready."
        else
          echo ""
          echo "  ⚠️  MYPI agent is not fully configured."
          echo "     Run \`mypi doctor\` for details, or \`mypi sync\` to set up."
        fi
        echo ""
        echo "  Quick reference:"
        echo "    mypi sync     — Bootstrap/sync the Pi agent"
        echo "    mypi doctor   — Check configuration status"
        echo "    mypi pi       — Run Pi (with SecretSpec secrets)"
        echo "    mypi agent    — Run Pi directly"
        echo ""
      ''
    else
      "";
in
{
  options.piAgent = {
    enable = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Whether to enable MYPI agent tooling.";
    };

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
      default = "0.78.0";
      description = "Pinned Pi package version for reproducible installs.";
    };

    npmInstallFlags = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [
        "--ignore-scripts"
        "--no-audit"
        "--no-fund"
      ];
      description = "Additional flags passed to npm install for Pi package installation.";
    };

    allowFloatingPiVersion = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Allow floating (unpinned) Pi package version. Set to true to use latest from npm.";
    };

    bootstrap.mode = lib.mkOption {
      type = lib.types.enum [
        "first_entry_only"
        "manual_only"
        "every_entry"
      ];
      default = "first_entry_only";
      description = "Bootstrap sync policy on shell entry.";
    };

    secrets.enable = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Run the pi command through SecretSpec for runtime secret injection.";
    };

    showUsageOnEntry = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Print configuration status and quick-reference usage guide on shell entry.";
    };
  };

  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = !(lib.hasPrefix "/" cfg.root);
        message = "piAgent.root must be project-relative, not absolute.";
      }
      {
        assertion = builtins.match ".*\\.\\..*" cfg.root == null;
        message = "piAgent.root must not contain '..' path traversal.";
      }
    ];

    env = {
      MYPI_PROJECT_ROOT = config.devenv.root;
      NPM_CONFIG_PREFIX = "${config.devenv.root}/${cfg.root}/npm-global";
      NPM_CONFIG_CACHE = "${config.devenv.root}/${cfg.root}/.npm-cache";
      NPM_CONFIG_AUDIT = "false";
      NPM_CONFIG_FUND = "false";
      MYPI_PI_PACKAGE_NAME = cfg.piPackageName;
      MYPI_PI_PACKAGE_VERSION = if cfg.piPackageVersion == null then "" else cfg.piPackageVersion;
      MYPI_ALLOW_FLOATING_PI_VERSION = lib.boolToString cfg.allowFloatingPiVersion;
      MYPI_AGENT_ROOT = cfg.root;
    };

    packages = [ cfg.nodePackage ];

    scripts.mypi = {
      description = "MYPI agent CLI wrapper";
      exec = ''
        set -euo pipefail
        export MYPI_NPM_INSTALL_FLAGS=${lib.escapeShellArg (builtins.toJSON cfg.npmInstallFlags)}
        if [ -n "''${DEVENV_ROOT:-}" ]; then
          cd "$DEVENV_ROOT"
        fi
        exec ${mypiPkg}/bin/mypi "$@"
      '';
    };

    scripts.pi = {
      description = "Run Pi with SecretSpec runtime secrets";
      exec =
        let
          providerArg = lib.optionalString ((config.secretspec.provider or null) != null)
            "--provider ${lib.escapeShellArg config.secretspec.provider} ";
          profileArg = lib.optionalString ((config.secretspec.profile or null) != null)
            "--profile ${lib.escapeShellArg config.secretspec.profile} ";
        in
        ''
          set -euo pipefail

          if [ -n "''${DEVENV_ROOT:-}" ]; then
            cd "$DEVENV_ROOT"
          fi

          project_root="''${DEVENV_ROOT:-$PWD}"
          agent_root="''${MYPI_AGENT_ROOT:-.agents/pi}"
          real_pi="$project_root/$agent_root/node_modules/.bin/pi"

          if [ ! -x "$real_pi" ]; then
            echo "error: Pi is not installed. Run: mypi sync" >&2
            exit 127
          fi

          ${if cfg.secrets.enable then ''
            exec secretspec run ${providerArg}${profileArg}-- "$real_pi" "$@"
          '' else ''
            exec "$real_pi" "$@"
          ''}
        '';
    };

    scripts.secretspec-setup = {
      description = "Verify and initialise SecretSpec for this project";
      exec = ''
        set -euo pipefail
        export MYPI_NPM_INSTALL_FLAGS=${lib.escapeShellArg (builtins.toJSON cfg.npmInstallFlags)}
        if [ -n "''${DEVENV_ROOT:-}" ]; then
          cd "$DEVENV_ROOT"
        fi
        exec ${mypiPkg}/bin/mypi secretspec-setup "$@"
      '';
    };

    enterShell = lib.mkAfter ''
      ${bootstrapCmd}
      ${secretspecSetupCmd}
      ${usageCheckCmd}
    '';

    profiles.pi.module = {
      enterShell = lib.mkAfter ''
        pi
      '';
    };
  };
}
