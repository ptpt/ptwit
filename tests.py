import unittest
import os
import sys
from shutil import rmtree
from time import strftime
from datetime import datetime
from ptwit.ptwit import Profile, lookup, render_template
from ptwit import ptwit


class TestFormat(unittest.TestCase):
    def testLookup(self):
        profile = {
            'user': {'name': 'pt',
                     'age': 24},
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
        Profile.profile_root = os.path.join(os.path.dirname(__file__),
                                            'tmp_profile_dir')

    def testGlobal(self):
        # always return the same global profile
        self.assertTrue(Profile.get_global() is Profile.get_global())

    def testDirectory(self):
        profile = Profile('ptpt')
        self.assertTrue(os.path.isdir(Profile.profile_root))
        self.assertFalse(os.path.isfile(os.path.join(Profile.profile_root, 'global.conf')))
        self.assertFalse(os.path.isfile(profile.config_path))

    def testSet(self):
        profile = Profile('ptpt')
        profile.set('hello', 'world', True)
        profile.save()
        with open(profile.config_path) as f:
            buf = f.read()
            self.assertEqual(buf, '''[hello]
world = True

''')
        global_profile = Profile()
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
        profile = Profile('ptpt')
        global_profile = Profile()
        self.assertEqual(profile.get('hello', 'world'), 'True')
        self.assertEqual(global_profile.get('global', 'hello'), '12')
        self.assertEqual(global_profile.get('hello', 'world'), '13')
        self.assertIsNone(global_profile.get('hello', 'nonexists'))
        self.assertIsNone(global_profile.get('nonexists', 'nonexists'))

    def testUnset(self):
        self.testSet()
        profile = Profile('ptpt')
        global_profile = Profile()
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
        profile = Profile('ptpt')
        profile.clear()
        self.assertFalse(os.path.isfile(profile.config_path))
        self.assertFalse(os.path.isdir(os.path.dirname(profile.config_path)))

    def testIsGlobal(self):
        profile = Profile('ptpt')
        self.assertFalse(profile.is_global)
        self.assertTrue(Profile.get_global().is_global)
        self.assertTrue(Profile().is_global)

    def testGetAll(self):
        self.assertEqual(Profile.get_all(), [])
        profile = Profile('ptpt')
        all = Profile.get_all()
        self.assertEqual([profile.name], all)

    def tearDown(self):
        if os.path.isdir(Profile.profile_root):
            rmtree(Profile.profile_root)


class TestInput(unittest.TestCase):
    def setUp(self):
        Profile.profile_root = 'tmp_ptwit_profile'

    def testChooseName(self):
        vals = iter(['hello', 'world', '', 'ptpt'])
        def raw_input(prompt=''):
            return vals.next()
        ptwit.raw_input = raw_input
        self.assertEqual('hello', ptwit.choose_profile_name('default'))
        self.assertEqual('world', ptwit.choose_profile_name('default'))
        self.assertEqual('default', ptwit.choose_profile_name('default'))
        profile = Profile('ptpt')
        self.assertRaises(ptwit.PtwitError, ptwit.choose_profile_name, 'default')

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
        profile = Profile('ptpt')
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
        if os.path.isdir(Profile.profile_root):
            rmtree(Profile.profile_root)


if __name__ == '__main__':
    unittest.main()
