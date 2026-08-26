{ inputs, ... }:
{
  imports = [
    (inputs.mypi-agent + "/modules/pi-agent.nix")
  ];

  piAgent = {
    enable = true;
    settings = {
      defaultProvider = "openrouter";
      defaultModel = "stealth/ox-alpha";
    };
    models.providers.openrouter.models = [
      {
        id = "stealth/ox-alpha";
        reasoning = true;
      }
    ];
  };

  tasks."fixture:verify".exec = ''
    set -euxo pipefail
    mkdir -p .fake-bin
    cat > .fake-bin/npm <<'SH'
    #!/usr/bin/env sh
    set -eu
    prefix=
    pkg_name=
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --prefix) shift; prefix="$1" ;;
        @*) pkg_name="$1" ;;
      esac
      shift
    done
    [ -n "$prefix" ] || exit 1
    base_name=$(echo "$pkg_name" | sed 's/@[^@/]*$//')
    [ -n "$base_name" ] || base_name="@earendil-works/pi-coding-agent"
    mkdir -p "$prefix/node_modules/.bin" "$prefix/node_modules/$base_name"
    cat > "$prefix/node_modules/.bin/pi" <<'PI'
    #!/usr/bin/env sh
    echo pi 0.0.1-fixture
    PI
    chmod +x "$prefix/node_modules/.bin/pi"
    cat > "$prefix/node_modules/$base_name/package.json" <<'PKG'
    {"name":"@earendil-works/pi-coding-agent","version":"0.0.1-fixture"}
    PKG
    SH
    chmod +x .fake-bin/npm
    export PATH="$PWD/.fake-bin:$PATH"
    test -f .agents/pi/.pi-state/settings.json
    grep -F '"defaultProvider":"openrouter"' .agents/pi/.pi-state/settings.json
    test -f .agents/pi/.pi-state/models.json
    grep -F '"id":"stealth/ox-alpha"' .agents/pi/.pi-state/models.json
    mypi sync
    mypi doctor
  '';
}
