{ pkgs, ... }:
{
  env.GREET = "devenv";

  packages = [
    pkgs.git
    pkgs.uv
  ];

  languages = {
    python = {
      enable = true;
      version = "3.13";
      venv.enable = true;
      uv.enable = true;
    };
  };

  scripts.hello.exec = ''
    echo hello from $GREET
  '';

  allium.enable = true;
  allium.specsDir = ".scratch/specs";
  allium.codexSkills.enable = true;
  allium.codexSkills.autoInstall = true;
  allium.codexSkills.targetDir = ".agents/skills";

  enterShell = ''
    echo
    hello
    git --version
    echo
  '';

  enterTest = ''
    echo "Running tests"
    git --version | grep --color=auto "${pkgs.git.version}"
  '';
}
