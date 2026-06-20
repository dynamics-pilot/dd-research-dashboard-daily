from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from smtp_secret_dpapi import protect_text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--secret-file",
        required=True,
        help="Path to the encrypted SMTP secret file to write.",
    )
    args = parser.parse_args()

    secret_file = Path(args.secret_file)
    secret_file.parent.mkdir(parents=True, exist_ok=True)

    first = getpass.getpass("Enter new SMTP auth code: ")
    second = getpass.getpass("Re-enter SMTP auth code: ")
    if first != second:
        raise SystemExit("The two inputs do not match.")
    if not first.strip():
        raise SystemExit("SMTP auth code cannot be empty.")

    secret_file.write_text(protect_text(first), encoding="ascii")
    print(f"Encrypted SMTP secret stored at {secret_file}")


if __name__ == "__main__":
    main()
