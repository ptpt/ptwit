import unittest
import os
import tempfile
from shutil import rmtree
from datetime import datetime

from ptwit import ptwit
from ptwit.ptwit import Config, lookup, render_template
from ptwit.config import TwitterConfig


class TestTwitterConfig(unittest.TestCase):
    def setUp(self):
        _, self.filename = tempfile.mkstemp()

    def tearDown(self):
        os.remove(self.filename)

    def test_open(self):
        filename = tempfile.mktemp()
        # create if config file does not exist
        config = TwitterConfig(filename)
        self.assertTrue(os.path.isfile(filename))
        os.remove(filename)
        # if the path is a directory?
        dirname = tempfile.mkdtemp()
        self.assertRaises(IOError, TwitterConfig, dirname)
        os.removedirs(dirname)

    def test_set(self):
        config = TwitterConfig(self.filename)
        config.set('option', 'value')  # save hello=world to general section
        config.set('name', 'tao', account='Tao')
        config.set('name', 'mian', account='Mian')
        self.assertEqual(config.config.items('general'), [('option', 'value')])
        self.assertEqual(config.config.items('Tao'), [('name', 'tao')])
        self.assertEqual(config.config.items('Mian'), [('name', 'mian')])

    def test_get(self):
        config = TwitterConfig(self.filename)
        config.set('option', 'value')
        config.set('format', 'json', account='Tao')
        self.assertEqual(config.get('option'), 'value')
        self.assertEqual(config.get('format', account='Tao'), 'json')

    def test_unset(self):
        config = TwitterConfig(self.filename)
        config.set('option', 'value')
        config.set('format', 'json', account='Tao')
        config.unset('format', account='Tao')
        config.unset('option')
        self.assertIsNone(config.get('format', account='Tao'))
        self.assertIsNone(config.get('option'))

    def test_remove_account(self):
        config = TwitterConfig(self.filename)
        config.set('option', 'value', account='Tao')
        config.remove_account('Tao')

    def test_list_account(self):
        config = TwitterConfig(self.filename)
        self.assertEqual(config.list_accounts(), [])
        config.set('option', 'value')
        config.set('option', 'value', account='Tao')
        self.assertEqual(config.list_accounts(), ['Tao'])

    def test_save(self):
        config = TwitterConfig(self.filename)
        config.set('option', 'value')
        config.set('name', 'Tao', account='Tao')
        config.save()
        with open(self.filename) as fp:
            content = fp.read()
        self.assertTrue(content.find('general'))
        self.assertTrue(content.find('Tao'))
        self.assertTrue(content.find('name'))


class TestTemplate(unittest.TestCase):
    def test_lookup(self):
        profile = {
            'user': {'name': 'pt', 'age': 24},
            'status': 'hello world',
            'web.site': 'google.com'}
        self.assertEqual(lookup('user.name', profile), 'pt')
        self.assertEqual(lookup('user.age', profile), 24)
        self.assertEqual(lookup('status', profile), 'hello world')
        self.assertIsNone(lookup('test', profile))
        self.assertIsNone(lookup('user.test', profile))
        self.assertEqual(lookup('user', profile), {'name': 'pt', 'age': 24})
        self.assertIsNone(lookup('.name', profile))
        self.assertIsNone(lookup('status.name', profile))
        self.assertEqual(lookup('web.site', profile), 'google.com')

    def test_render_template(self):
        profile = {'user': {'name': 'pt',
                            'age': 12},
                   'status': 'good',
                   'web.site': 'taopeng.me',
                   'y': 'not year'}
        self.assertEqual(render_template('%user%', profile), "{'age': 12, 'name': 'pt'}")
        self.assertEqual(render_template('%user.name% is good', profile), 'pt is good')
        self.assertEqual(render_template('%y%', profile), 'not year')
        self.assertEqual(render_template('%%', profile), '%')
        now = datetime.utcnow()
        self.assertEqual(render_template('%y%', profile, now), now.strftime('%y'))


class TestConfig(unittest.TestCase):
    def setUp(self):
        Config.config_root = os.path.join(os.path.dirname(__file__),
                                            'tmp_profile_dir')

    def test_global(self):
        # always return the same global profile
        self.assertTrue(Config.get_global() is Config.get_global())

    def test_directory(self):
        profile = Config('ptpt')
        self.assertTrue(os.path.isdir(Config.config_root))
        self.assertFalse(os.path.isfile(os.path.join(Config.config_root, 'global.conf')))
        self.assertFalse(os.path.isfile(profile.config_path))

    def test_set(self):
        profile = Config('ptpt')
        profile.set('hello', 'world', True)
        profile.save()
        with open(profile.config_path) as f:
            buf = f.read()
            self.assertEqual(buf, '''[hello]
world = True

''')
        global_profile = Config()
        global_profile.set('global', 'hello', 12)
        global_profile.set('hello', 'world', 13)
        global_profile.save(force=True)
        with open(global_profile.config_path) as fp:
            buf = fp.read()
            self.assertEqual(buf, '''[global]
hello = 12

[hello]
world = 13

''')

    def test_get(self):
        self.test_set()
        profile = Config('ptpt')
        global_profile = Config()
        self.assertEqual(profile.get('hello', 'world'), 'True')
        self.assertEqual(global_profile.get('global', 'hello'), '12')
        self.assertEqual(global_profile.get('hello', 'world'), '13')
        self.assertIsNone(global_profile.get('hello', 'nonexists'))
        self.assertIsNone(global_profile.get('nonexists', 'nonexists'))

    def test_unset(self):
        self.test_set()
        profile = Config('ptpt')
        global_profile = Config()
        global_profile.unset('global', 'hello')
        global_profile.save()
        with open(global_profile.config_path) as f:
            buf = f.read()
            self.assertEqual(buf, '[hello]\nworld = 13\n\n')
        profile.unset('hello', 'world')
        profile.save()
        with open(profile.config_path) as f:
            buf = f.read()
            self.assertEqual(buf, '')

    def test_clear(self):
        profile = Config('ptpt')
        profile.clear()
        self.assertFalse(os.path.isfile(profile.config_path))
        self.assertFalse(os.path.isdir(os.path.dirname(profile.config_path)))

    def test_is_global(self):
        profile = Config('ptpt')
        self.assertFalse(profile.is_global)
        self.assertTrue(Config.get_global().is_global)
        self.assertTrue(Config().is_global)

    def test_get_all(self):
        self.assertEqual(Config.get_all(), [])
        profile = Config('ptpt')
        all = Config.get_all()
        self.assertEqual([profile.name], all)

    def tearDown(self):
        if os.path.isdir(Config.config_root):
            rmtree(Config.config_root)


class TestInput(unittest.TestCase):
    def setUp(self):
        Config.config_root = 'tmp_ptwit_profile'

    def test_choose_name(self):
        values = iter(['hello', 'world', '', 'ptpt'])

        def raw_input(prompt=''):
            return values.next()

        ptwit.raw_input = raw_input
        self.assertEqual('hello', ptwit.choose_config_name('default'))
        self.assertEqual('world', ptwit.choose_config_name('default'))
        self.assertEqual('default', ptwit.choose_config_name('default'))
        profile = Config('ptpt')
        self.assertRaises(ptwit.PtwitError, ptwit.choose_config_name, 'default')

    def test_get_consumer_and_token(self):
        consumer_key = 'consumer_key'
        consumer_secret = 'consumer_secret'
        token_key = 'token_key'
        token_secret = 'token_secret'

        old_get_consumer = ptwit.input_consumer_pair
        old_get_oauth = ptwit.get_oauth

        ptwit.input_consumer_pair = lambda: (consumer_key, consumer_secret)
        ptwit.get_oauth = lambda _, __: (token_key, token_secret)

        _, filename = tempfile.mkstemp()
        config = TwitterConfig(filename)

        self.assertEqual(ptwit.get_consumer_and_token(config, 'Tao'),
                         (consumer_key, consumer_secret, token_key, token_secret))

        ptwit.input_consumer_pair = old_get_consumer
        ptwit.get_oauth = old_get_oauth

        config.set('consumer_key', consumer_key)
        config.set('consumer_secret', consumer_secret)
        config.set('token_key', token_key, account='Tao')
        config.set('token_secret', token_secret, account='Tao')

        self.assertEqual(ptwit.get_consumer_and_token(config, 'Tao'),
                         (consumer_key, consumer_secret, token_key, token_secret))

        os.remove(filename)

    def tearDown(self):
        ptwit.raw_input = raw_input
        if os.path.isdir(Config.config_root):
            rmtree(Config.config_root)


if __name__ == '__main__':
    unittest.main()
