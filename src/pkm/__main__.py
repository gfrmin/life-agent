"""Enable ``python -m pkm`` to invoke the CLI."""

from pkm.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
