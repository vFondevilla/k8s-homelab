#!/usr/bin/env python3
"""Copy the initialized R2 backend state to a unique backup key."""

import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit


def main():
    metadata = Path(__file__).parent / ".terraform" / "terraform.tfstate"
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
        or key != "unifi/terraform.tfstate"
        or not bucket
    ):
        sys.exit("The initialized backend is not the expected UniFi R2 backend.")

    workspace = metadata.parent / "environment"
    if workspace.exists() and workspace.read_text().strip() != "default":
        sys.exit("State backups require the default OpenTofu workspace.")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = f"backups/unifi/{stamp}-{uuid.uuid4().hex}.tfstate"
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
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
    except FileNotFoundError:
        sys.exit("The AWS CLI is required for R2 state backups.")
    except subprocess.CalledProcessError:
        sys.exit("The R2 state backup failed. The apply task will stop.")
    print(f"State backup: s3://{bucket}/{destination}")


if __name__ == "__main__":
    main()
