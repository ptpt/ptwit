import unittest
import os
import tempfile

from ptwit import TwitterConfig


class TestTwitterConfig(unittest.TestCase):
    def setUp(self):
        _, self.filename = tempfile.mkstemp()

    def tearDown(self):
        os.remove(self.filename)

    def test_open(self):
        TwitterConfig("./hello")
        self.assertFalse(os.path.exists("./hello"))

    def test_set(self):
        config = TwitterConfig(self.filename)
        config.set("option", "value")  # Save hello=world to general section
        config.set("name", "tao", account="Tao")
        config.set("name", "mian", account="Mian")
        self.assertEqual(config.config.items("general"), [("option", "value")])
        self.assertEqual(config.config.items("Tao"), [("name", "tao")])
        self.assertEqual(config.config.items("Mian"), [("name", "mian")])

    def test_get(self):
        config = TwitterConfig(self.filename)
        config.set("option", "value")
        config.set("format", "json", account="Tao")
        self.assertEqual(config.get("option"), "value")
        self.assertEqual(config.get("format", account="Tao"), "json")

    def test_unset(self):
        config = TwitterConfig(self.filename)
        config.set("option", "value")
        config.set("format", "json", account="Tao")
        config.unset("format", account="Tao")
        config.unset("option")
        self.assertIsNone(config.get("format", account="Tao"))
        self.assertIsNone(config.get("option"))

    def test_remove_account(self):
        config = TwitterConfig(self.filename)
        config.set("option", "value", account="Tao")
        config.remove_account("Tao")

    def test_list_account(self):
        config = TwitterConfig(self.filename)
        self.assertEqual(config.list_accounts(), [])
        config.set("option", "value")
        config.set("option", "value", account="Tao")
        self.assertEqual(config.list_accounts(), ["Tao"])

    def test_save(self):
        config = TwitterConfig(self.filename)
        config.set("option", "value")
        config.set("name", "Tao", account="Tao")
        config.save()
        with open(self.filename) as fp:
            content = fp.read()
        self.assertTrue(content.find("general"))
        self.assertTrue(content.find("Tao"))
        self.assertTrue(content.find("name"))


if __name__ == "__main__":
    unittest.main()
