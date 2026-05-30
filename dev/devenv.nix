# Non-Allium development tooling for MYPI-Agent.
{ pkgs, ... }:

{
  packages = [
    pkgs.git
    pkgs.uv
  ];
}
