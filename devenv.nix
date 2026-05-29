{ lib, ... }:
{
  imports = [ ./modules/pi-agent.nix ];
  piAgent.enable = lib.mkDefault true;
}
