"""Outgoing Android SIM provider through an authenticated, local Asterisk instance.

No incoming answering or laptop/phone takeover is exposed by this provider.
Constructing it and checking readiness never originates a telephone call.
"""
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import queue
import re
import socket
import subprocess
import threading
import time
import uuid

from sip_audio import AmiClient, SipCallerAudio, SipOutput, packet, read_packet

RECEIVER = "io.github.sparkcyf.voicesipagent/io.github.sparkcyf.voicesipagent.app.AdbControlReceiver"


@dataclass(frozen=True)
class SipConfig:
    ami_port: int
    relay_port: int
    ami_user: str = field(repr=False)
    ami_secret: str = field(repr=False)
    relay_token: bytes = field(repr=False)
    adb: str = field(repr=False)
    phone_serial: str = field(repr=False)
    phone_slot: int = 0
    outbound_enabled: bool = False

    @classmethod
    def load(cls, filename):
        if not filename or not Path(filename).is_absolute():
            raise ValueError("An absolute private Android SIP configuration path is required.")
        with open(filename, encoding="utf-8-sig") as stream:
            value = json.load(stream)
        token = bytes.fromhex(value["relay_token"])
        if len(token) != 32:
            raise ValueError("Invalid SIP relay token.")
        for name in ("ami_port", "relay_port"):
            if not isinstance(value[name], int) or not 1024 <= value[name] <= 65535:
                raise ValueError("Invalid local SIP control port.")
        if not re.fullmatch(r"[A-Za-z0-9._:-]+", value["phone_serial"]):
            raise ValueError("Invalid selected Android transport.")
        if value.get("phone_slot", 0) not in (0, 1):
            raise ValueError("Select SIM slot zero or one explicitly.")
        if not os.path.isfile(value["adb"]):
            raise ValueError("The configured ADB installation is unavailable.")
        return cls(value["ami_port"], value["relay_port"], value["ami_user"], value["ami_secret"],
                   token, value["adb"], value["phone_serial"], value.get("phone_slot", 0),
                   value.get("outbound_enabled") is True)


class AndroidSetupControl:
    def __init__(self, config):
        self.config = config

    def command(self, operation, *arguments):
        done = subprocess.run([self.config.adb, "-s", self.config.phone_serial, "shell", "am", "broadcast",
                               "-n", RECEIVER, "--es", "op", operation, *map(str, arguments)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if done.returncode or "Broadcast completed: result=1," not in done.stdout:
            raise RuntimeError("The selected Android gateway did not acknowledge its control request.")
        return done.stdout

    def status(self):
        return self.command("status")

class SipLine:
    supports_handover = False

    def __init__(self, config, log_path=None):
        self.config = config
        self.log_path = log_path
        self.ready = threading.Event()
        self.ended = threading.Event()
        self.ringing = threading.Event()
        self.events = queue.Queue()
        self.started = []
        self.audio = None
        self.in_call = False
        self.ami = None
        self.media = None
        self.media_lock = threading.Lock()
        self.caller = SipCallerAudio()
        self.session_id = uuid.uuid4()
        self.unique_id = "pat-" + self.session_id.hex
        self.channel = None
        self.dial_started = False
        self.closed = False

    def check(self):
        if not self.wait_ready():
            return self.started or ["The local SIP controller is unavailable."]
        return []

    def wait_ready(self, seconds=60, require_phone=True):
        if self.ready.is_set():
            return True
        try:
            self.ami = AmiClient("127.0.0.1", self.config.ami_port, self.config.ami_user,
                                 self.config.ami_secret, self._event)
            state = self.ami.request("ExtensionState", Exten="android", Context="pat-status") if require_phone else {"Status": "0"}
            if state.get("Status") != "0":
                self.ami.close()
                self.ami = None
                self.started.append("The selected Android SIP endpoint is not registered and idle.")
                return False
            self.ready.set()
            return True
        except (OSError, RuntimeError, ValueError, queue.Empty):
            self.started.append("The authenticated local SIP controller could not be reached.")
            return False

    def taken_by_another_app(self):
        return False

    def _event(self, event):
        if event.get("Event") == "PatDisconnected":
            self._ended()
            return
        if event.get("Uniqueid") != self.unique_id:
            return
        if event.get("Channel"):
            self.channel = event["Channel"]
        kind = event.get("Event")
        if kind == "Newstate":
            state = event.get("ChannelStateDesc")
            if state in ("Ring", "Ringing"):
                self.events.put(("Dialing", "", "Outgoing"))
        elif kind == "Hangup":
            self._ended()

    def _ended(self):
        self.in_call = False
        self.ended.set()
        self.caller.close()
        self.events.put(("Ended", "", ""))

    def _open_media(self):
        self.media = socket.create_connection(("127.0.0.1", self.config.relay_port), timeout=5)
        self.media.sendall(self.config.relay_token + self.session_id.bytes)
        self.media.settimeout(100)
        threading.Thread(target=self._read_media, daemon=True).start()

    def _read_media(self):
        try:
            kind, payload = read_packet(self.media)
            if kind != 1 or payload != self.session_id.bytes:
                raise ValueError("SIP audio session did not match this call.")
            self.media.settimeout(None)
            self.audio = "LocalDevice"
            self.in_call = True
            self.events.put(("Talking", "", "Outgoing"))
            while not self.ended.is_set():
                kind, payload = read_packet(self.media)
                if kind == 0:
                    break
                if kind == 0x10:
                    self.caller.deliver(payload)
                elif kind != 3:
                    raise ValueError("Unsupported SIP audio frame.")
        except (OSError, EOFError, ValueError):
            pass
        finally:
            self._ended()

    def _originate(self, channel, variables=None):
        if not self.ready.is_set() or self.dial_started:
            raise RuntimeError("A fresh, authenticated SIP session is required.")
        self.dial_started = True
        self._open_media()
        self.ami.request("Originate", Channel=channel, ChannelId=self.unique_id, Async="true",
                         Application="AudioSocket", Data=f"{self.session_id},127.0.0.1:18001",
                         Variable=["TIMEOUT(absolute)=300", *(variables or [])], Timeout="90000")

    def dial(self, number):
        if not re.fullmatch(r"\+[1-9][0-9]{7,14}", number):
            raise ValueError("The SIP provider requires a full international phone number.")
        if not self.config.outbound_enabled:
            raise RuntimeError("Android SIP outgoing calls are disabled pending the owner's explicit test-call request.")
        # The gateway refuses calls without an explicit SIM header. Do not change that default.
        self._originate(f"PJSIP/{number}@pat-android",
                        [f"PJSIP_HEADER(add,X-VSA-SIMSLOT)={self.config.phone_slot}"])

    def dial_local_echo(self):
        """Only a hard-coded local fixture. Never changes phone guards or uses PJSIP."""
        self._originate("Local/echo@pat-local-test/n")

    def send_audio(self, payload):
        if self.audio != "LocalDevice" or self.ended.is_set() or self.media is None:
            raise EOFError("No scoped SIP audio session is connected.")
        with self.media_lock:
            self.media.sendall(packet(0x10, payload))

    def output(self, rate):
        return SipOutput(self, rate)

    def wait_for(self, statuses, seconds=None):
        deadline = time.monotonic() + seconds if seconds else None
        while True:
            remaining = deadline - time.monotonic() if deadline else None
            if remaining is not None and remaining <= 0:
                return None
            try:
                state, who, _ = self.events.get(timeout=remaining)
            except queue.Empty:
                return None
            if state in statuses or state in ("Ended", "Closed"):
                return state, who

    def wait_for_laptop_audio(self, seconds):
        return self.audio == "LocalDevice" and not self.ended.is_set()

    def answer(self):
        raise RuntimeError("Incoming Android SIP answering is disabled.")

    def to_phone(self):
        raise RuntimeError("The Android SIP provider does not support call handover.")

    def to_laptop(self):
        if self.audio != "LocalDevice":
            raise RuntimeError("The SIP audio session is not connected.")

    def hang_up(self):
        # Media EOF terminates only the AudioSocket leg owned by this session.
        if self.media:
            try:
                self.media.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.media.close()
            self.media = None
        if self.ami and self.dial_started:
            try:
                self.ami.request("Hangup", Channel=self.channel or self.unique_id)
            except (OSError, RuntimeError, queue.Empty):
                # The media EOF and server absolute timeout remain independent cleanup paths.
                pass
        self._ended()

    def close(self):
        if self.closed:
            return
        try:
            self.hang_up()
        finally:
            if self.ami:
                self.ami.close()
            self.closed = True
