"""Fetch nine hash-pinned upstream files into /tmp and build a small CLI.

Upstream source and license are preserved byte-for-byte; none is vendored in
the repository. Hash mismatches fail before compilation.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import urllib.request

HERE = Path(__file__).resolve().parent


def build(cache=Path("/tmp/neural_bem_algoim")):
    manifest = json.loads((HERE / "upstream.json").read_text())
    for item in manifest["headers"]:
        path = cache / item["path"]
        if not path.exists():
            url = f"https://raw.githubusercontent.com/algoim/algoim/{manifest['commit']}/{item['path']}"
            content = urllib.request.urlopen(url, timeout=30).read()
            if hashlib.sha256(content).hexdigest() != item["sha256"]:
                raise ValueError(f"Upstream hash mismatch: {item['path']}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Cached hash mismatch: {path}")
    executable = cache / "neural_quadrature"
    subprocess.run(["g++", "-O3", "-std=c++17", "-I", str(cache), str(HERE / "quadrature.cpp"), "-o", str(executable)], check=True)
    return executable


if __name__ == "__main__":
    print(build())
