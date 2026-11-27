"""Local-only AudioSocket rendezvous. Authentication never travels to Asterisk.

Run beside Asterisk. Windows connects through WSL's localhost forwarding, so no
Windows inbound TCP firewall exception is needed for call control or PCM audio.
"""
import argparse
import hmac
import json
import select
import socket
import struct
import threading
import time


def exact(peer, size):
    value = bytearray()
    while len(value) < size:
        chunk = peer.recv(size - len(value))
        if not chunk:
            raise EOFError
        value.extend(chunk)
    return bytes(value)


class Rendezvous:
    def __init__(self, token):
        self.token = token
        self.pending = {}
        self.lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(4)

    def accept(self, peer, windows):
        if not self.slots.acquire(blocking=False):
            peer.close()
            return
        joined = False
        transferred = False
        try:
            peer.settimeout(5)
            if windows:
                credential = exact(peer, 32)
                if not hmac.compare_digest(credential, self.token):
                    return
                identity = exact(peer, 16)
            else:
                if exact(peer, 3) != b"\x01\x00\x10":
                    return
                identity = exact(peer, 16)
            with self.lock:
                record = self.pending.setdefault(identity, {"event": threading.Event(), "peers": {}})
                role = "windows" if windows else "asterisk"
                if role in record["peers"]:
                    return
                record["peers"][role] = peer
                joined = True
                if len(record["peers"]) == 2:
                    record["event"].set()
            deadline = time.monotonic() + 100
            while not record["event"].wait(0.2):
                if time.monotonic() >= deadline:
                    return
                readable, _, _ = select.select([peer], [], [], 0)
                if readable and not peer.recv(1, socket.MSG_PEEK):
                    return
            if not windows:
                transferred = True
                return  # The Windows owner's worker forwards both directions.
            remote = record["peers"]["asterisk"]
            peer.sendall(b"\x01\x00\x10" + identity)
            peer.settimeout(None)
            remote.settimeout(None)
            while True:
                readable, _, _ = select.select([peer, remote], [], [], 310)
                if not readable:
                    break
                for source in readable:
                    chunk = source.recv(65536)
                    if not chunk:
                        return
                    (remote if source is peer else peer).sendall(chunk)
        except (OSError, EOFError):
            pass
        finally:
            # The Asterisk worker transfers ownership of its peer to the Windows worker.
            if joined and not transferred:
                with self.lock:
                    record = self.pending.pop(identity, None)
                if record:
                    for owned in record["peers"].values():
                        try:
                            owned.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass
                        owned.close()
            if not transferred:
                peer.close()
            self.slots.release()

    def listen(self, port, windows):
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", port))
        server.listen(4)
        while True:
            peer, _ = server.accept()
            threading.Thread(target=self.accept, args=(peer, windows), daemon=True).start()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    options = parser.parse_args()
    with open(options.config, encoding="utf-8-sig") as stream:
        config = json.load(stream)
    token = bytes.fromhex(config["relay_token"])
    if len(token) != 32:
        raise ValueError("Invalid local relay key.")
    relay = Rendezvous(token)
    threading.Thread(target=relay.listen, args=(18001, False), daemon=True).start()
    relay.listen(config["relay_port"], True)


if __name__ == "__main__":
    main()
