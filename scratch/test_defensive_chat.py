import sys
import unittest
import unicodedata

# Import the helper functions directly from the draft file
sys.path.insert(0, '/Users/carlosrivas/Dev/kenbun-agent/scratch')
from draft_input_sanitizer import sanitize_input, prune_dialog_history

class TestDefensiveChat(unittest.TestCase):

    def test_input_sanitizer_normal_text(self):
        # Normal alphanumeric text, emojis, and foreign characters should be preserved.
        text = "Hello, World! 🌸 Kenbun 日本語 123"
        self.assertEqual(sanitize_input(text), text)

    def test_input_sanitizer_control_sequences(self):
        # Raw C0 control sequences like NUL, BS, BEL, ESC (except tab, CR, LF) should be stripped.
        # ESC code: \x1b, BEL code: \x07
        text = "Hello\x00\x07World\x1b[31m!"
        # Strips NUL, BEL, and the ANSI escape sequence \x1b[31m
        expected = "HelloWorld!"
        self.assertEqual(sanitize_input(text), expected)

    def test_input_sanitizer_whitespace_preservation(self):
        # Tabs and newlines should be preserved.
        text = "Line 1\nLine 2\tTabbed"
        self.assertEqual(sanitize_input(text), text)

    def test_input_sanitizer_invisible_characters(self):
        # Invisible format characters (Cf) like zero-width spaces (\u200b), 
        # zero-width joiners (\u200d), bidi overrides (\u200e, \u200f) should be stripped.
        text = "Zero\u200bWidth\u200dJoiner\u200eDirection"
        expected = "ZeroWidthJoinerDirection"
        self.assertEqual(sanitize_input(text), expected)

    def test_history_pruning_by_turns(self):
        # System prompt + 22 messages (11 user-assistant turns)
        history = [{"role": "system", "content": "system"}]
        for i in range(11):
            history.append({"role": "user", "content": f"user {i}"})
            history.append({"role": "assistant", "content": f"assistant {i}"})
        
        # Max turns is 20 (system prompt + 19 messages)
        # So we should prune the oldest turns (matching pairs)
        # If len(history) is 23, and max_turns is 20:
        # Pruning 1 pair (2 messages) reduces length to 21. Still > 20.
        # Pruning another pair (2 messages) reduces length to 19. <= 20.
        # Total turns left should be 9 turns (18 messages) + 1 system prompt = 19 messages.
        pruned = prune_dialog_history(list(history), max_turns=20)
        self.assertEqual(len(pruned), 19)
        self.assertEqual(pruned[0]["role"], "system")
        self.assertEqual(pruned[1]["role"], "user")
        self.assertEqual(pruned[1]["content"], "user 2")
        self.assertEqual(pruned[2]["role"], "assistant")
        self.assertEqual(pruned[2]["content"], "assistant 2")

    def test_history_pruning_by_characters(self):
        # Create a history where total characters exceed max_chars
        # System prompt + 5 turns of very long messages
        history = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "A" * 10000},
            {"role": "assistant", "content": "B" * 10000},
            {"role": "user", "content": "C" * 10000},
            {"role": "assistant", "content": "D" * 10000},
            {"role": "user", "content": "E" * 5000},
        ]
        # Total length of contents is: 6 + 10000 + 10000 + 10000 + 10000 + 5000 = 45006 characters.
        # With max_chars = 32000:
        # Pruning oldest turn (A & B) -> total length drops to 6 + 10000 + 10000 + 5000 = 25006.
        # 25006 is <= 32000, so it should stop there.
        pruned = prune_dialog_history(list(history), max_chars=32000)
        self.assertEqual(len(pruned), 4) # system, user C, assistant D, user E
        self.assertEqual(pruned[0]["role"], "system")
        self.assertEqual(pruned[1]["content"], "C" * 10000)
        self.assertEqual(pruned[2]["content"], "D" * 10000)
        self.assertEqual(pruned[3]["content"], "E" * 5000)

if __name__ == '__main__':
    unittest.main()
