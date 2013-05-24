import unittest
import os
import sys
from shutil import rmtree
from time import strftime
from datetime import datetime
from ptwit.ptwit import Config, lookup, render_template
from ptwit import ptwit


class TestFormat(unittest.TestCase):
    def testLookup(self):
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


class TestProfile(unittest.TestCase):
    def setUp(self):
        Config.config_root = os.path.join(os.path.dirname(__file__),
                                            'tmp_profile_dir')

    def testGlobal(self):
        # always return the same global profile
        self.assertTrue(Config.get_global() is Config.get_global())

    def testDirectory(self):
        profile = Config('ptpt')
        self.assertTrue(os.path.isdir(Config.config_root))
        self.assertFalse(os.path.isfile(os.path.join(Config.config_root, 'global.conf')))
        self.assertFalse(os.path.isfile(profile.config_path))

    def testSet(self):
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

    def testGet(self):
        self.testSet()
        profile = Config('ptpt')
        global_profile = Config()
        self.assertEqual(profile.get('hello', 'world'), 'True')
        self.assertEqual(global_profile.get('global', 'hello'), '12')
        self.assertEqual(global_profile.get('hello', 'world'), '13')
        self.assertIsNone(global_profile.get('hello', 'nonexists'))
        self.assertIsNone(global_profile.get('nonexists', 'nonexists'))

    def testUnset(self):
        self.testSet()
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

    def testClear(self):
        profile = Config('ptpt')
        profile.clear()
        self.assertFalse(os.path.isfile(profile.config_path))
        self.assertFalse(os.path.isdir(os.path.dirname(profile.config_path)))

    def testIsGlobal(self):
        profile = Config('ptpt')
        self.assertFalse(profile.is_global)
        self.assertTrue(Config.get_global().is_global)
        self.assertTrue(Config().is_global)

    def testGetAll(self):
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

    def testChooseName(self):
        vals = iter(['hello', 'world', '', 'ptpt'])
        def raw_input(prompt=''):
            return vals.next()
        ptwit.raw_input = raw_input
        self.assertEqual('hello', ptwit.choose_config_name('default'))
        self.assertEqual('world', ptwit.choose_config_name('default'))
        self.assertEqual('default', ptwit.choose_config_name('default'))
        profile = Config('ptpt')
        self.assertRaises(ptwit.PtwitError, ptwit.choose_config_name, 'default')

    def testGetConsumerAndTokens(self):
        consumer_key = 'consumer_key'
        consumer_secret = 'consumer_secret'
        token_key = 'token_key'
        token_secret = 'token_secret'
        # vals = iter([consumer_key, consumer_secret, token_key, token_secret])
        # def raw_input(prompt=''):
        #     return vals.next()
        # ptwit.raw_input = raw_input
        old_get_consumer = ptwit.input_consumer_pair
        old_get_oauth = ptwit.get_oauth
        ptwit.input_consumer_pair = lambda: (consumer_key, consumer_secret)
        ptwit.get_oauth = lambda ck, cs: (token_key, token_secret)
        profile = Config('ptpt')
        self.assertEqual(ptwit.get_consumer_and_token(profile),
                         (consumer_key, consumer_secret, token_key, token_secret))
        ptwit.input_consumer_pair = old_get_consumer
        ptwit.get_oauth = old_get_oauth

        profile.set('consumer', 'key', consumer_key+'2')
        profile.set('consumer', 'secret', consumer_secret+'2')
        profile.set('token', 'key', token_key+'2')
        profile.set('token', 'secret', token_secret+'2')
        self.assertEqual(ptwit.get_consumer_and_token(profile),
                         (consumer_key+'2', consumer_secret+'2', token_key+'2', token_secret+'2'))

    def tearDown(self):
        ptwit.raw_input = raw_input
        if os.path.isdir(Config.config_root):
            rmtree(Config.config_root)


if __name__ == '__main__':
    unittest.main()
