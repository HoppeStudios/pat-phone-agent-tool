"""Protocol and safety regressions. No phones, real calls or audio devices."""
import importlib.util
from pathlib import Path
import socket
import struct
import sys
import threading
import time
import unittest
from unittest import mock
import uuid
from types import SimpleNamespace

import numpy as np

from sip_audio import AmiClient, Resampler, packet, read_packet
from sip_provider import SipConfig, SipLine


def config(enabled=False):
    return SipConfig(15038, 18002, "fixture", "not-a-real-secret", b"a" * 32,
                     sys.executable, "USB_FIXTURE", 0, enabled)


class AudioProtocol(unittest.TestCase):
    def test_fragmented_packet_and_eof(self):
        reader, writer = socket.socketpair()
        self.addCleanup(reader.close)
        self.addCleanup(writer.close)
        value = packet(0x10, b"\0\1" * 40)
        def send():
            for piece in (value[:1], value[1:4], value[4:]):
                writer.sendall(piece)
        worker = threading.Thread(target=send)
        worker.start()
        self.assertEqual(read_packet(reader), (0x10, b"\0\1" * 40))
        worker.join(1)
        writer.shutdown(socket.SHUT_WR)
        with self.assertRaises(EOFError):
            read_packet(reader)

    def test_oversized_packet_rejected_before_payload_read(self):
        reader, writer = socket.socketpair()
        self.addCleanup(reader.close)
        self.addCleanup(writer.close)
        writer.sendall(struct.pack("!BH", 0x10, 65535))
        with self.assertRaises(ValueError):
            read_packet(reader)
        with self.assertRaises(ValueError):
            packet(0x10, b"x" * 4097)

    def test_streaming_resample_matches_one_block_without_chunk_drift(self):
        samples = np.sin(np.arange(10000) * .031).astype(np.float32)
        complete = Resampler(22050, 8000).feed(samples)
        stream = Resampler(22050, 8000)
        split = np.concatenate([stream.feed(samples[n:n+137]) for n in range(0, len(samples), 137)])
        self.assertEqual(len(complete), len(split))
        np.testing.assert_allclose(complete, split, atol=1e-6)


class CallSafety(unittest.TestCase):
    def test_note_network_transport_does_not_offer_bluetooth_pairing(self):
        import note
        late = note.LateDesk(None)
        late.desk = SimpleNamespace(line=note.OutgoingOnlyLine())
        factory = mock.Mock()
        late.start_pairing(factory)
        factory.assert_not_called()
        self.assertIn("Tailscale", late.notice)

    def test_media_eof_still_hangs_up_only_the_owned_channel(self):
        line = SipLine(config())
        line.ami = mock.Mock()
        line.dial_started = True
        line.channel = "PJSIP/fixture-owned"
        line._ended()
        line.close()
        line.ami.request.assert_called_once_with("Hangup", Channel="PJSIP/fixture-owned")

    def test_mcp_refuses_disabled_transport_before_starting_a_worker(self):
        import phone_mcp
        profile = SimpleNamespace(values={"phone_transport": "android-sip", "android_sip_config": "fixture.json"})
        with mock.patch.object(phone_mcp, "setup_refusal", return_value=None), \
                mock.patch.object(phone_mcp, "UserProfile", return_value=profile), \
                mock.patch("sip_provider.SipConfig.load", return_value=config()), \
                mock.patch.object(phone_mcp.subprocess, "Popen") as process:
            reply = phone_mcp.start_call("+14155550101", {"goal": "fixture"}, 1)
        self.assertEqual(reply["status"], "refused")
        process.assert_not_called()

    def test_sip_check_skips_windows_audio_defaults_and_models(self):
        import pat
        profile = SimpleNamespace(values={"phone_transport": "android-sip", "android_sip_config": "fixture.json"})
        line = mock.Mock(config=config())
        line.check.return_value = []
        with mock.patch.object(pat, "UserProfile", return_value=profile), \
                mock.patch("sip_provider.SipConfig.load", return_value=config()), \
                mock.patch("sip_provider.SipLine", return_value=line), \
                mock.patch.object(pat, "only_one_copy"), mock.patch.object(pat, "CallDevices") as devices, \
                mock.patch.object(pat, "check_audio_setup") as audio, \
                mock.patch.object(pat, "load_speech") as speech, \
                mock.patch.object(sys, "argv", ["pat.py", "check"]):
            pat.main()
        devices.return_value.restore.assert_not_called()
        audio.assert_not_called()
        speech.assert_not_called()
        line.close.assert_called_once_with()

    def test_disabled_call_does_not_reach_ami_or_adb(self):
        line = SipLine(config())
        with mock.patch.object(line, "_originate") as originate, mock.patch("subprocess.run") as run:
            with self.assertRaisesRegex(RuntimeError, "disabled"):
                line.dial("+14155550101")
        originate.assert_not_called()
        run.assert_not_called()
        line.close()

    def test_call_selects_sim_in_its_own_invite_without_changing_phone_defaults(self):
        line = SipLine(config(True))
        with mock.patch.object(line, "_originate") as originate, mock.patch("subprocess.run") as run:
            line.dial("+14155550101")
        originate.assert_called_once_with("PJSIP/+14155550101@pat-android", ["PJSIP_HEADER(add,X-VSA-SIMSLOT)=0"])
        run.assert_not_called()
        line.close()

    def test_dial_validation_blocks_short_codes_ussd_and_protocol_injection(self):
        line = SipLine(config(True))
        with mock.patch.object(line, "_originate") as originate:
            for value in ("112", "*100#", "+14155550101\r\nAction: Originate", "contact", "+１２３４５６７８９"):
                with self.assertRaises(ValueError, msg=value):
                    line.dial(value)
        originate.assert_not_called()
        line.close()

    def test_other_call_events_cannot_end_this_call(self):
        line = SipLine(config())
        line._event({"Event": "Hangup", "Uniqueid": "another-call"})
        self.assertFalse(line.ended.is_set())
        line._event({"Event": "Hangup", "Uniqueid": line.unique_id})
        self.assertTrue(line.ended.is_set())
        line.close()

    def test_wrong_media_identity_never_delivers_audio(self):
        line = SipLine(config())
        reader, writer = socket.socketpair()
        self.addCleanup(writer.close)
        line.media = reader
        writer.sendall(packet(1, uuid.uuid4().bytes))
        line._read_media()
        self.assertIsNone(line.audio)
        self.assertTrue(line.caller.blocks.empty())
        self.assertTrue(line.ended.is_set())
        line.close()


class FakeAmi:
    def __init__(self):
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(1)
        self.port = self.server.getsockname()[1]
        self.messages = []
        self.done = threading.Event()
        self.worker = threading.Thread(target=self.run, daemon=True)
        self.worker.start()

    def run(self):
        try:
            peer, _ = self.server.accept()
            with peer, peer.makefile("rb") as stream:
                peer.sendall(b"Asterisk Call Manager/9.0\r\n")
                while True:
                    lines = []
                    while True:
                        line = stream.readline()
                        if not line:
                            return
                        if line == b"\r\n":
                            break
                        lines.append(line.decode().rstrip("\r\n"))
                    self.messages.append(lines)
                    action = next(x.split(": ", 1)[1] for x in lines if x.startswith("ActionID: "))
                    peer.sendall(f"Response: Success\r\nActionID: {action}\r\n\r\n".encode())
        except OSError:
            pass
        finally:
            self.server.close()
            self.done.set()


class AmiSafety(unittest.TestCase):
    def test_repeated_variables_are_separate_headers_and_crlf_is_rejected(self):
        fixture = FakeAmi()
        client = AmiClient("127.0.0.1", fixture.port, "fixture", "placeholder", lambda _: None)
        try:
            variables = ["TIMEOUT(absolute)=300", "PJSIP_HEADER(add,X-VSA-SIMSLOT)=0"]
            client.request("Originate", Channel="Local/echo@pat-local-test/n", Variable=variables)
            self.assertEqual([line for line in fixture.messages[-1] if line.startswith("Variable: ")],
                             ["Variable: " + value for value in variables])
            before = len(fixture.messages)
            with self.assertRaises(ValueError):
                client.request("Ping", Extra="value\r\nAction: Originate")
            self.assertEqual(len(fixture.messages), before)
        finally:
            client.close()
        self.assertTrue(fixture.done.wait(2))

    def test_ami_credentials_never_go_to_a_remote_host(self):
        with mock.patch("socket.create_connection") as connect:
            with self.assertRaises(ValueError):
                AmiClient("192.0.2.1", 15038, "fixture", "placeholder", lambda _: None)
        connect.assert_not_called()


class RelaySafety(unittest.TestCase):
    def test_bad_authentication_cannot_claim_a_media_session(self):
        path = Path(__file__).resolve().parents[1] / "scripts" / "sip_relay.py"
        spec = importlib.util.spec_from_file_location("pat_test_sip_relay", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        relay = module.Rendezvous(b"a" * 32)
        server, client = socket.socketpair()
        worker = threading.Thread(target=relay.accept, args=(server, True), daemon=True)
        worker.start()
        client.sendall(b"b" * 32 + uuid.uuid4().bytes)
        client.settimeout(2)
        try:
            result = client.recv(1)
        except ConnectionResetError:
            result = b""  # Windows resets a peer closed with unread bytes.
        self.assertEqual(result, b"")
        worker.join(2)
        client.close()
        self.assertEqual(relay.pending, {})

    def test_closed_owner_releases_an_unpaired_session_promptly(self):
        path = Path(__file__).resolve().parents[1] / "scripts" / "sip_relay.py"
        spec = importlib.util.spec_from_file_location("pat_test_sip_relay_cleanup", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        relay = module.Rendezvous(b"a" * 32)
        server, client = socket.socketpair()
        worker = threading.Thread(target=relay.accept, args=(server, True), daemon=True)
        worker.start()
        client.sendall(b"a" * 32 + uuid.uuid4().bytes)
        deadline = time.monotonic() + 1
        while not relay.pending and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(relay.pending)
        client.close()
        worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(relay.pending, {})


if __name__ == "__main__":
    unittest.main()
