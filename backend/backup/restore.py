import os
import subprocess
import sys


def restore_snapshot(snapshot_path):
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    command = [
        "pg_restore",
        "--clean",
        "--if-exists",
        "--dbname",
        database_url,
        snapshot_path,
    ]

    subprocess.run(command, check=True)

    print(f"Restored snapshot: {snapshot_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python restore.py <snapshot.dump>")
        sys.exit(1)

    restore_snapshot(sys.argv[1])