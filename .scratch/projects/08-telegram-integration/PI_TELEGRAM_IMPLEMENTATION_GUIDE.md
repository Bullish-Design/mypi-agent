# PI_TELEGRAM_IMPLEMENTATION_GUIDE.md

## Overview

This guide translates the [`telegram.allium`](../../specs/allium/telegram.allium) specification and [`PI_TELEGRAM_CONCEPT.md`](./PI_TELEGRAM_CONCEPT.md) into concrete implementation steps for integrating `@llblab/pi-telegram` into the MyPi-Agent devenv module.

**Target outcome (one repo = one bot):**

```
one repo = one devenv environment
one repo = one Pi session with pi-telegram connected
one repo = one Telegram bot token
one repo = one DM conversation
```

The integration is **minimal**: no daemon, no process supervisor, no auto-connect. Pi runs interactively, the user invokes `/telegram-connect`, and the Telegram bot polls from within the Pi session.

---

## Spec traceability matrix

Every implementation change is traceable to a rule, entity, or invariant in the allium spec.

| Spec construct | What it demands | Implementation location |
|---|---|---|
| `entity Extension` / `telegram_extension` | Track installation state of pi-telegram | `sync.py` — install + verify; `doctor.py` — check |
| `rule InstallTelegramExtension` | npm install on `SyncCompleted()` when `telegram_enable` | `sync.py` — in `_build_sync_plan()` or new helper |
| `entity TelegramBotToken` | Detect token presence, source = secretspec only | `doctor.py` — env var check; `modules/pi-agent.nix` — env binding |
| `entity TelegramPaired` | Check `.mypi/telegram.paired` marker file | `doctor.py` or new startup check |
| `entity TelegramStartupNotes` | Compute what to show on shell entry | `modules/pi-agent.nix` — `enterShell` hook |
| `rule DetectTelegramToken` | On `ShellEntered()`, check env var non-empty | Nix enterShell + doctor |
| `rule DetectPairedState` | On `ShellEntered()`, check `.mypi/telegram.paired` exists | Nix enterShell |
| `rule TelegramStartupScreenContent` | Three-level readiness (token/ext/paired) | Nix enterShell rendering |
| `rule DoctorChecksTelegram` | Warn if ext missing or token missing when enabled | `doctor.py` — `run_doctor()` |
| `invariant TelegramTokenOnlyViaSecretspec` | Token source enforced to secretspec | Architectural — Nix env binding |
| `invariant TelegramTokenDeclaredInSecretspecConfig` | Token declared in secretspec.toml | `secretspec_setup.py` — optional validation |
| `invariant TelegramPairedFileInProjectRoot` | Paired file location constraint | `doctor.py` — path validation |
| `invariant TelegramExtensionInstalledWhenEnabled` | Ext must be installed after sync when enabled | `sync.py` — post-install assertion |

---

## Implementation steps

### Step 1: Nix module — `telegram.enable` option and environment binding

**File:** `modules/pi-agent.nix`

Add a `telegram.enable` option that gates the entire feature. Defaults to `true` (the feature ships enabled). When enabled, wire `TELEGRAM_BOT_TOKEN` from secretspec into the devenv environment.

#### 1a. Add option declaration

In the `options.piAgent` block, add after the `showUsageOnEntry` option:

```nix
telegram.enable = lib.mkOption {
  type = lib.types.bool;
  default = true;
  description = "Enable pi-telegram extension integration.";
};
```

#### 1b. Bind TELEGRAM_BOT_TOKEN from secretspec

In the `config = lib.mkIf cfg.enable` block, add to the `env` attribute set **after** `MYPI_AGENT_ROOT`:

```nix
env = {
  # ... existing env vars ...
  MYPI_AGENT_ROOT = cfg.root;
  # NEW: Telegraph token from secretspec (bound to profile)
  TELEGRAM_BOT_TOKEN = lib.mkIf cfg.telegram.enable (
    if cfg.secrets.enable && (config.secretspec.secretEnvVars or {}) ? TELEGRAM_BOT_TOKEN then
      config.secretspec.secretEnvVars.TELEGRAM_BOT_TOKEN
    else
      ""
  );
};
```

**Note:** The exact mechanism depends on how `secretspec` exposes resolved secret values to the devenv environment. The intent is: when `telegram.enable` is true and secrets are configured, `TELEGRAM_BOT_TOKEN` (or one of the accepted aliases: `TELEGRAM_BOT_KEY`, `TELEGRAM_TOKEN`, `TELEGRAM_KEY`) is available in the shell environment. The token value flows through `secretspec run` into the Pi process only — it is never written to disk.

If the secretspec integration doesn't support direct env binding yet, the fallback is documented user setup (the user adds `TELEGRAM_BOT_TOKEN` to their secretspec `.env` file and the `scripts.pi` wrapper passes it through). In that case, the Nix module only needs the option flag.

#### 1c. Export telegram_enable for mypi CLI

The existing `environment.allium` spec has `ShellEnvironment.telegram_bot_token_available` and `ModuleOptions.telegram_enable`. Currently `ModuleOptions.telegram_enable` defaults to `true` in the spec but has no Nix option. Add the env var:

```nix
MYPI_TELEGRAM_ENABLE = lib.boolToString cfg.telegram.enable;
```

This lets the Python CLI read `os.environ.get("MYPI_TELEGRAM_ENABLE")` to decide whether to run telegram checks.

---

### Step 2: Extension auto-install during sync

**File:** `src/mypi_agent/sync.py`

**Spec rule:** `InstallTelegramExtension` — fires on `SyncCompleted()`, requires `telegram_enable`, installs `@llblab/pi-telegram` via npm into the agent root.

#### 2a. Add extension install constants

Near the top of `sync.py`, add after the existing constants:

```python
# Telegram extension
TELEGRAM_EXTENSION_PACKAGE = "@llblab/pi-telegram"
TELEGRAM_EXTENSION_DIR = "pi-telegram"  # directory name inside node_modules
```

#### 2b. Add extension install logic in `_build_sync_plan()`

After the Pi installation block (around the `npm install` call for Pi), add a second npm install for the telegram extension when:

1. `MYPI_TELEGRAM_ENABLE` is true
2. The extension is not already installed
3. `diff_requested` is false

```python
# -- Telegram extension install --
telegram_extension_installed = False
telegram_enable = os.environ.get("MYPI_TELEGRAM_ENABLE", "").strip().lower() in {"1", "true", "yes"}
if telegram_enable and not diff_requested:
    ext_path = paths.agent_root / "node_modules" / TELEGRAM_EXTENSION_PACKAGE
    if not ext_path.exists():
        if npm is not None:
            ext_install = subprocess.run(
                [npm, "install", "--prefix", str(paths.agent_root),
                 *npm_install_flags, TELEGRAM_EXTENSION_PACKAGE],
                text=True, capture_output=True, check=False,
            )
            if ext_install.returncode == 0:
                telegram_extension_installed = True
            else:
                warnings.append("telegram_extension_install_failed")
        else:
            warnings.append("telegram_extension_install_skipped_no_npm")
    else:
        telegram_extension_installed = True
```

#### 2c. Wire telegram_extension_installed into the result

Add a field to `SyncPlan` dataclass:

```python
@dataclass
class SyncPlan:
    # ... existing fields ...
    telegram_extension_installed: bool
```

And in the `SyncResult` model:

```python
class SyncResult(MypiBaseModel):
    # ... existing fields ...
    telegram_extension_installed: bool
```

Update `_build_sync_plan()` return to include `telegram_extension_installed`, and `run_sync()` to pass it through.

#### 2d. Verify extension installation

The spec's `InstallTelegramExtension` rule requires `installation_verified = true`. After the npm install, verify that the extension package directory exists and that `node_modules/@llblab/pi-telegram/package.json` is readable.

---

### Step 3: Token detection

**Files:** `src/mypi_agent/doctor.py`, `modules/pi-agent.nix`

**Spec rule:** `DetectTelegramToken` — on `ShellEntered()`, checks env for any accepted token variable name (TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_KEY, TELEGRAM_TOKEN, TELEGRAM_KEY).

#### 3a. Add token detection helper

In `doctor.py`, add:

```python
TELEGRAM_TOKEN_ENV_VARS = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_BOT_KEY",
    "TELEGRAM_TOKEN",
    "TELEGRAM_KEY",
)


def _telegram_token_available() -> bool:
    """Check if any accepted Telegram bot token env var is non-empty."""
    return any(
        os.environ.get(var, "").strip()
        for var in TELEGRAM_TOKEN_ENV_VARS
    )


def _telegram_enabled() -> bool:
    """Check if telegram integration is enabled via Nix module option."""
    return os.environ.get("MYPI_TELEGRAM_ENABLE", "").strip().lower() in {"1", "true", "yes"}
```

#### 3b. Add doctor checks (spec: DoctorChecksTelegram)

In `run_doctor()`, add after the SecretSpec infrastructure checks block:

```python
# -- Telegram readiness (spec: DoctorChecksTelegram) --
if _telegram_enabled():
    # Check extension installed
    ext_path = paths.agent_root / "node_modules" / "@llblab" / "pi-telegram"
    if not ext_path.exists():
        warnings.append("telegram_extension_not_installed")
        diagnostics.append({"code": "telegram_extension_not_installed", "severity": "warning"})
    # Check token available
    if not _telegram_token_available():
        warnings.append("telegram_bot_token_not_configured")
        diagnostics.append({"code": "telegram_bot_token_not_configured", "severity": "warning"})
```

Both are **warnings only** — Telegram is value-add, not core. The system functions without it.

#### 3c. secretspec.toml validation (spec: invariant TelegramTokenDeclaredInSecretspecConfig)

Optionally, in `secretspec_setup.py` or `doctor.py`, check that `secretspec.toml` declares `TELEGRAM_BOT_TOKEN` as a secret key when `telegram_enable` is true. This is a lighter-weight "info" check:

```python
# In doctor.py, after the spec_toml_path check:
if _telegram_enabled() and spec_toml_path.exists():
    try:
        # Parse secretspec.toml to verify TELEGRAM_BOT_TOKEN is declared
        # (implementation depends on secretspec.toml format)
        spec_text = spec_toml_path.read_text(encoding="utf-8")
        if "TELEGRAM_BOT_TOKEN" not in spec_text and "TELEGRAM_BOT_KEY" not in spec_text:
            warnings.append("telegram_token_not_declared_in_secretspec")
            diagnostics.append({"code": "telegram_token_not_declared_in_secretspec", "severity": "warning"})
    except OSError:
        pass
```

---

### Step 4: Paired state detection

**Files:** `src/mypi_agent/doctor.py` (or new helper), `modules/pi-agent.nix`

**Spec rule:** `DetectPairedState` — checks for `.mypi/telegram.paired` in the project root. Existence = paired.

#### 4a. Add paired state helper

In `doctor.py`:

```python
def _telegram_paired(paths) -> bool:
    """Check if the user has completed the Telegram pairing flow."""
    paired_file = paths.project_root / ".mypi" / "telegram.paired"
    return paired_file.exists()
```

#### 4b. Add paired state to doctor output

In `run_doctor()`, when telegram is enabled and token is available but not paired:

```python
if _telegram_enabled() and _telegram_token_available():
    if not _telegram_paired(paths):
        warnings.append("telegram_not_paired")
        diagnostics.append({"code": "telegram_not_paired", "severity": "info"})
```

Note: "not paired" is `info` level (not `warning`), because it's an expected transitional state.

---

### Step 5: Startup screen integration

**File:** `modules/pi-agent.nix`

**Spec rule:** `TelegramStartupScreenContent` — computes three-level readiness on `ShellEntered()` and displays actionable notes.

#### 5a. Add startup screen logic

In the Nix module, add a new helper section in the `config` block that computes the telegram status and appends it to the shell entry screen. This should go in the `enterShell` hook, inside the existing `usageCheckCmd` or as a separate block:

```nix
telegramStartupNotes =
  if cfg.telegram.enable then
    ''
      # -- Telegram readiness --
      TELEGRAM_SECTION_SHOWN=""
      PAIRED_FILE="$DEVENV_ROOT/.mypi/telegram.paired"

      if [ -z "''${TELEGRAM_BOT_TOKEN:-}" ] && \
         [ -z "''${TELEGRAM_BOT_KEY:-}" ] && \
         [ -z "''${TELEGRAM_TOKEN:-}" ] && \
         [ -z "''${TELEGRAM_KEY:-}" ]; then
        echo ""
        echo "  Telegram:"
        echo "    ! No bot token configured"
        echo "      -> Create a bot via @BotFather, then add TELEGRAM_BOT_TOKEN to secretspec"
        TELEGRAM_SECTION_SHOWN=1
      fi

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

      if [ -n "''${TELEGRAM_BOT_TOKEN:-}''${TELEGRAM_BOT_KEY:-}''${TELEGRAM_TOKEN:-}''${TELEGRAM_KEY:-}" ] && \
         [ ! -f "$PAIRED_FILE" ]; then
        if [ -z "$TELEGRAM_SECTION_SHOWN" ]; then
          echo ""
          echo "  Telegram:"
        fi
        echo "    ! Bot not yet paired"
        echo "      -> Start Pi, run /telegram-connect, then send /start to your bot"
        echo "      -> After pairing, run: touch .mypi/telegram.paired"
        TELEGRAM_SECTION_SHOWN=1
      fi

      if [ -z "$TELEGRAM_SECTION_SHOWN" ] && [ -n "''${TELEGRAM_BOT_TOKEN:-}''${TELEGRAM_BOT_KEY:-}''${TELEGRAM_TOKEN:-}''${TELEGRAM_KEY:-}" ] && [ -f "$PAIRED_FILE" ]; then
        echo ""
        echo "  Telegram: OK (ready to use)"
      fi
    ''
  else
    "";
```

#### 5b. Wire into enterShell

In the existing `enterShell` block:

```nix
enterShell = lib.mkAfter ''
  ${secretsEnv}
  ${bootstrapCmd}
  ${secretspecSetupCmd}
  ${usageCheckCmd}
  ${telegramStartupNotes}
'';
```

**Display logic summary (from spec):**

| State | Shows |
|---|---|
| `!telegram_enable` | Nothing (section suppressed) |
| No token + no ext | "No bot token configured" + "extension not installed" |
| Token yes, ext yes, not paired | "Bot not yet paired" + instructions + `touch .mypi/telegram.paired` |
| Token yes, ext yes, paired | "Telegram: OK (ready to use)" or suppress entirely |

---

### Step 6: Doctor command surface wiring

**File:** `src/mypi_agent/cli.py`

No changes needed at this stage. The `mypi doctor` command already invokes `run_doctor()` which will include the new telegram checks. The spec's `DoctorChecksTelegram` rule fires on `DoctorRequested()` which maps to `mypi doctor`.

**Not implementing now:** A separate `mypi telegram doctor` subcommand. The concept doc mentions it as a minimal command, but the elicitation confirmed that existing `mypi doctor` integration covers the need. This can be added later if needed without spec changes.

---

## File-by-file change summary

| File | Changes |
|---|---|
| `modules/pi-agent.nix` | Add `telegram.enable` option, `MYPI_TELEGRAM_ENABLE` env var, token env binding, startup screen shell script, wire into `enterShell` |
| `src/mypi_agent/sync.py` | Add `TELEGRAM_EXTENSION_PACKAGE` constant, npm install logic in `_build_sync_plan()`, `telegram_extension_installed` field in `SyncPlan` and `SyncResult` |
| `src/mypi_agent/doctor.py` | Add `_telegram_enabled()`, `_telegram_token_available()`, `_telegram_paired()` helpers, add token/ext/paired checks in `run_doctor()`, optional secretspec.toml validation |
| `src/mypi_agent/models.py` | No changes (telegram checks use existing `Paths` properties) |
| `src/mypi_agent/cli.py` | No changes (telegram flows through existing `mypi doctor`) |
| `secretspec.toml` | Template: add `TELEGRAM_BOT_TOKEN` secret key declaration (documentation-only) |

**No changes needed to:**
- `devenv.nix` — the public import surface stays unchanged
- `dev/` — development environment unchanged
- Test fixtures — add telegram-specific tests as a follow-up

---

## Acceptance criteria

### Spec invariant verification

Each invariant must be manually verified after implementation:

| Invariant | How to verify |
|---|---|
| `TelegramExtensionInstalledWhenEnabled` | After `mypi sync` with telegram enabled, `node_modules/@llblab/pi-telegram/package.json` exists |
| `TelegramTokenOnlyViaSecretspec` | `TELEGRAM_BOT_TOKEN` is available in shell only when secretspec is configured; no manual env export accepted |
| `TelegramTokenNeverPersisted` | Search generated files (`.pi/settings.json`, `.agents/pi/manifest.json`, `.state/*.json`) — no token value present |
| `TelegramOnlyShownWhenEnabled` | Set `telegram.enable = false` — startup screen has no Telegram section |
| `TelegramPairedFileInProjectRoot` | Paired check only looks at `<project_root>/.mypi/telegram.paired` |
| `TelegramTokenDeclaredInSecretspecConfig` | `secretspec.toml` contains `TELEGRAM_BOT_TOKEN` when enabled (warning if missing) |
| `ExtensionInstallationVerified` | After install, `installation_verified` reflects actual package existence check |

### Integration test scenarios

1. **Clean repo, telegram enabled, no token:**
   - `devenv shell` → shows "No bot token configured" with secretspec instructions
   - `mypi doctor` → warning: `telegram_bot_token_not_configured`
   - `mypi sync` → installs pi-telegram extension

2. **Clean repo, telegram enabled, token in secretspec:**
   - `devenv shell` → shows "Bot not yet paired" with `/telegram-connect` instructions
   - `mypi doctor` → no telegram warnings

3. **After user creates `.mypi/telegram.paired`:**
   - `devenv shell` → shows "Telegram: OK (ready to use)" or no section

4. **Telegram disabled:**
   - `devenv shell` → no Telegram section
   - `mypi doctor` → no telegram checks
   - `mypi sync` → does not install pi-telegram

5. **Extension install failure:**
   - `mypi sync` → warning: `telegram_extension_install_failed`
   - `mypi doctor` → warning: `telegram_extension_not_installed`
   - Startup screen → shows "pi-telegram extension not installed → Run: mypi sync"

---

## What MyPi-Agent does NOT implement (manual user steps)

These are the inherently manual steps the user must perform. The implementation guide documents them but does not automate them:

| Step | Who | Description |
|---|---|---|
| Create Telegram bot | User (one-time) | Create a bot via @BotFather on Telegram, get the bot token |
| Add token to secretspec | User (one-time) | Add `TELEGRAM_BOT_TOKEN=<token>` to the repo's secretspec `.env` file |
| Mark as paired | User (one-time) | After completing `/start` in Telegram, run `touch .mypi/telegram.paired` |
| Run `/telegram-connect` | User (per-session) | Inside the Pi TUI, invoke `/telegram-connect` to start polling |

**Deferred (not in Phase 1 scope):**
- Auto-connect on Pi startup (eliminates per-session `/telegram-connect`)
- Process supervision / restart
- TelePi daemon integration
- Remote deployment (24/7 availability)

---

## Upgrade path (not implemented)

As documented in the concept doc, this implementation is Phase 1. Later phases build on it:

```
Phase 1 (this guide):
  pi-telegram extension, manual /telegram-connect, laptop-bound

Phase 2:
  Auto-connect wrapper (mypi telegram start -> execs Pi with auto-connect)

Phase 3:
  TelePi daemon model with devenv process management

Phase 4:
  Remote container deployment
```
