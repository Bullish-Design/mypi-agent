{ pkgs, lib, ... }:
{
  imports = [ ./modules/pi-agent.nix ];
  piAgent.enable = lib.mkDefault true;

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
