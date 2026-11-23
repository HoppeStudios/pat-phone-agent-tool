"""Czech call coverage without starting audio, a model or a phone."""
import datetime
import inspect
import tempfile
import unittest
from unittest import mock

import pat
import phone_mcp
from call_brief import CallBrief, is_bare_answer
from languages import guess_language, written_in
from note_settings import NoteSettings
from real_dates import real_dates
from voice_loop import SYSTEM_PROMPTS


class Czech(unittest.TestCase):
    def test_assistant_name_does_not_become_the_human_owner(self):
        phrase = pat.call_opening("dial", "cs", "PRIVATE_OWNER", "PRIVATE_OWNER", "codex assistant")
        self.assertIn("jsem codex assistant", phrase)
        self.assertIn("umělou inteligencí", phrase)
        self.assertIn("může hovor poslouchat", phrase)
        self.assertNotIn("PRIVATE_OWNER", phrase)
        self.assertEqual(pat.call_opening("dial", "en", "Alex", "Alex"),
                         pat.OPENINGS["dial"]["en"].format(owner="Alex", owner_ru="Alex"))

    def test_bargein_interrupts_codex_generation(self):
        from tests.test_supervision import FakeBrain, conversation
        brain = FakeBrain()
        brain.interrupt = mock.Mock()
        call, _ = conversation(brain, language="cs")
        call.generating = True
        call._cut_speech()
        brain.interrupt.assert_called_once_with()
        self.assertEqual(call.mouth.cancels, 1)

    def test_czech_brief_preserves_identity_gate_and_task_privacy(self):
        brief = CallBrief.from_dict({"goal": "SECRET_PIZZA", "company": "Pizzerie", "confidence": "confirmed", "language": "cs"})
        prompt = brief.haiku_prompt(SYSTEM_PROMPTS["cs"], "opening", "Jan", "nonce")
        self.assertNotIn("SECRET_PIZZA", prompt)
        self.assertIn("SECRET_PIZZA", brief.task_message("Jan"))
        self.assertIn("Pizzerie", brief.check_question())
        self.assertIn("v pátek", brief.spoken_date_table())

    def test_czech_disclosure_and_all_fixed_call_phrases_exist(self):
        self.assertIn("umělou inteligencí", pat.OPENINGS["dial"]["cs"])
        for phrases in (pat.TAKING_OVER, pat.NOBODY_CAME, pat.ENDING, pat.WARM_UP, pat.STALLS):
            self.assertTrue(phrases["cs"])
        self.assertTrue(pat.ENDING_REASONS["time limit"]["cs"])

    def test_czech_saved_voice_is_not_english(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = NoteSettings(folder)
            self.assertEqual(settings.voice_for("cs"), "jirka")
            settings.change("language", "cs")
            self.assertEqual(NoteSettings(folder).language, "cs")

    def test_local_czech_speech_selects_multilingual_recognizer_and_czech_piper(self):
        with mock.patch("speech_service.available", return_value=None), mock.patch.object(pat, "BatchEar") as ear, \
                mock.patch.object(pat, "PiperVoice") as voice, mock.patch.object(pat, "TrackingMouth"), \
                mock.patch.object(pat, "PocketVoice") as english:
            pat.load_speech("cs", None)
            ear.assert_called_once_with("nemo-parakeet-tdt-0.6b-v3", mic=False)
            voice.assert_called_once_with("jirka")
            english.assert_not_called()

    def test_resident_czech_speech_uses_czech_voice(self):
        with mock.patch("speech_service.available", return_value={"ready": True}), \
                mock.patch("speech_service.RemoteEar") as ear, mock.patch("speech_service.RemoteVoice") as voice, \
                mock.patch.object(pat, "TrackingMouth"):
            pat.load_speech("cs", None)
            ear.assert_called_once_with({"ready": True}, "cs")
            voice.assert_called_once_with({"ready": True}, "cs", "jirka")

    def test_czech_answers_names_and_schema(self):
        self.assertTrue(is_bare_answer("Ano"))
        self.assertTrue(is_bare_answer("Jasně"))
        self.assertTrue(written_in("Jiří Šťastný", "cs"))
        self.assertEqual(guess_language("Jiří Šťastný", "cs"), "cs")
        self.assertIn("cs", str(inspect.signature(phone_mcp.place_call).parameters["language"].annotation))

    def test_relative_czech_dates_are_saved_as_calendar_dates(self):
        result = real_dates("zítra a pozítří, včera a předevčírem, dnes", today=datetime.date(2026, 11, 23))
        self.assertNotIn("zítra", result)
        self.assertNotIn("včera", result)


if __name__ == "__main__":
    unittest.main()
