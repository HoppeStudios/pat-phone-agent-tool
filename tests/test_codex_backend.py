"""Real stdio protocol tests with a disposable fake server. No network or phones."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "voice-loop"))
from codex_brain import CodexBrain, restricted_config

SERVER = r'''
import json, sys, threading
sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
turn = 0
active = None
history = []
def send(value):
    print(json.dumps(value), flush=True)
def notice(method, params):
    send({"method":method,"params":params})
def done(status="completed", error=None):
    notice("turn/completed", {"threadId":"fake-thread", "turn":{"id":active,"status":status,"error":error}})
for raw in sys.stdin:
    message = json.loads(raw)
    method, params = message.get("method"), message.get("params", {})
    if method in ("initialize", "thread/start"):
        result = {} if method == "initialize" else {"thread":{"id":"fake-thread"},"model":"test-model"}
        send({"id":message["id"],"result":result})
    elif method == "turn/start":
        turn += 1
        active = str(turn)
        text = params["input"][0]["text"]
        send({"id":message["id"],"result":{"turn":{"id":active}}})
        if text == "crash": sys.exit(2)
        if text == "fail":
            done("failed", {"message":"planned failure"})
        elif text in ("wait", "timeout"):
            notice("item/agentMessage/delta", {"threadId":"fake-thread","turnId":active,"itemId":"answer", "delta":"Waiting"})
        else:
            answer = "|".join(history) if text == "history" else text
            history.append(text)
            if text != "fallback":
                notice("item/agentMessage/delta", {"threadId":"fake-thread","turnId":active,"itemId":"answer", "delta":answer})
            notice("item/completed", {"threadId":"fake-thread","turnId":active,"item":{"type":"agentMessage", "id":"answer","text":answer}})
            done()
    elif method == "turn/interrupt":
        send({"id":message["id"],"result":{}})
        done("interrupted")
'''


class Backend(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="pat-protocol-test-")
        self.addCleanup(self.folder.cleanup)
        fake = Path(self.folder.name) / "server.py"
        fake.write_text(SERVER, encoding="utf-8")
        popen = subprocess.Popen
        self.command = None
        self.environment = None
        def launch(args, **kwargs):
            self.command = args
            self.environment = kwargs["env"]
            return popen([sys.executable, "-u", str(fake)], **kwargs)
        self.patch = mock.patch("codex_brain.subprocess.Popen", side_effect=launch)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.brain = CodexBrain(cli=sys.executable, system_prompt="Czech test", timeout=1)
        self.addCleanup(self.brain.close)

    def test_streaming_and_conversation_history(self):
        self.assertEqual("".join(self.brain.ask("Objednávka pizzy")), "Objednávka pizzy")
        self.assertEqual("".join(self.brain.ask("history")), "Objednávka pizzy")

    def test_completed_item_fallback_without_duplicate_stream(self):
        self.assertEqual("".join(self.brain.ask("fallback")), "fallback")
        self.assertEqual("".join(self.brain.ask("normal")), "normal")

    def test_failed_turn_is_reported(self):
        with self.assertRaisesRegex(RuntimeError, "planned failure"):
            list(self.brain.ask("fail"))

    def test_disconnected_server_is_reported(self):
        with self.assertRaisesRegex(RuntimeError, "disconnected"):
            list(self.brain.ask("crash"))

    def test_timeout_interrupts_and_next_turn_still_works(self):
        with self.assertRaises(TimeoutError):
            list(self.brain.ask("timeout"))
        self.assertEqual("".join(self.brain.ask("next")), "next")

    def test_interrupt_keeps_thread_available(self):
        chunks = []
        worker = threading.Thread(target=lambda: chunks.extend(self.brain.ask("wait")))
        worker.start()
        deadline = time.monotonic() + 2
        while not chunks and time.monotonic() < deadline:
            time.sleep(0.01)
        self.brain.interrupt()
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual("".join(self.brain.ask("again")), "again")

    def test_no_api_key_or_claude_environment_forwarded(self):
        self.assertNotIn("OPENAI_API_KEY", self.environment)
        self.assertNotIn("CODEX_API_KEY", self.environment)
        self.assertFalse(any(key.upper().startswith(("CLAUDE", "ANTHROPIC")) for key in self.environment))

    def test_unknown_server_requests_and_permissions_are_refused(self):
        with mock.patch.object(self.brain, "_write") as write:
            self.brain._server_request({"id": 88, "method": "item/commandExecution/requestApproval"})
            self.assertEqual(write.call_args.args[0]["result"]["decision"], "decline")
            self.brain._server_request({"id": 89, "method": "unknown/privilegedAction"})
            self.assertIn("error", write.call_args.args[0])

    def test_inherited_mcp_integrations_are_disabled(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {"CODEX_HOME": home}):
            Path(home, "config.toml").write_text('[mcp_servers.mail]\ncommand="mail-server"\n', encoding="utf-8")
            config = restricted_config()
            self.assertFalse(config["mcp_servers.mail.enabled"])
            self.assertFalse(config["features.shell_tool"])
            self.assertFalse(config["features.apps"])
            self.assertFalse(config["features.hooks"])

    def test_only_explicit_dynamic_tools_are_dispatched(self):
        self.brain.dynamic_tools = [{"name": "get_call"}]
        self.brain.tool_handler = mock.Mock(return_value="ok")
        with mock.patch.object(self.brain, "_write") as write:
            self.brain._server_request({"id": 9, "method": "item/tool/call", "params": {"tool": "send_email"}})
            self.brain.tool_handler.assert_not_called()
            self.assertFalse(write.call_args.args[0]["result"]["success"])


if __name__ == "__main__":
    unittest.main()
