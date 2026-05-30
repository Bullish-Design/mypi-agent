{ pkgs, lib, ... }:
{
  imports = [ ./modules/pi-agent.nix ];
  piAgent.enable = lib.mkDefault true;
  piAgent.secrets = {
    enable = true;
  };

  packages = [
    pkgs.secretspec
  ];
}
