{ lib, python3Packages }:

python3Packages.buildPythonApplication {
  pname = "mypi-agent";
  version = "0.1.0";
  src = ../.;
  pyproject = true;

  build-system = [
    python3Packages.hatchling
  ];

  dependencies = [
    python3Packages.pydantic
    python3Packages.typer
  ];

  pythonImportsCheck = [ "mypi_agent" ];

  meta = with lib; {
    description = "MYPI-AGENT CLI";
    license = licenses.mit;
    platforms = platforms.all;
  };
}
