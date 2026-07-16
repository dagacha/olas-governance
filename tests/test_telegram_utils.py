from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from governance import telegram_utils


class TelegramUtilsTests(unittest.TestCase):
    def test_message_chunks_preserve_text_within_limit(self) -> None:
        text = "x" * (telegram_utils.MESSAGE_LIMIT + 1)

        chunks = telegram_utils._message_chunks(text)

        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(len(chunk) <= telegram_utils.MESSAGE_LIMIT for chunk in chunks))

    def test_telegram_error_redacts_token_from_url(self) -> None:
        error = "request failed for https://api.telegram.org/bot123456:secret-token/getUpdates"

        message = telegram_utils.redact_telegram_error(error)

        self.assertIn("https://api.telegram.org/bot<redacted>/getUpdates", message)
        self.assertNotIn("secret-token", message)

    @patch("governance.telegram_utils.requests.post")
    def test_send_message_posts_each_chunk_to_authorized_chat(self, post: Mock) -> None:
        response = Mock(ok=True)
        response.json.return_value = {"ok": True}
        post.return_value = response
        text = "x" * (telegram_utils.MESSAGE_LIMIT + 1)

        telegram_utils.send_telegram_message(text, token="bot-token", chat_id="-10042")

        self.assertEqual(post.call_count, 2)
        for call in post.call_args_list:
            self.assertEqual(call.args[0], "https://api.telegram.org/botbot-token/sendMessage")
            self.assertEqual(call.kwargs["json"]["chat_id"], "-10042")
            self.assertLessEqual(len(call.kwargs["json"]["text"]), telegram_utils.MESSAGE_LIMIT)


if __name__ == "__main__":
    unittest.main()
