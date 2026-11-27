"""Bounded AudioSocket framing and silent PCM I/O. No microphone or speaker access."""
import queue
import socket
import struct
import threading
import time

import numpy as np


def read_exact(stream, count):
    data = bytearray()
    while len(data) < count:
        piece = stream.recv(count - len(data))
        if not piece:
            raise EOFError("AudioSocket closed.")
        data.extend(piece)
    return bytes(data)


def read_packet(stream):
    kind, length = struct.unpack("!BH", read_exact(stream, 3))
    if length > 4096:
        raise ValueError("AudioSocket packet exceeds the voice client's limit.")
    return kind, read_exact(stream, length)


def packet(kind, payload=b""):
    if len(payload) > 4096:
        raise ValueError("AudioSocket packet is too large.")
    return struct.pack("!BH", kind, len(payload)) + payload


class Resampler:
    """Keep interpolation positions across input blocks, avoiding chunk-length drift."""
    def __init__(self, source_rate, target_rate):
        self.step = source_rate / target_rate
        self.input_count = 0
        self.next_position = 0.0
        self.last = None

    def feed(self, samples):
        samples = np.asarray(samples, dtype=np.float32).reshape(-1)
        if not len(samples):
            return samples
        start = self.input_count
        positions = np.arange(len(samples), dtype=np.float64) + start
        if self.last is not None:
            positions = np.concatenate(([start - 1], positions))
            samples = np.concatenate(([self.last], samples))
        end = positions[-1]
        count = max(0, int(np.floor((end - self.next_position) / self.step + 1e-8)) + 1)
        wanted = self.next_position + np.arange(count) * self.step
        result = np.interp(wanted, positions, samples).astype(np.float32)
        self.next_position += count * self.step
        self.input_count = int(end) + 1
        self.last = float(samples[-1])
        return result


class SipCallerAudio:
    name = "Android SIM through the local SIP bridge"
    rate = 8000
    channels = 1

    def __init__(self):
        self.blocks = queue.Queue(maxsize=100)
        self.closed = False
        self.tap = None

    def deliver(self, payload):
        if len(payload) % 2:
            raise ValueError("Invalid signed PCM frame.")
        block = np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0
        if self.tap:
            self.tap(block)
        try:
            self.blocks.put_nowait(block)
        except queue.Full:
            self.blocks.get_nowait()
            self.blocks.put_nowait(block)

    def drop_waiting(self):
        while True:
            try:
                self.blocks.get_nowait()
            except queue.Empty:
                return

    def frames(self):
        resampler = Resampler(8000, 16000)
        pending = np.zeros(0, dtype=np.float32)
        while not self.closed:
            try:
                block = self.blocks.get(timeout=0.2)
            except queue.Empty:
                block = np.zeros(1600, dtype=np.float32)
            pending = np.concatenate((pending, resampler.feed(block)))
            while len(pending) >= 512:
                yield pending[:512]
                pending = pending[512:]

    def close(self):
        self.closed = True


class SipOutput:
    """Sounddevice-like output into a scoped call, paced to at most one 20ms frame ahead."""
    def __init__(self, line, rate):
        self.line = line
        self.samplerate = rate
        self.resampler = Resampler(rate, 8000)
        self.pending = np.zeros(0, dtype=np.float32)
        self.deadline = 0.0
        self.active = False

    def start(self):
        self.active = True
        self.deadline = time.monotonic()

    def write(self, samples):
        if not self.active:
            raise RuntimeError("SIP voice output is stopped.")
        self.pending = np.concatenate((self.pending, self.resampler.feed(samples)))
        while len(self.pending) >= 160:
            chunk, self.pending = self.pending[:160], self.pending[160:]
            payload = np.rint(np.clip(chunk, -1, 32767 / 32768) * 32768).astype("<i2").tobytes()
            if self.line.ended.wait(max(0.0, self.deadline - time.monotonic())):
                raise EOFError("The SIP call ended.")
            self.line.send_audio(payload)
            self.deadline = max(self.deadline, time.monotonic()) + 0.02
        return False

    def abort(self):
        self.active = False
        self.pending = np.zeros(0, dtype=np.float32)
        self.resampler = Resampler(self.samplerate, 8000)

    def close(self):
        self.abort()


class AmiClient:
    """Only local authenticated AMI. Never log messages containing login credentials."""
    def __init__(self, host, port, username, secret, on_event):
        import ipaddress
        import uuid
        if not ipaddress.ip_address(host).is_loopback:
            raise ValueError("The AMI control endpoint must be loopback.")
        self.stream = socket.create_connection((host, port), timeout=5)
        self.stream.settimeout(None)
        self.file = self.stream.makefile("rb")
        banner = self.file.readline(8193)
        if not banner.startswith(b"Asterisk Call Manager/"):
            self.close()
            raise ValueError("Unexpected AMI server.")
        self.on_event = on_event
        self.pending = {}
        self.lock = threading.Lock()
        self.send_lock = threading.Lock()
        self.closed = threading.Event()
        self.worker = threading.Thread(target=self._read, daemon=True)
        self.worker.start()
        try:
            self.request("Login", Username=username, Secret=secret, Events="on")
        except BaseException:
            self.close()
            raise

    def _read(self):
        try:
            while True:
                fields, size = {}, 0
                while True:
                    raw = self.file.readline(8193)
                    if not raw:
                        raise EOFError("AMI disconnected.")
                    size += len(raw)
                    if len(raw) > 8192 or size > 65536:
                        raise ValueError("AMI message exceeded its limit.")
                    if raw in (b"\r\n", b"\n"):
                        if fields:
                            break
                        continue
                    line = raw.decode("utf-8", "replace").rstrip("\r\n")
                    if ":" in line:
                        key, value = line.split(":", 1)
                        fields[key] = value.lstrip()
                if "Event" in fields:
                    self.on_event(fields)
                else:
                    with self.lock:
                        waiter = self.pending.get(fields.get("ActionID"))
                    if waiter:
                        waiter.put(fields)
        except (OSError, EOFError, ValueError):
            self.closed.set()
            with self.lock:
                for waiter in self.pending.values():
                    waiter.put({"Response": "Error", "Message": "AMI disconnected."})
            self.on_event({"Event": "PatDisconnected"})

    def request(self, action, **fields):
        import uuid
        action_id = uuid.uuid4().hex
        values = {"Action": action, "ActionID": action_id, **fields}
        entries = [(key, item) for key, value in values.items()
                   for item in (value if isinstance(value, (list, tuple)) else [value])]
        if any(any(char in str(value) for char in "\r\n\0") or len(str(value)) > 2048 for _, value in entries):
            raise ValueError("Invalid AMI field.")
        waiter = queue.Queue()
        with self.lock:
            self.pending[action_id] = waiter
        try:
            wire = "\r\n".join(f"{key}: {value}" for key, value in entries) + "\r\n\r\n"
            with self.send_lock:
                self.stream.sendall(wire.encode("utf-8"))
            reply = waiter.get(timeout=10)
            if reply.get("Response") != "Success":
                raise RuntimeError("Local SIP control request failed.")
            return reply
        finally:
            with self.lock:
                self.pending.pop(action_id, None)

    def close(self):
        if getattr(self, "stream", None):
            try:
                self.stream.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.stream.close()
        if getattr(self, "file", None):
            self.file.close()
