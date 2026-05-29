{ ... }:
{
  tasks."fixture:verify".exec = ''
    set -euxo pipefail
    command -v mypi
    command -v node
    command -v npm
    mypi paths --json
    mypi sync --trigger shell
    mypi doctor
  '';
}
