# mypi-agent

Nix/devenv module that provisions and manages Pi agent state for a project.

## Generated file policy

Commit these files:
- `.pi/settings.json`

Optional to commit:
- `.agents/pi/manifest.json`

Do not commit runtime/install artifacts:
- `.agents/pi/node_modules/`
- `.agents/pi/.npm-cache/`
- `.agents/pi/bin/`
- `.agents/pi/.state/`
