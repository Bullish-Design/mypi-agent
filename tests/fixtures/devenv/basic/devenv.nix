{ inputs, ... }:
{
  imports = [
    (inputs.mypi-agent + "/modules/pi-agent.nix")
  ];

  piAgent.enable = true;

  tasks."fixture:verify".exec = ''
    set -euxo pipefail
    mypi sync
    mypi doctor
  '';
}
