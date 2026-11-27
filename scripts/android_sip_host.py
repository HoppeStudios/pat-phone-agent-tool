"""Phone-only Tailscale SIP and RTP forwarding on Windows.

No microphone, speaker, phone call API or startup configuration is used here.
"""
import argparse
import ipaddress
import json
from pathlib import Path
import select
import socket
import threading


def stream_pair(client, destination):
    remote = None
    try:
        remote = socket.create_connection(destination, timeout=5)
        client.settimeout(None)
        remote.settimeout(None)
        while True:
            readable, _, _ = select.select([client, remote], [], [], 360)
            if not readable:
                break
            for source in readable:
                data = source.recv(65536)
                if not data:
                    return
                (remote if source is client else client).sendall(data)
    except OSError:
        pass
    finally:
        client.close()
        if remote:
            remote.close()


def tcp_forward(listener, port, linux_address, allowed_peer=None):
    slots = threading.BoundedSemaphore(4)
    def handle(peer):
        try:
            stream_pair(peer, (linux_address, port))
        finally:
            slots.release()
    while True:
        peer, address = listener.accept()
        if allowed_peer and address[0] != allowed_peer:
            peer.close()
            continue
        if not slots.acquire(blocking=False):
            peer.close()
            continue
        threading.Thread(target=handle, args=(peer,), daemon=True).start()


def rtp_forward(outside, inside, phone_address):
    target = None
    while True:
        readable, _, _ = select.select([outside, inside], [], [])
        for source in readable:
            if source is outside:
                data, sender = outside.recvfrom(4096)
                if sender[0] != phone_address or len(data) < 8 or data[0] >> 6 != 2:
                    continue
                target = sender
                try:
                    inside.send(data)
                except ConnectionResetError:
                    continue
            else:
                try:
                    data = inside.recv(4096)
                except ConnectionResetError:
                    continue  # No Asterisk RTP socket until a call is active.
                if target:
                    outside.sendto(data, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    options = parser.parse_args()
    with open(options.config, encoding="utf-8-sig") as stream:
        config = json.load(stream)
    tailscale = ipaddress.ip_network("100.64.0.0/10")
    for name in ("pc_tailscale_address", "phone_tailscale_address"):
        if ipaddress.ip_address(config[name]) not in tailscale:
            raise ValueError("Select the two verified Tailscale IPv4 addresses.")
    linux = ipaddress.ip_address(config["linux_address"])
    if linux.version != 4 or not linux.is_private or linux.is_loopback:
        raise ValueError("Select the existing private WSL IPv4 address.")
    listeners = []
    for address in ("127.0.0.1", config["pc_tailscale_address"]):
        listener = socket.socket()
        listener.bind((address, 15060))
        listener.listen(4)
        listeners.append((listener, None if address == "127.0.0.1" else config["phone_tailscale_address"]))
    rtp = []
    for port in range(19000, 19022):
        outside = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        outside.bind((config["pc_tailscale_address"], port))
        inside = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        inside.connect((config["linux_address"], port))
        rtp.append((outside, inside))
    for listener, allowed in listeners:
        threading.Thread(target=tcp_forward, args=(listener, 15060, config["linux_address"], allowed), daemon=True).start()
    for outside, inside in rtp:
        threading.Thread(target=rtp_forward,
                         args=(outside, inside, config["phone_tailscale_address"]),
                         daemon=True).start()
    Path(config["windows_pid_file"]).write_text(str(__import__("os").getpid()), encoding="ascii")
    # Keep no recurring Windows task or Startup entry. The installed launcher owns this process.
    threading.Event().wait()


if __name__ == "__main__":
    main()
