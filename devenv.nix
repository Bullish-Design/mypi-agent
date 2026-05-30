{ pkgs, lib, ... }:
{
  imports = [ ./modules/pi-agent.nix ];
  piAgent.secrets = {
    enable = true;
  };

  packages = [
    pkgs.secretspec
  ];
}
