# PI_TELEGRAM_CONCEPT.md

## Purpose

This document describes how `@llblab/pi-telegram` can integrate into the MyPi-Agent architecture as a repo-scoped Telegram interface for Pi Agent. The approach uses Pi's native extension system rather than a standalone daemon, keeping the integration minimal while providing mobile access to running Pi sessions.

The target outcome is:

```text
one repo = one devenv environment
one repo = one Pi session with pi-telegram connected
one repo = one Telegram bot token
one repo = one DM conversation
```

This gives clear isolation between projects with minimal additional infrastructure.

---

## Summary

Each repo runs Pi with the `@llblab/pi-telegram` extension installed. When a Pi session starts and `/telegram-connect` is invoked, the Telegram bot begins polling. The user can then interact with that repo's Pi Agent from their phone via Telegram DM.

There is no separate process to manage. Pi *is* the process, and pi-telegram lives inside it.

---

## Why This Model Fits MyPi-Agent

MyPi-Agent provides a reusable devenv module for Pi-powered repos. The pi-telegram extension requires:

1. The extension installed (`pi install npm:@llblab/pi-telegram`)
2. A `TELEGRAM_BOT_TOKEN` in the environment
3. A running Pi session with `/telegram-connect` active

All three can be provided by the MyPi devenv module and secretspec integration. No additional daemon, service manager, or process supervisor is needed for the basic "laptop stays on" use case.

---

## Architecture

```text
MyPi-Agent devenv module:
  Provides pi binary, mypi CLI, pi-telegram extension, bot token via secretspec

Per-repo Pi session:
  Runs interactively in a terminal (or tmux/screen)
  pi-telegram polls Telegram from within the session
  Session is workspace-scoped to the repo root

Telegram DM:
  User sends messages to @MyProjectBot
  Pi processes them against the repo workspace
  Responses stream back as Telegram messages
```

### Session Lifecycle

```text
Terminal: pi (starts session in ~/dev/project-a)
Terminal: /telegram-connect (starts polling)
Phone:   send prompt -> Pi executes -> response streams back
Phone:   /new -> fresh session, same workspace, auto-acquires polling
Phone:   send more prompts -> new session handles them
Terminal: Pi still running, full history preserved
```

### Ownership Model

- Only one Pi instance per bot token polls Telegram at a time
- Polling ownership recorded in `~/.pi/agent/locks.json`
- `/new` and same-cwd restarts auto-resume without confirmation
- Cross-session ownership transfer requires explicit confirmation
- Queued work in the old session completes before it goes quiet

---

## Telegram Bot Strategy

Same as TelePi concept: **one Telegram bot per repo**.

```text
@MyPiProjectABot -> controls project-a
@MyPiProjectBBot -> controls project-b
```

Benefits:

```text
wrong bot = wrong repo, visibly obvious
no workspace switching required
no accidental cross-repo prompts
no shared busy state between projects
```

The user creates one bot per repo via @BotFather. The token is stored in secretspec.

---

## Secrets Strategy

Required per-repo secrets:

```text
TELEGRAM_BOT_TOKEN          # from BotFather, per repo
```

Optional/shared:

```text
OPENAI_API_KEY              # or other provider keys
ANTHROPIC_API_KEY           # if used
```

The bot token flows through secretspec -> devenv environment -> Pi session -> pi-telegram extension.

pi-telegram also accepts `TELEGRAM_BOT_KEY`, `TELEGRAM_TOKEN`, or `TELEGRAM_KEY` as aliases.

Note: pi-telegram uses a **first-pair model** for access control. The first user to send `/start` to the bot becomes the exclusive owner. No explicit allowlist is needed (or available).

---

## What MyPi-Agent Should Provide

### Automatic Setup on Import

When a repo imports mypi-agent via `devenv.yaml`, the following should happen **automatically** without user intervention:

```text
pi-telegram extension installed (part of devenv module Pi setup)
TELEGRAM_BOT_TOKEN sourced from secretspec (if configured)
Telegram readiness included in mypi doctor checks
Startup screen shows outstanding manual steps
```

The user should never need to run a separate `mypi telegram init`. The devenv module handles setup. The only manual steps are inherently external (creating a bot, adding the token, pairing).

### Startup Screen Integration

On `devenv shell` entry, the MyPi startup screen should display outstanding Telegram setup actions as clear, actionable notes:

```text
MyPi Agent v0.x.x
==================

  Telegram:
    ! No bot token configured
      -> Create a bot via @BotFather, then add TELEGRAM_BOT_TOKEN to secretspec

    ! Bot not yet paired
      -> Start Pi, run /telegram-connect, then send /start to your bot

    OK: pi-telegram installed
    OK: TELEGRAM_BOT_TOKEN available
    OK: Bot paired (ready to use)
```

The startup screen should only show Telegram notes when:
- The pi-telegram extension is part of the devenv module (always, once this feature ships)
- There are incomplete setup steps to surface

Once everything is configured and paired, the Telegram section should show a single green status line or disappear entirely.

### Detection Logic for Startup Notes

```text
1. Is TELEGRAM_BOT_TOKEN in the environment?
   No  -> show "No bot token configured" with secretspec instructions
   Yes -> check next

2. Is pi-telegram extension installed?
   No  -> should not happen (auto-installed), but show error if so
   Yes -> check next

3. Has the bot been paired? (optional, may not be detectable)
   Unknown/No -> show "run /telegram-connect and send /start" reminder
   Yes        -> show "ready to use"
```

Note: detecting whether the bot has been paired may not be possible without querying Telegram. In that case, the startup screen can show the `/telegram-connect` + `/start` instructions until the user has run through the flow at least once, then suppress via a local state file (e.g., `.mypi/telegram.paired`).

### Secret Binding

The MyPi secretspec integration provides `TELEGRAM_BOT_TOKEN` per repo:

```text
secretspec source (central) -> repo-local binding -> TELEGRAM_BOT_TOKEN in devenv shell
```

### CLI Commands

Minimal command set (mostly for diagnostics, since setup is automatic):

```bash
mypi telegram doctor     # validate extension, token, pairing status
```

`mypi telegram doctor` should validate:

```text
OK: pi binary found
OK: pi-telegram extension installed
OK: TELEGRAM_BOT_TOKEN available
INFO: run /telegram-connect in your Pi session to start polling
INFO: send /start to your bot to pair your Telegram account
```

---

## What MyPi-Agent Does NOT Need to Provide

```text
Process management (Pi is already running interactively)
Daemon/service wrappers (not needed for laptop use case)
Session file manipulation (pi-telegram handles this internally)
.mypi/telepi/ directory structure (no separate config needed)
Custom .env files for telegram (token comes from devenv/secretspec)
Manual init commands (setup is automatic on devenv import)
```

---

## User Experience

### First-time setup (per repo)

```bash
cd ~/dev/project-a
devenv shell
# startup screen shows:
#   Telegram:
#     ! No bot token configured
#     -> Create a bot via @BotFather, then add TELEGRAM_BOT_TOKEN to secretspec

# User creates bot, adds token to secretspec, re-enters shell:
devenv shell
# startup screen shows:
#   Telegram:
#     OK: TELEGRAM_BOT_TOKEN available
#     ! Run /telegram-connect in Pi, then send /start to @MyPiProjectABot

pi
# inside Pi:
/telegram-connect
# open Telegram, send /start to @MyPiProjectABot

# Next devenv shell entry:
#   Telegram: OK (ready to use)
```

### Daily use

```bash
cd ~/dev/project-a
devenv shell
pi
# inside Pi:
/telegram-connect
```

Then from phone:

```text
Open @MyPiProjectABot
Send: /start (first time only, pairs your account)
Send: summarize the recent changes
Send: run tests and fix any failures
Send: /new (starts fresh session if needed)
```

### Multiple repos simultaneously

```text
Terminal 1: cd ~/dev/project-a && devenv shell && pi -> /telegram-connect
Terminal 2: cd ~/dev/project-b && devenv shell && pi -> /telegram-connect
Terminal 3: cd ~/dev/project-c && devenv shell && pi -> /telegram-connect

Phone: message @ProjectABot -> hits project-a Pi
Phone: message @ProjectBBot -> hits project-b Pi
Phone: message @ProjectCBot -> hits project-c Pi
```

---

## pi-telegram Features Available Out of the Box

The extension provides significant functionality without any mypi wrapper:

```text
Queue runtime        - messages sent while Pi is busy queue and process in order
Streaming replies    - markdown renders as Telegram HTML while generating
Media handling       - text, images, files, voice notes, media groups
Operator menu        - inline controls for status, model selection, thinking levels
/new                 - start fresh session from Telegram
/start               - pair account and open control panel
Prompt templates     - Pi templates exposed as Telegram commands
Extension interop    - unknown button callbacks forward to other Pi extensions
```

---

## Limitations and Tradeoffs

### No explicit user allowlist

pi-telegram uses first-pair: whoever sends `/start` first owns the bot. This is fine for personal bots but less controllable than TelePi's `TELEGRAM_ALLOWED_USER_IDS`.

Mitigation: each bot token is unique per repo and created by the user, so only they know it exists.

### No bidirectional handoff

You can't `/handoff` a session from terminal to Telegram or back in a structured way. You're either typing in the terminal or in Telegram — both hit the same session, but there's no formal transfer protocol.

Mitigation: since both access the same session, you can just start typing in either place.

### Pi must stay running

If Pi exits (crash, idle timeout, Ctrl-C), the Telegram bot goes dead. No supervisor restarts it.

Mitigation: acceptable for "laptop at home" use case. For reliability, upgrade to TelePi daemon model later.

### No auto-connect

Pi doesn't auto-run `/telegram-connect` on startup. The user must invoke it each time they start a Pi session.

Mitigation: could be solved with a Pi startup hook, alias, or future `mypi telegram start` wrapper that execs Pi with auto-connect.

### Laptop must stay awake

If the machine sleeps, all bots go dark.

Mitigation: acceptable for initial scope. Remote deployment (Phase 2+) solves this.

---

## Upgrade Path to TelePi

This pi-telegram integration is intentionally minimal. When reliability requirements grow, the architecture can evolve:

```text
Phase 1 (this doc):
  pi-telegram extension, manual /telegram-connect, laptop-bound
  -> works now, zero new infrastructure

Phase 2:
  Auto-connect wrapper (mypi telegram start -> execs Pi with auto-connect)
  -> slightly more reliable, still laptop-bound

Phase 3:
  TelePi daemon model with devenv process management
  -> survives Pi crashes, auto-restarts, proper service lifecycle

Phase 4:
  Remote container deployment
  -> 24/7 availability, per-repo containers, compose orchestration
```

Each phase builds on the previous without breaking the "one bot per repo" model or the secretspec integration.

---

## Comparison to TELEPI_CONCEPT.md

| Concern | This doc (pi-telegram) | TELEPI_CONCEPT.md (TelePi) |
|---|---|---|
| Process model | No extra process | Standalone daemon |
| Reliability | Fragile (Pi must stay alive) | Robust (own service lifecycle) |
| Setup complexity | Minimal (install extension + token) | Heavier (config files, process defs) |
| Features needed from mypi | init + doctor only | init + run + doctor + process config |
| Infrastructure | None | devenv process, .mypi/telepi/, .env files |
| Handoff | No formal handoff | Bidirectional CLI/Telegram handoff |
| Access control | First-pair model | Explicit allowlist |
| Upgrade path | Evolves into TelePi later | Full solution from the start |

---

## Recommended Initial Implementation

### MyPi-Agent should provide:

```text
pi-telegram extension (auto-installed via devenv module)
TELEGRAM_BOT_TOKEN in secretspec per repo
Startup screen with outstanding manual steps
mypi telegram doctor (for diagnostics)
```

### A consuming repo needs only:

```text
1. Create bot via @BotFather (one-time, external)
2. Add token to secretspec (one-time)
3. Run /telegram-connect in Pi session (per-session)
4. Send /start to bot (one-time pairing)
```

Everything else is automatic on `devenv.yaml` import.

### Defer until later:

```text
Auto-connect on Pi startup (eliminates step 3)
Process supervision / restart
TelePi daemon integration
Remote deployment
OS-level services
```
