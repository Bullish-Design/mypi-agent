# Non-Allium development tooling for MYPI-Agent.
{ pkgs, ... }:

{
  packages = [
    pkgs.git
    pkgs.uv
  ];

  languages.python = {
    enable = true;
    package = pkgs.python313;
    venv.enable = true;

    uv = {
      enable = true;
      sync = {
        enable = true;
        allExtras = true;
      };
    };
  };
}
