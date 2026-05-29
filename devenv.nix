{ pkgs, lib, config, inputs, ... }:

let
  allium = pkgs.stdenv.mkDerivation {
    pname = "allium";
    version = "3.2.3";

    src = pkgs.fetchurl {
      url = "https://github.com/juxt/allium-tools/releases/download/v3.2.3/allium-x86_64-unknown-linux-gnu.tar.gz";
      hash = "sha256-Phr77ZmwOaH+ZZsaOqpp27J0v+GKBoBXHJ0KSrOsIF8=";
    };

    sourceRoot = ".";
    dontBuild = true;

    installPhase = ''
      runHook preInstall

      mkdir -p $out/bin
      binary="$(find . -type f -name allium | head -n1)"

      if [ -z "$binary" ]; then
        echo "Could not find allium binary in release archive" >&2
        exit 1
      fi

      install -m755 "$binary" "$out/bin/allium"

      runHook postInstall
    '';
  };

  alliumRepo = "https://github.com/juxt/allium.git";
  alliumCommit = "82da292e989d518f79189fdfef4446d0d517c277";
  alliumVendorDir = ".vendor/allium";

  alliumSkills = [
    "allium"
    "elicit"
    "distill"
    "propagate"
    "tend"
    "weed"
  ];
in

{
  # https://devenv.sh/basics/
  env.GREET = "devenv";

  # https://devenv.sh/packages/
  packages = [
    pkgs.git
    pkgs.uv
    allium
  ];

  # https://devenv.sh/languages/
  # languages.rust.enable = true;
  languages = {
      python = {
          enable = true;
          version = "3.13";
          venv.enable = true;
          uv.enable = true;
        };
    };

  # https://devenv.sh/processes/
  # processes.cargo-watch.exec = "cargo-watch";

  # https://devenv.sh/services/
  # services.postgres.enable = true;

  # https://devenv.sh/scripts/
  scripts.hello.exec = ''
    echo hello from $GREET
  '';

  scripts.allium-check.exec = ''
    allium check .scratch/specs/
  '';

  scripts.allium-analyse.exec = ''
    allium analyse .scratch/specs/
  '';

  scripts.install-allium-codex-skills.exec = ''
    set -euo pipefail

    ALLIUM_REPO="${alliumRepo}"
    ALLIUM_COMMIT="${alliumCommit}"
    ALLIUM_VENDOR_DIR="${alliumVendorDir}"
    CODEX_SKILLS_DIR=".agents/skills"

    echo
    echo "Installing Allium Codex skills"
    echo "Repo:   $ALLIUM_REPO"
    echo "Commit: $ALLIUM_COMMIT"
    echo "Target: $ALLIUM_VENDOR_DIR"
    echo

    if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
      echo "Error: run this from inside a Git repository." >&2
      exit 1
    fi

    repo_root="$(git rev-parse --show-toplevel)"
    cd "$repo_root"

    mkdir -p .vendor .agents/skills

    if [ -d "$ALLIUM_VENDOR_DIR/.git" ]; then
      echo "Error: $ALLIUM_VENDOR_DIR looks like a nested Git repo, not a subtree." >&2
      exit 1
    fi

    if [ ! -d "$ALLIUM_VENDOR_DIR" ]; then
      echo "Adding Allium subtree..."
      git subtree add \
        --prefix "$ALLIUM_VENDOR_DIR" \
        "$ALLIUM_REPO" \
        "$ALLIUM_COMMIT" \
        --squash
    else
      echo "Updating Allium subtree..."
      git subtree pull \
        --prefix "$ALLIUM_VENDOR_DIR" \
        "$ALLIUM_REPO" \
        "$ALLIUM_COMMIT" \
        --squash
    fi

    for skill in ${builtins.concatStringsSep " " alliumSkills}; do
      source_path="../../$ALLIUM_VENDOR_DIR/skills/$skill"
      link_path="$CODEX_SKILLS_DIR/$skill"
      actual_source="$ALLIUM_VENDOR_DIR/skills/$skill"

      if [ ! -f "$actual_source/SKILL.md" ]; then
        echo "Error: expected $actual_source/SKILL.md to exist." >&2
        exit 1
      fi

      if [ -L "$link_path" ]; then
        rm "$link_path"
      elif [ -e "$link_path" ]; then
        echo "Error: $link_path already exists and is not a symlink." >&2
        echo "Remove it manually before rerunning this script." >&2
        exit 1
      fi

      ln -s "$source_path" "$link_path"
      echo "Linked $link_path -> $source_path"
    done

    echo
    echo "Allium Codex skills installed."
    echo "Next:"
    echo "  git status"
    echo "  git add .vendor/allium .agents/skills"
    echo "  git commit -m 'Vendor Allium Codex skills'"
    echo 
  '';


  enterShell = ''
    echo
    hello
    git --version
    echo
  '';

  # https://devenv.sh/tasks/
  # tasks = {
  #   "myproj:setup".exec = "mytool build";
  #   "devenv:enterShell".after = [ "myproj:setup" ];
  # };

  # https://devenv.sh/tests/
  enterTest = ''
    echo "Running tests"
    git --version | grep --color=auto "${pkgs.git.version}"
  '';

  # https://devenv.sh/pre-commit-hooks/
  # pre-commit.hooks.shellcheck.enable = true;

  # See full reference at https://devenv.sh/reference/options/
}
