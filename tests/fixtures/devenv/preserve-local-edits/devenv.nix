{ inputs, ... }:
{
  imports = [
    (inputs.mypi-agent + "/modules/pi-agent.nix")
  ];

  piAgent = {
    enable = true;
    bootstrap.mode = "manual_only";
  };

  tasks."fixture:verify".exec = ''
    set -euxo pipefail
    mypi sync
    mypi doctor
  '';
}
