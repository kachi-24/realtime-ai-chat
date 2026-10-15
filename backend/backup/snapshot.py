import hashlib
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import sentry_sdk

# --- CONFIGURATION ---
CONTAINER_NAME = "realtime-ai-chat-postgres"
RETENTION_COUNT = 7
# ---------------------

# Dynamic calculation matching your requirements (points to application root 'backups')
BACKUP_DIR = Path(__file__).resolve().parents[2] / "backups"
BACKUP_DIR.mkdir(exist_ok=True)


def calculate_sha256(file_path: Path) -> str:
    """Calculates the SHA-256 hash of a file streaming chunks to safely support large backups."""
    sha256 = hashlib.sha256()
    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def clean_old_backups():
    """Enforces the retention policy by keeping only the most recent snapshots."""
    print(f"Enforcing retention policy (keeping last {RETENTION_COUNT})...")
    all_dumps = sorted(BACKUP_DIR.glob("realtime_chat_*.dump"))

    if len(all_dumps) <= RETENTION_COUNT:
        print("No old backups to purge.")
        return

    to_delete = all_dumps[:-RETENTION_COUNT]
    for dump_file in to_delete:
        try:
            dump_file.unlink()
            print(f"Purged old backup file: {dump_file.name}")

            checksum_file = dump_file.with_suffix(".sha256")
            if checksum_file.exists():
                checksum_file.unlink()
                print(f"Purged old checksum file: {checksum_file.name}")
        except Exception as exc:
            print(f"Warning: Failed to purge old file {dump_file.name}: {exc}")
            sentry_sdk.capture_exception(exc)


def create_snapshot():
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    backup_file = BACKUP_DIR / f"realtime_chat_{timestamp}.dump"
    checksum_file = BACKUP_DIR / f"realtime_chat_{timestamp}.sha256"

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    database_url = database_url.strip()

    # Refuse to overwrite an existing snapshot
    if backup_file.exists():
        exc = FileExistsError(f"Backup already exists: {backup_file}")
        sentry_sdk.capture_exception(exc)
        raise exc

    # Parse connection string to extract parameters for Docker exec pg_dump execution
    try:
        clean_url = database_url.replace("postgresql+asyncpg://", "").replace("postgresql://", "")
        auth_part, rest = clean_url.split("@")
        db_user = auth_part.split(":")[0]
        db_name = rest.split("/")[-1].split("?")[0]
    except Exception as parse_exc:
        exc = RuntimeError(f"Failed to parse DATABASE_URL: {parse_exc}")
        sentry_sdk.capture_exception(exc)
        raise exc

    command = [
        "docker", "exec", "-i",
        CONTAINER_NAME,
        "pg_dump",
        "-U", db_user,
        "-d", db_name,
        "--format=custom"
    ]

    try:
        print(f"Running pg_dump inside Docker container '{CONTAINER_NAME}'...")

        # Stream from container directly into target host backup file safely preserving header streams
        with open(backup_file, "wb") as f:
            subprocess.run(command, stdout=f, check=True)

        # Validate that the file was generated and contains actual data
        if not backup_file.exists() or backup_file.stat().st_size == 0:
            raise RuntimeError("Backup file was created but is empty")

        # Generate and save SHA-256 Checksum
        checksum = calculate_sha256(backup_file)
        checksum_file.write_text(checksum, encoding="utf-8")

        # Immediate programmatic validation verification hook
        verified_checksum = calculate_sha256(backup_file)
        if checksum != verified_checksum:
            raise RuntimeError("Backup checksum verification failed (mismatch on immediate reread)")

        print(f"Snapshot created: {backup_file.name}")
        print(f"SHA256: {checksum}")
        print("Backup verification: PASSED")

        # Run retention pruning after successful validation checks
        clean_old_backups()

        return backup_file

    except Exception as exc:
        # Catch-all reports any process errors or stream validation breakdowns to Sentry
        sentry_sdk.capture_exception(exc)
        raise


if __name__ == "__main__":
    create_snapshot()
