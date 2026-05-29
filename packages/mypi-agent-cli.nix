{ lib, python313Packages }:

python313Packages.buildPythonApplication {
  pname = "mypi-agent";
  version = "0.1.0";
  src = ../.;
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
    description = "MYPI-AGENT CLI";
    license = licenses.mit;
    platforms = platforms.all;
  };
}
