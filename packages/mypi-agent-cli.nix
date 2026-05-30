{ lib, python313Packages }:

python313Packages.buildPythonApplication {
  pname = "mypi-agent";
  version = "0.2.0";
  src = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      ../pyproject.toml
      ../README.md
      ../src
    ];
  };
  pyproject = true;

  build-system = [
    python313Packages.hatchling
  ];

  dependencies = [
    python313Packages.pydantic
    python313Packages.typer
  ];

  pythonImportsCheck = [ "mypi_agent" ];

  meta = with lib; {
    description = "Repo-scoped MYPI/Pi bootstrap CLI for devenv/Nix";
    license = licenses.mit;
    platforms = platforms.all;
  };
}
