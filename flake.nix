{
  description = "Channel_To_Summary: daily channel recaps with a local LLM";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      # Keep in step with the FROM line in Dockerfile and requires-python in
      # pyproject.toml.
      python = pkgs.python314;
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        packages = [
          python
          pkgs.uv
          pkgs.ruff
          # llama-cpp-python builds llama.cpp from source on uv sync.
          pkgs.cmake
        ];

        # uv's own Python downloads are built for a generic Linux and won't
        # start on NixOS: always use the one above.
        UV_PYTHON = python.interpreter;
        UV_PYTHON_DOWNLOADS = "never";

        # Wheels with compiled code (aiohttp is fine, but e.g. faster-whisper,
        # numpy) expect libstdc++ and zlib where a regular distro has them.
        LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
          pkgs.stdenv.cc.cc.lib
          pkgs.zlib
        ];

        # Creates or updates .venv from uv.lock (a no-op when it's current)
        # and puts it first on PATH, so `python -m bot` just works.
        shellHook = ''
          if [ -f pyproject.toml ]; then
            uv sync --quiet
            export VIRTUAL_ENV="$PWD/.venv"
            export PATH="$VIRTUAL_ENV/bin:$PATH"
          fi
        '';
      };
    };
}
