#!/usr/bin/env python3
"""Copy the initialized R2 backend state to a unique backup key."""

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-missing", action="store_true",
                        help="Allow a new stack to have no state before its first apply.")
    args = parser.parse_args()
    metadata = Path(os.environ.get("TF_DATA_DIR", ".terraform")) / "terraform.tfstate"
    try:
        backend = json.loads(metadata.read_text())["backend"]
        config = backend["config"]
        endpoint = config["endpoints"]["s3"]
        bucket = config["bucket"]
        key = config["key"]
    except (OSError, ValueError, KeyError, TypeError):
        sys.exit("Cannot read the backend configuration. Run task init first.")

    host = urlsplit(endpoint)
    if (
        backend["type"] != "s3"
        or host.scheme != "https"
        or not (host.hostname or "").endswith(".r2.cloudflarestorage.com")
        or endpoint != f"https://{os.environ.get('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com"
        or bucket != os.environ.get("R2_BUCKET")
        or not isinstance(key, str)
        or not re.fullmatch(r"[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*/terraform\.tfstate", key)
        or key.startswith("backups/")
    ):
        sys.exit("The initialized backend does not match the stack's R2 configuration.")

    workspace = metadata.parent / "environment"
    selected_workspace = os.environ.get("TF_WORKSPACE") or (
        workspace.read_text().strip() if workspace.exists() else "default"
    )
    if selected_workspace != "default":
        sys.exit("State backups require the default OpenTofu workspace.")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stack_prefix = key.removesuffix("/terraform.tfstate")
    destination = f"backups/{stack_prefix}/{stamp}-{uuid.uuid4().hex}.tfstate"
    command = [
        "aws", "s3api", "copy-object",
        "--endpoint-url", endpoint,
        "--region", "auto",
        "--bucket", bucket,
        "--key", destination,
        "--copy-source", quote(f"{bucket}/{key}", safe="/"),
        "--no-cli-pager",
    ]
    try:
        if args.allow_missing:
            check = subprocess.run(
                ["aws", "s3api", "head-object", "--endpoint-url", endpoint,
                 "--region", "auto", "--bucket", bucket, "--key", key,
                 "--no-cli-pager"],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
            )
            if check.returncode:
                if "(404)" in check.stderr:
                    print("No remote state exists yet. Skipping the first backup.")
                    return
                sys.stderr.write(check.stderr)
                sys.exit("Cannot check the remote state. The apply task will stop.")
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
    except FileNotFoundError:
        sys.exit("The AWS CLI is required for R2 state backups.")
    except subprocess.CalledProcessError:
        sys.exit("The R2 state backup failed. The apply task will stop.")
    print(f"State backup: s3://{bucket}/{destination}")


if __name__ == "__main__":
    main()
