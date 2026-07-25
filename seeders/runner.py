import argparse
import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")

import django

django.setup()

SEEDERS = [
    "role_seeder",
    "user_seeder",
    "academic_department_seeder",
]


def list_seeders() -> None:
    """Display all available seeders."""
    print("Available seeders:")
    for name in SEEDERS:
        print(f" - {name}")


def run_seeder(name: str) -> dict:
    """Import and execute a seeder."""
    module = importlib.import_module(f"seeders.{name}")
    return module.run()


def main() -> None:

    parser = argparse.ArgumentParser(description="Run one or more database seeders.")

    parser.add_argument(
        "seeders",
        nargs="*",
        help="Seeder names to run. Runs all seeders by default.",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List available seeders.",
    )

    args = parser.parse_args()

    if args.list:
        list_seeders()
        return

    selected = args.seeders or SEEDERS

    invalid = [name for name in selected if name not in SEEDERS]

    if invalid:
        print(f"Unknown seeder(s): {', '.join(invalid)}")
        print("Run with '--list' to see available seeders.")
        raise SystemExit(1)

    print("Starting database seeding...\n")

    for name in selected:
        print(f"Running {name}...")
        result = run_seeder(name)

        print(
            f"Completed {name}. "
            f"Created: {result.get('created', 0)}, "
            f"Existing: {result.get('existing', 0)}, "
            f"Skipped: {result.get('skipped', False)}"
        )
        print()

    print("Database seeding completed successfully.")


if __name__ == "__main__":
    main()