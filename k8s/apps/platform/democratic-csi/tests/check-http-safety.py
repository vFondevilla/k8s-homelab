"""Run the HTTP regression test in an existing CSI driver container."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--context", required=True)
parser.add_argument("--pod", required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix="csi-http-test-") as directory:
    key, cert = Path(directory) / "key.pem", Path(directory) / "cert.pem"
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-keyout", str(key), "-out", str(cert), "-days", "1", "-subj", "/CN=localhost",
    ], check=True, capture_output=True)
    code = "globalThis.csiTestTls=" + json.dumps({
        "key": key.read_text(), "cert": cert.read_text(),
    }) + ";\n"
    # Clear NODE_OPTIONS for this test process and load the working-tree patch.
    code += "new Function('require', " + json.dumps(
        (root / "components/http-safety/http-safety.cjs").read_text()
    ) + ")(require);\n"
    code += (root / "tests/http-safety.cjs").read_text()
    subprocess.run([
        "kubectl", "--context", args.context, "-n", "democratic-csi",
        "exec", "-i", args.pod, "-c", "csi-driver", "--",
        "env", "NODE_OPTIONS=", "node",
    ], input=code, text=True, check=True, timeout=45)
