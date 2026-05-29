{ inputs, ... }:
{
  imports = [
    (inputs.mypi-agent + "/modules/pi-agent.nix")
  ];

  piAgent = {
    enable = true;
    root = ".agents/custom-pi";
    bootstrap.mode = "first_entry_only";
  };

  tasks."fixture:verify".exec = ''
    set -euxo pipefail
    mypi sync
    mypi doctor
  '';
}
