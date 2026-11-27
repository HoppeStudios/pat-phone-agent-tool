"""Own one isolated Asterisk process and the local media rendezvous, without systemd."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess

from sip_relay import Rendezvous
import threading


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    options = parser.parse_args()
    with open(options.config, encoding="utf-8-sig") as stream:
        config = json.load(stream)
    token = bytes.fromhex(config["relay_token"])
    if len(token) != 32:
        raise ValueError("Invalid local relay key.")
    prefix = Path(config["asterisk_prefix"])
    env = {**os.environ, "LD_LIBRARY_PATH": str(prefix / "lib")}
    log = open(config["asterisk_log"], "ab", buffering=0)
    process = subprocess.Popen([str(prefix / "sbin/asterisk"), "-f", "-C", config["asterisk_config"]],
                               stdin=subprocess.DEVNULL, stdout=log, stderr=log, env=env)
    def stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    Path(config["runtime_pid_file"]).write_text(str(os.getpid()), encoding="ascii")
    closing = threading.Event()
    def watch_child():
        process.wait()
        if not closing.is_set():
            os.kill(os.getpid(), signal.SIGTERM)
    try:
        threading.Thread(target=watch_child, daemon=True).start()
        relay = Rendezvous(token)
        threading.Thread(target=relay.listen, args=(18001, False), daemon=True).start()
        relay.listen(config["relay_port"], True)
    except KeyboardInterrupt:
        pass
    finally:
        closing.set()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        log.close()
        Path(config["runtime_pid_file"]).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
