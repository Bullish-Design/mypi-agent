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
        echo "    mypi sync       — Bootstrap/sync the Pi agent"
        echo "    mypi doctor     — Check configuration status"
        echo "    mypi secrets    — Manage per-repo API key secrets"
        echo "    mypi secrets check — Verify secrets are configured"
        echo "    mypi pi         — Run Pi (with SecretSpec secrets)"
        echo "    mypi agent      — Run Pi directly"
        echo ""
      ''
    else
      "";

  # -- Telegram extension auto-install on shell entry --
  # If the extension directory is missing, run mypi sync to install it
  # AND register it in Pi's settings.json (raw npm install is insufficient).
  telegramAutoInstall =
    if cfg.telegram.enable then
      ''
        _TELEGRAM_EXT_PATH="$DEVENV_ROOT/''${MYPI_AGENT_ROOT:-.agents/pi}/node_modules/@llblab/pi-telegram"
        if [ ! -d "$_TELEGRAM_EXT_PATH" ]; then
          echo "  Installing pi-telegram extension..."
          if mypi sync --trigger shell >/dev/null 2>&1; then
            echo "  ✓ pi-telegram extension installed"
          else
            echo "  ⚠ pi-telegram extension install failed" >&2
          fi
        fi
      ''
    else
      "";

  # -- Telegram startup notes (spec: TelegramStartupScreenContent) --
  telegramStartupNotes =
    if cfg.telegram.enable then
      ''
        # -- Telegram readiness --
        TELEGRAM_SECTION_SHOWN=""
        PAIRED_FILE="$DEVENV_ROOT/.mypi/telegram.paired"

        # Token check (any accepted env var non-empty)
        if [ -z "''${TELEGRAM_BOT_TOKEN:-}" ] && [ -z "''${TELEGRAM_BOT_KEY:-}" ] && \
           [ -z "''${TELEGRAM_TOKEN:-}" ] && [ -z "''${TELEGRAM_KEY:-}" ]; then
          echo ""
          echo "  Telegram:"
          echo "    ! No bot token configured"
          echo "      -> Create a bot via @BotFather, then add TELEGRAM_BOT_TOKEN to secretspec"
          TELEGRAM_SECTION_SHOWN=1
        fi

        # Extension check
        EXT_PATH="$DEVENV_ROOT/''${MYPI_AGENT_ROOT:-.agents/pi}/node_modules/@llblab/pi-telegram"
        if [ ! -d "$EXT_PATH" ]; then
          if [ -z "$TELEGRAM_SECTION_SHOWN" ]; then
            echo ""
            echo "  Telegram:"
          fi
          echo "    ! pi-telegram extension not installed"
          echo "      -> Run: mypi sync"
          TELEGRAM_SECTION_SHOWN=1
        fi

        # Paired check
        if [ ! -f "$PAIRED_FILE" ]; then
          # Auto-detect pairing from pi-telegram config
          _TELEGRAM_CONFIG="$DEVENV_ROOT/''${MYPI_AGENT_ROOT:-.agents/pi}/.pi-state/telegram.json"
          if [ -f "$_TELEGRAM_CONFIG" ]; then
            _ALLOWED_USER="$(grep -o '"allowedUserId":[[:space:]]*[0-9]\+' "$_TELEGRAM_CONFIG" 2>/dev/null | grep -o '[0-9]\+$' || true)"
            if [ -n "$_ALLOWED_USER" ]; then
              mkdir -p "$(dirname "$PAIRED_FILE")"
              touch "$PAIRED_FILE"
            fi
          fi
        fi

        if [ ! -f "$PAIRED_FILE" ]; then
          if [ -z "$TELEGRAM_SECTION_SHOWN" ]; then
            echo ""
            echo "  Telegram:"
          fi
          echo "    ! Bot not yet paired"
          echo "      -> Start Pi, run /telegram-connect, then send /start to your bot"
          echo "      -> (pairing is now detected automatically)"
          TELEGRAM_SECTION_SHOWN=1
        fi

        if [ -z "$TELEGRAM_SECTION_SHOWN" ]; then
          echo ""
          echo "  Telegram: OK (ready to use)"
        fi
      ''
    else
      "";

  # -- Secrets env vars --
  secretsEnv =
    let
      profileEnv = lib.optionalString (cfg.secrets.profile != null) ''
        export MYPI_SECRETS_PROFILE=${lib.escapeShellArg cfg.secrets.profile}
      '';
      rootEnv = lib.optionalString (cfg.secrets.defaultRoot != null) ''
        export MYPI_SECRETS_ROOT=${lib.escapeShellArg cfg.secrets.defaultRoot}
      '';
      slugEnv = lib.optionalString (cfg.secrets.projectSlug != null) ''
        export MYPI_SECRETS_SLUG=${lib.escapeShellArg cfg.secrets.projectSlug}
      '';
    in
    profileEnv + rootEnv + slugEnv;

  # Extra profile arg for the pi wrapper when secrets.profile is explicitly set
  secretsProfileArg =
    if cfg.secrets.enable && cfg.secrets.profile != null then
      "--profile ${lib.escapeShellArg cfg.secrets.profile} "
    else
      "";

  # -- Pi state directory seeding --
  # Seed PI_CODING_AGENT_DIR with settings.json and resource directories on shell entry.
  piStateSeed =
    let
      stateDir = "${config.devenv.root}/${cfg.root}/.pi-state";
      settingsSeed =
        if cfg.settings != {} then
          ''
            _PI_SETTINGS_DESIRED=${lib.escapeShellArg (builtins.toJSON cfg.settings)}
            _PI_SETTINGS_FILE="${stateDir}/settings.json"
            if [ ! -f "$_PI_SETTINGS_FILE" ] || [ "$(cat "$_PI_SETTINGS_FILE")" != "$_PI_SETTINGS_DESIRED" ]; then
              printf '%s' "$_PI_SETTINGS_DESIRED" > "$_PI_SETTINGS_FILE"
            fi
          ''
        else
          "";
      resourceDirs = [ "extensions" "skills" "prompts" "scripts" ];
      syncResource = dir:
        let
          src = cfg.stateSeedDir + "/${dir}";
        in
        lib.optionalString (cfg.stateSeedDir != null && builtins.pathExists src) ''
          if [ -d ${lib.escapeShellArg (toString src)} ]; then
            mkdir -p "${stateDir}/${dir}"
            ${pkgs.rsync}/bin/rsync -a --delete ${lib.escapeShellArg (toString src)}/ "${stateDir}/${dir}/"
          fi
        '';
    in
    ''
      mkdir -p "${stateDir}"
      ${settingsSeed}
      ${lib.concatMapStrings syncResource resourceDirs}
    '';
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

    secrets.profile = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = ''
        SecretSpec profile name to use (e.g. "default", "ci", "offline").
        When null, the profile is read from devenv.local.yaml or defaults to "default".
      '';
    };

    secrets.projectSlug = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = ''
        Explicit repo slug for secret storage directory naming.
        When null, the slug is auto-derived from the project directory name.
        Set this if the directory name is ambiguous or changes between machines.
      '';
    };

    secrets.defaultRoot = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = ''
        Override the base directory for per-repo secret storage.
        Defaults to XDG_CONFIG_HOME/mypi-agent/secrets or ~/.config/mypi-agent/secrets.
        Useful for containers (e.g. /run/secrets/mypi-agent) or multi-user setups.
      '';
    };

    showUsageOnEntry = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Print configuration status and quick-reference usage guide on shell entry.";
    };

    telegram.enable = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Enable pi-telegram extension integration.";
    };

    settings = lib.mkOption {
      type = lib.types.attrs;
      default = {};
      description = ''
        Pi settings.json content, written to the project-local PI_CODING_AGENT_DIR on shell entry.
        Example: { defaultProvider = "anthropic"; defaultModel = "claude-opus-4-5"; }
      '';
    };

    stateSeedDir = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = ''
        Path to a directory whose subdirectories (extensions/, skills/, prompts/, scripts/)
        are synced into the project-local PI_CODING_AGENT_DIR on shell entry.
      '';
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
      MYPI_TELEGRAM_ENABLE = lib.boolToString cfg.telegram.enable;
      PI_CODING_AGENT_DIR = "${config.devenv.root}/${cfg.root}/.pi-state";
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
            # Use explicit profile from Nix option if set, otherwise let
            # secretspec/cli resolve it from devenv.local.yaml
            profile_flag=""
            if [ -n "''${MYPI_SECRETS_PROFILE:-}" ]; then
              profile_flag="--profile $MYPI_SECRETS_PROFILE"
            fi

            exec secretspec run ${providerArg}''${profile_flag} -- "$real_pi" "$@"
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
      ${secretsEnv}
      ${piStateSeed}
      ${bootstrapCmd}
      ${secretspecSetupCmd}
      ${usageCheckCmd}
      ${telegramAutoInstall}
      ${telegramStartupNotes}
    '';

    profiles.pi.module = {
      enterShell = lib.mkAfter ''
        pi
      '';
    };
  };
}
