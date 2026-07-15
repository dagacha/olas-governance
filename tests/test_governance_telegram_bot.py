from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from governance import governance_telegram_bot as bot


class GovernanceTelegramBotTests(unittest.TestCase):
    def test_chat_authorization_requires_exact_chat_id(self) -> None:
        message = {"chat": {"id": -10042}}

        self.assertTrue(bot.chat_matches(message, "-10042"))
        self.assertFalse(bot.chat_matches(message, "-10043"))
        self.assertFalse(bot.chat_matches({}, "-10042"))

    def test_offset_round_trip_and_invalid_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            offset_file = Path(temp_dir) / "offset"
            with patch.object(bot, "OFFSET_FILE", offset_file), patch.object(bot, "STATE_DIR", offset_file.parent):
                bot.save_offset(123)
                self.assertEqual(bot.load_offset(), 123)
                offset_file.write_text("not-an-offset\n", encoding="utf-8")
                self.assertEqual(bot.load_offset(), 0)

    def test_command_parser_accepts_bot_mentions_only(self) -> None:
        self.assertEqual(bot.command_text({"text": " /governance "}), "/governance")
        self.assertTrue(bot.COMMAND_RE.match("/governance@olas_bot status"))
        self.assertFalse(bot.COMMAND_RE.match("/governance-extra"))


if __name__ == "__main__":
    unittest.main()
