# TELEPI_CONCEPT.md

## Purpose

This document describes how TelePi can fit into the MyPi-Agent architecture as a repo-scoped Telegram interface for Pi Agent. The core idea is to keep MyPi-Agent focused on one repo at a time, while allowing each repo to expose its own independent TelePi bot process through `devenv.sh` process management.

The target outcome is:

```text
one repo = one devenv environment
one repo = one TelePi service
one repo = one Telegram bot token
one repo = one Pi Agent workspace
one repo = one independently managed process
```

This gives clear isolation between projects without prematurely building a larger multi-repo orchestration layer.

---

## Summary of the Recommended Model

The recommended model is **one TelePi service per repo**, managed by that repo's `devenv` process system.

Each repo imports the MyPi-Agent devenv module. That module provides the `pi` binary, the `mypi` CLI, TelePi integration commands, and a `processes.telepi` process definition. On initialization, MyPi generates the repo-local TelePi configuration and validates that required secrets are available.

At runtime:

```text
project-a/
  devenv up
    -> starts project-a TelePi process
    -> uses project-a Telegram bot token
    -> points Pi Agent at project-a workspace

project-b/
  devenv up
    -> starts project-b TelePi process
    -> uses project-b Telegram bot token
    -> points Pi Agent at project-b workspace
```

This gives each project its own Telegram bot endpoint, environment variables, workspace, logs, lifecycle, and failure boundary.

---

## Why This Model Fits MyPi-Agent

MyPi-Agent is intended to be a modular bootstrap foundation for `devenv.nix` / `devenv.sh` managed projects. Its purpose is not to become a centralized control plane at the beginning. Instead, it should provide a reusable repo-scoped Pi Agent baseline that any devenv-managed repo can import.

TelePi fits this model because it can run headlessly as a process inside a repo's environment. The repo's devenv configuration supplies the runtime environment. TelePi then exposes that repo's Pi Agent session over Telegram.

This keeps the responsibilities clean:

```text
MyPi-Agent:
  Provides pi/mypi tooling, TelePi integration, config generation, doctor checks.

The consuming repo:
  Owns its workspace, local config, secrets bindings, and devenv process lifecycle.

TelePi:
  Bridges Telegram messages into Pi Agent sessions for the configured workspace.

Devenv:
  Provides reproducible environment setup and process management via devenv up.
```

---

## TelePi Capability Assumptions

TelePi's implementation supports the general shape needed for this design:

1. TelePi can run as a standalone process.
2. TelePi loads configuration from environment variables and a config env file.
3. TelePi can derive its workspace from Docker `/workspace`, `TELEPI_WORKSPACE`, or `process.cwd()`.
4. TelePi creates Pi sessions against a workspace.
5. TelePi's session/task model is context-scoped, meaning separate bot processes are naturally isolated.
6. TelePi can hand a session back to the normal Pi CLI by producing a `pi --session ...` command.

For the MyPi-Agent model, the most important detail is that a TelePi process can be started with a deterministic working directory and `TELEPI_WORKSPACE` value. That is enough to make the process repo-scoped.

---

## Local Development Architecture

### Target Local Runtime

For local development, each repo runs TelePi through `devenv up`.

```text
~/dev/project-a/
  devenv.yaml
  devenv.nix
  devenv.local.yaml       # ignored local secrets/config references
  .mypi/
    telepi/
      .env                # ignored TelePi local config

~/dev/project-b/
  devenv.yaml
  devenv.nix
  devenv.local.yaml
  .mypi/
    telepi/
      .env
```

Each project has its own process definition:

```text
processes.telepi -> mypi telepi run
```

The project owner starts the repo agent with:

```bash
devenv up
```

That starts TelePi for that repo only.

---

## Telegram Bot Strategy

The recommended initial approach is **one Telegram bot per repo**.

Example:

```text
@MyPiProjectABot -> controls project-a
@MyPiProjectBBot -> controls project-b
@MyPiProjectCBot -> controls project-c
```

This is operationally heavier than using one bot with forum topics, but it has clearer isolation:

```text
wrong bot = wrong repo, visibly obvious
no workspace switching required
no accidental cross-repo prompts
no shared busy state between projects
no topic/session mapping to remember
```

The tradeoff is that the user must create and manage one Telegram bot token per repo. This is acceptable for the initial MyPi-Agent model because the number of active repo agents is likely to be small, and the isolation benefits are significant.

---

## What Can Be Programmatically Initialized

Almost everything can be generated programmatically once the user has created the external API keys and bot token.

`mypi init --telepi` or `mypi telepi init` can generate:

```text
.mypi/telepi/
.mypi/telepi/.env
.mypi/telepi/.env.example
.gitignore entries
devenv.local.yaml entries or instructions
devenv process config
TelePi config validation
secretspec/devenv secret references
doctor checks
```

The only pieces that cannot be fully generated locally are external credentials:

```text
Telegram bot token
Telegram allowed user ID
LLM provider API keys
```

The Telegram bot token generally comes from BotFather. Provider API keys come from each provider's dashboard or an existing central secrets file.

---

## Recommended Initialization UX

The desired user experience should be:

```bash
mypi init --telepi
# provide or bind the repo's Telegram bot token once
# provide or bind Telegram allowed user ID once

devenv up
```

After that, normal operation should be:

```bash
devenv up
```

The user should not need to manually write TelePi config, process definitions, or workspace paths.

---

## MyPi CLI Responsibilities

The MyPi CLI should own all TelePi integration logic instead of exposing raw TelePi details to the consuming repo.

Recommended command set for the initial implementation:

```bash
mypi telepi init
mypi telepi run
mypi telepi doctor
```

Later command set:

```bash
mypi telepi status
mypi telepi logs
mypi telepi service install
mypi telepi service start
mypi telepi service stop
mypi telepi rotate-token
```

However, when using devenv process management, OS-level service commands should be deferred. The initial lifecycle should be handled by `devenv up`.

---

## `mypi telepi init`

`mypi telepi init` should be idempotent. Running it multiple times should safely update or validate the repo setup without destroying user configuration.

Responsibilities:

1. Detect the repo root.
2. Confirm the repo is inside a devenv-managed project.
3. Create `.mypi/telepi/`.
4. Create `.mypi/telepi/.env` for repo-local TelePi config.
5. Create `.mypi/telepi/.env.example` for documentation.
6. Add `.mypi/telepi/.env` to `.gitignore`.
7. Ensure the MyPi devenv import is present or give exact instructions.
8. Ensure a `processes.telepi` process is provided by the MyPi module.
9. Check whether required secrets are available.
10. Print any missing values.
11. Optionally prompt for local secret values or generate a `devenv.local.yaml` template.

State machine:

```text
Uninitialized
  -> create local MyPi/TelePi files
  -> add gitignore entries
  -> check devenv import
  -> check secrets
  -> initialized

Initialized but missing secrets
  -> report exact missing variables
  -> optionally write local bindings
  -> initialized

Initialized and valid
  -> no-op except report current status
```

---

## `mypi telepi run`

The devenv process should call only one stable command:

```bash
mypi telepi run
```

This command should:

1. Detect the repo root.
2. Load `.mypi/telepi/.env` if present.
3. Set `TELEPI_CONFIG=.mypi/telepi/.env`.
4. Set `TELEPI_WORKSPACE` to the repo root if missing.
5. Verify `TELEGRAM_BOT_TOKEN` exists.
6. Verify `TELEGRAM_ALLOWED_USER_IDS` exists.
7. Verify provider API keys or Pi auth are available.
8. Exec TelePi.

The devenv process should not need to know TelePi's internal configuration details. It should delegate to MyPi.

---

## `mypi telepi doctor`

`mypi telepi doctor` should provide a deterministic check of the current repo's TelePi readiness.

It should validate:

```text
devenv shell is active
pi binary exists
telepi binary exists
mypi binary exists
repo root is detected
TELEPI_WORKSPACE points to the repo root
TELEGRAM_BOT_TOKEN exists
TELEGRAM_ALLOWED_USER_IDS exists
provider API keys are available or Pi auth is configured
.mypi/telepi/.env exists
.mypi/telepi/.env is gitignored
devenv process telepi is available
```

It should produce actionable output:

```text
OK: pi binary found
OK: telepi binary found
MISSING: TELEGRAM_BOT_TOKEN
FIX: add TELEGRAM_BOT_TOKEN to devenv.local.yaml or central secretspec source
```

---

## Recommended Repo File Layout

Recommended generated structure:

```text
project-a/
  devenv.yaml
  devenv.nix
  devenv.local.yaml          # ignored; optional local secret bindings
  .gitignore
  .mypi/
    telepi/
      .env                   # ignored; repo-local TelePi config
      .env.example           # optional committed example
```

Suggested `.gitignore` entries:

```gitignore
# MyPi local runtime config
.mypi/telepi/.env

# Local devenv overrides / secrets
devenv.local.yaml
```

---

## Recommended `.mypi/telepi/.env`

The local TelePi env file should contain repo-specific non-secret defaults.

Example:

```env
TELEPI_WORKSPACE=/absolute/path/to/project-a
TOOL_VERBOSITY=summary
PI_MODEL=openai:gpt-5.1-codex-mini
```

Secrets should preferably come from the active devenv environment rather than this file.

Avoid putting these directly in `.mypi/telepi/.env` if secretspec/devenv can supply them:

```env
TELEGRAM_BOT_TOKEN=...
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
```

This keeps the repo-local file focused on workspace behavior, not secret storage.

---

## Recommended `.mypi/telepi/.env.example`

A committed example can document the expected values without exposing secrets.

```env
# Repo-local TelePi config
TELEPI_WORKSPACE=/absolute/path/to/this/repo
TOOL_VERBOSITY=summary
PI_MODEL=openai:gpt-5.1-codex-mini

# Prefer supplying these through devenv.local.yaml or secretspec:
# TELEGRAM_BOT_TOKEN=
# TELEGRAM_ALLOWED_USER_IDS=
# OPENAI_API_KEY=
# ANTHROPIC_API_KEY=
```

---

## Devenv Process Integration

The MyPi-Agent devenv module should provide a process that starts TelePi through MyPi.

Conceptual Nix configuration:

```nix
{ config, ... }:

{
  processes.telepi = {
    exec = ''
      mypi telepi run
    '';
    cwd = "${config.git.root}";
    restart.on = "on_failure";
  };
}
```

This keeps the process definition stable across repos.

The consuming repo should not need to manually define TelePi unless it wants custom behavior.

---

## Devenv Import Model

Each consuming repo should import MyPi-Agent through `devenv.yaml`.

Conceptual example:

```yaml
imports:
  - github:your-org/mypi-agent
```

The imported MyPi module should provide:

```text
pi binary
mypi CLI
TelePi package/binary
processes.telepi
init/doctor/run scripts
shared defaults
```

The consuming repo supplies only repo-specific local configuration and secrets.

---

## Secrets Strategy

The preferred model is:

```text
central secret source
  -> secretspec/devenv local binding
  -> environment variables inside devenv shell
  -> mypi telepi run
  -> TelePi process
```

This avoids writing sensitive values into repo-local files.

Required secret/environment values:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_ALLOWED_USER_IDS
OPENAI_API_KEY or other provider keys
ANTHROPIC_API_KEY, if used
other Pi provider credentials, as needed
```

Repo-local non-secret values:

```text
TELEPI_WORKSPACE
TOOL_VERBOSITY
PI_MODEL
```

---

## Per-Repo Bot Token Management

Each repo should have its own Telegram bot token.

Naming convention:

```text
mypi-project-a-bot
mypi-project-b-bot
mypi-project-c-bot
```

The MyPi initialization flow should ask for the token or check whether the token is already available through secretspec/devenv.

Recommended secret names:

```text
PROJECT_A_TELEGRAM_BOT_TOKEN
PROJECT_B_TELEGRAM_BOT_TOKEN
```

Then the repo's local devenv binding maps the project-specific secret to the generic variable TelePi expects:

```text
PROJECT_A_TELEGRAM_BOT_TOKEN -> TELEGRAM_BOT_TOKEN
```

This allows TelePi to remain generic while secrets remain project-specific.

---

## Pi Config Directory Strategy

The recommended default is **shared Pi auth/config with per-repo TelePi services**.

Do not create separate Pi `.config/` or auth directories per repo by default.

Default model:

```text
shared Pi identity/auth/config
many repo-local TelePi services
many repo-local Telegram bot tokens
many repo-local workspaces
```

This is simpler and sufficient for most personal development workflows.

Use separate Pi config/auth directories only when stronger isolation is required, such as:

```text
different provider accounts per repo
different billing/account boundaries
client projects that must not share auth
untrusted repos
testing MyPi against clean Pi state
```

If hard isolation is needed later, MyPi can add an opt-in mode:

```bash
mypi telepi init --isolated-pi-config
```

That mode could set repo-specific Pi config/cache/auth paths, but it should not be the default.

---

## Local Runtime Example

A complete local flow could look like this:

```bash
cd ~/dev/project-a

devenv shell
mypi init --telepi
# paste Telegram bot token or bind it through secretspec
# confirm Telegram allowed user ID

devenv up
```

Then Telegram usage:

```text
Open @MyPiProjectABot
Send: summarize this repo
Send: run the test suite
Send: inspect failing tests and propose a fix
```

For another repo:

```bash
cd ~/dev/project-b

devenv shell
mypi init --telepi

devenv up
```

And use a different bot:

```text
Open @MyPiProjectBBot
```

---

## Remote Container Architecture

The same repo-scoped devenv model can be moved to a remote computer by running each repo in its own container.

Target shape:

```text
remote host
  project-a container
    -> devenv process set
    -> TelePi for project-a

  project-b container
    -> devenv process set
    -> TelePi for project-b

  project-c container
    -> devenv process set
    -> TelePi for project-c
```

Each container gets:

```text
one repo workspace
one TelePi process
one Telegram bot token
one environment/secrets set
one failure boundary
```

---

## Remote Deployment Options

### Option A: Build a Devenv Container Per Repo

This is the recommended eventual model.

Each repo builds a container image from its devenv environment. The container starts the TelePi process or the full `devenv` process set.

Conceptual flow:

```bash
cd project-a
mypi deploy build
mypi deploy push
```

Then on the remote host:

```bash
docker compose up -d project-a-telepi
```

Advantages:

```text
reproducible runtime
fast startup
clear deployment artifact
works well with CI/CD
remote host does not need to evaluate every repo from scratch at runtime
```

Disadvantages:

```text
requires image build/push flow
requires registry or image transfer strategy
```

### Option B: Run Devenv Inside a Generic Container

This is easier for early prototyping.

The remote container contains Nix/devenv, clones or mounts the repo, then runs:

```bash
devenv up
```

Advantages:

```text
simple early experiment
no custom image build required at first
```

Disadvantages:

```text
slower startup
more runtime complexity
less deterministic deployment artifact
remote host does more work
```

Recommendation:

```text
Prototype with Option B only if needed.
Move to Option A once the process shape is stable.
```

---

## Remote Host Directory Layout

Recommended remote layout:

```text
/srv/mypi/
  shared/
    pi/
      # optional shared Pi auth/session/config storage

  repos/
    project-a/
      workspace/
      state/
      env

    project-b/
      workspace/
      state/
      env
```

For shared Pi auth/config:

```text
/srv/mypi/shared/pi -> /home/mypi/.pi inside each container
```

For stronger per-repo isolation:

```text
/srv/mypi/repos/project-a/pi -> /home/mypi/.pi inside project-a container
/srv/mypi/repos/project-b/pi -> /home/mypi/.pi inside project-b container
```

Default recommendation:

```text
shared Pi auth/config for personal projects
per-repo Pi auth/config only for stronger isolation needs
```

---

## Remote Docker Compose Shape

Conceptual `compose.yaml`:

```yaml
services:
  project-a-telepi:
    image: registry.example.com/project-a-telepi:latest
    container_name: mypi-project-a
    restart: unless-stopped
    env_file:
      - /srv/mypi/repos/project-a/env
    volumes:
      - /srv/mypi/repos/project-a/workspace:/workspace
      - /srv/mypi/shared/pi:/home/mypi/.pi

  project-b-telepi:
    image: registry.example.com/project-b-telepi:latest
    container_name: mypi-project-b
    restart: unless-stopped
    env_file:
      - /srv/mypi/repos/project-b/env
    volumes:
      - /srv/mypi/repos/project-b/workspace:/workspace
      - /srv/mypi/shared/pi:/home/mypi/.pi
```

Each service has its own `env` file containing or referencing:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_ALLOWED_USER_IDS
TELEPI_WORKSPACE=/workspace
provider API keys
```

Inside a container, `TELEPI_WORKSPACE` should usually be `/workspace`.

---

## Remote Secrets Strategy

Remote secrets should not be committed to repo source.

Use one of these approaches:

```text
per-repo env files on the remote host
central secretspec-compatible env source mounted read-only
Docker secrets / Podman secrets
SOPS/age-managed encrypted files decrypted during deployment
CI/CD secret injection
```

For the initial MyPi-Agent concept, per-repo remote env files are simplest:

```text
/srv/mypi/repos/project-a/env
/srv/mypi/repos/project-b/env
```

Example:

```env
TELEGRAM_BOT_TOKEN=123456789:project_a_token
TELEGRAM_ALLOWED_USER_IDS=123456789
TELEPI_WORKSPACE=/workspace
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
TOOL_VERBOSITY=summary
PI_MODEL=openai:gpt-5.1-codex-mini
```

Later, MyPi can support secretspec-driven remote rendering.

---

## MyPi Deployment Commands

A future deployment layer could add:

```bash
mypi deploy init
mypi deploy build
mypi deploy push
mypi deploy render-compose
mypi deploy up
mypi deploy down
mypi deploy logs
mypi deploy status
```

However, these should be added after the local repo-scoped model is working.

Initial deployment support can be limited to generating documentation and config fragments:

```bash
mypi telepi init --container
```

That command could generate:

```text
.mypi/deploy/
  compose.fragment.yaml
  remote.env.example
  README.md
```

---

## Remote Deployment Phases

Recommended implementation sequence:

### Phase 1: Local Devenv TelePi

Goal:

```text
per-repo TelePi works locally with devenv up
```

Deliverables:

```text
mypi telepi init
mypi telepi run
mypi telepi doctor
processes.telepi
```

### Phase 2: Container Target

Goal:

```text
each repo can build a TelePi-capable container
```

Deliverables:

```text
devenv container definition
container-specific TELEPI_WORKSPACE=/workspace behavior
remote env example
```

### Phase 3: Remote Compose

Goal:

```text
remote host runs one container per repo
```

Deliverables:

```text
compose fragment generation
remote volume layout
manual docker compose up flow
```

### Phase 4: MyPi Deployment Automation

Goal:

```text
MyPi can build, push, deploy, restart, and inspect remote repo agents
```

Deliverables:

```text
mypi deploy build
mypi deploy push
mypi deploy up
mypi deploy logs
mypi deploy status
```

Do not build Phase 4 first. Start with the local process contract.

---

## Risks and Tradeoffs

### More Bot Tokens

One bot per repo means more Telegram bot tokens to manage.

Mitigation:

```text
standard bot naming convention
central secrets mapping
mypi doctor checks
clear per-repo init flow
```

### More Processes

Each repo has its own TelePi process.

Mitigation:

```text
use devenv up locally
use compose remotely
make logs/status easy through MyPi
```

### Secret Sprawl

Per-repo bot tokens can create scattered secret management.

Mitigation:

```text
central secretspec source
repo-local binding only
avoid committing secret values
```

### Shared Pi Auth Ambiguity

Shared Pi auth/config is convenient but may not be appropriate for all projects.

Mitigation:

```text
default to shared auth
support opt-in isolated auth later
```

### Remote Workspace Synchronization

Remote containers need access to up-to-date repo source.

Mitigation options:

```text
build source into the image
mount a git checkout on the remote host
sync via git pull/deploy command
sync via CI/CD
```

For early use, mounting a remote git checkout is easiest. For reproducible deployment, building source into the image is better.

---

## Recommended Initial Implementation

Build the smallest useful integration first.

### MyPi-Agent should provide:

```text
pi binary
telepi binary
mypi CLI
processes.telepi
mypi telepi init
mypi telepi run
mypi telepi doctor
```

### A consuming repo should need only:

```bash
mypi init --telepi
# provide/bind keys

devenv up
```

### Generated local config should include:

```text
.mypi/telepi/.env
.mypi/telepi/.env.example
.gitignore entries
optional devenv.local.yaml template
```

### Defer until later:

```text
multi-repo dashboard
remote deployment automation
OS-level launchd/systemd services
per-repo Pi config directories
advanced token rotation
```

---

## Final Target UX

For a new local project:

```bash
cd ~/dev/new-project

devenv shell
mypi init --telepi
# paste or bind the Telegram bot token
# confirm allowed Telegram user ID

devenv up
```

From then on:

```bash
cd ~/dev/new-project
devenv up
```

For a remote project later:

```bash
mypi deploy build
mypi deploy push
mypi deploy up
```

The conceptual rule stays the same in both environments:

```text
repo boundary = devenv boundary = TelePi process boundary = Telegram bot boundary
```

This is the cleanest starting architecture for integrating TelePi into MyPi-Agent while preserving the repo-scoped philosophy of the library.

