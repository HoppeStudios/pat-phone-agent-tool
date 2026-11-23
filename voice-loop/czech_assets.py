"""Pinned, verified Czech ONNX assets. No remote Python or pickle is loaded."""
import hashlib
import os
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent / "models" / "czech"
ASR_REVISION = "8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce"
PIPER_REVISION = "e5349433ed883a32f893a434dc43a6c66b95ef7c"
FILES = {
    "asr": ("istupakov/parakeet-tdt-0.6b-v3-onnx", ASR_REVISION, (
        ("config.json", "config.json", 97, "git", "02a773005666393de591dfd55230b778da1653d8"),
        ("vocab.txt", "vocab.txt", 93939, "git", "fc43e1c723e262df60b70e1919614417162d1fe2"),
        ("encoder-model.int8.onnx", "encoder-model.int8.onnx", 652183999, "sha256", "6139d2fa7e1b086097b277c7149725edbab89cc7c7ae64b23c741be4055aff09"),
        ("decoder_joint-model.int8.onnx", "decoder_joint-model.int8.onnx", 18202004, "sha256", "eea7483ee3d1a30375daedc8ed83e3960c91b098812127a0d99d1c8977667a70"),
    )),
    "piper": ("rhasspy/piper-voices", PIPER_REVISION, (
        ("cs/cs_CZ/jirka/medium/cs_CZ-jirka-medium.onnx", "cs_CZ-jirka-medium.onnx", 63221984, "sha256", "9bc0b76bb8f26e1d542bf7ed2ce8a6c764605a5f6edcc7663bd637d0b684c5d9"),
        ("cs/cs_CZ/jirka/medium/cs_CZ-jirka-medium.onnx.json", "cs_CZ-jirka-medium.onnx.json", 6154, "git", "8e5fc4651c4ae71bbb1331b8c32f75f59e41b81b"),
    )),
}


def verified(path, size, kind, expected):
    if not path.is_file() or path.stat().st_size != size:
        return False
    digest = hashlib.sha256() if kind == "sha256" else hashlib.sha1()
    if kind == "git":
        digest.update(f"blob {size}\0".encode())
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == expected


def ensure_assets(group, download=True):
    repo, revision, files = FILES[group]
    folder = ROOT / group
    folder.mkdir(parents=True, exist_ok=True)
    for remote, name, size, kind, expected in files:
        path = folder / name
        if verified(path, size, kind, expected):
            continue
        if not download:
            raise RuntimeError(f"Czech speech asset is missing or invalid: {name}. Run prepare-czech.py.")
        print(f"Downloading pinned Czech speech asset: {name} ({size // 1048576} MB)", flush=True)
        temporary = path.with_name(path.name + ".part")
        try:
            request = urllib.request.Request(f"https://huggingface.co/{repo}/resolve/{revision}/{remote}",
                                             headers={"User-Agent": "Pat-Codex-Czech/0.1"})
            received = 0
            with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as stream:
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    received += len(chunk)
                    if received > size:
                        raise RuntimeError(f"Speech asset exceeded its pinned size: {name}")
                    stream.write(chunk)
            if not verified(temporary, size, kind, expected):
                raise RuntimeError(f"Speech asset hash verification failed: {name}")
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    return folder


if __name__ == "__main__":
    for group in FILES:
        print(ensure_assets(group))
