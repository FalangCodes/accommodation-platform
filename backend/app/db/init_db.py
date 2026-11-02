"""Retired destructive reset entry point. Database changes use Alembic."""
import sys


def main():
    print(
        "Database reset is disabled. No database connection was opened.\n"
        "For a new installation, run from the project root:\n"
        "  docker compose run --rm --no-deps backend alembic upgrade head\n"
        "Existing data must be preserved; this command never drops tables.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
