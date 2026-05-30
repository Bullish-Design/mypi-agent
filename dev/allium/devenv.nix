# Allium configuration for MYPI-Agent development only.
# This file is imported by root devenv.yaml and is NOT part of
# the public downstream import surface (root devenv.nix).
{ pkgs, ... }:

{
  allium.enable = true;
  allium.specsDir = ".scratch/specs";
  allium.codexSkills = {
    enable = true;
    autoInstall = true;
    targetDir = ".agents/skills";
  };
}
