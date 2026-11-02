import argparse

import uvicorn

from simulacra.api.app import create_app
from simulacra.config import get_settings
from simulacra.persistence import migrate


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="simulacra")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("up", help="start the API and serve the web UI on localhost")
    sub.add_parser("migrate", help="apply database migrations")
    args = parser.parse_args(argv)

    settings = get_settings()
    if args.command == "migrate":
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        migrate.upgrade(settings.database_url)
    elif args.command == "up":
        uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
