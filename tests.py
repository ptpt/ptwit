import unittest
import os
import sys
from shutil import rmtree
from time import strftime
from datetime import datetime
from ptwit import Profile, lookup, format_dictionary


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

    def testFormatDictionary(self):
        profile = {'user': {'name': 'pt',
                            'age': 12},
                   'status': 'good',
                   'web.site': 'taopeng.me',
                   'y': 'not year'}
        self.assertEqual(format_dictionary('%user%', profile), "{'age': 12, 'name': 'pt'}")
        self.assertEqual(format_dictionary('%user.name% is good', profile), 'pt is good')
        self.assertEqual(format_dictionary('%y%', profile), 'not year')
        self.assertEqual(format_dictionary('%%', profile), '%')
        now = datetime.utcnow()
        self.assertEqual(format_dictionary('%y%', profile, now), now.strftime('%y'))


class TestProfile(unittest.TestCase):
    def setUp(self):
        root = os.path.join(os.path.dirname(__file__), 'profile_dir_for_test')
        Profile.profile_root = root
        self.profile = Profile('ptpt')

    def testDirectory(self):
        self.assertTrue(os.path.isdir(Profile.profile_root))
        self.assertTrue(os.path.isfile(os.path.join(Profile.profile_root, 'global.conf')))
        self.assertTrue(os.path.isdir(os.path.dirname(self.profile.config_path)))
        self.assertTrue(os.path.isfile(self.profile.config_path))
        self.assertRaises(Exception, Profile, 'global.conf')

    def testSet(self):
        self.profile.set('hello', 'world', True)
        self.profile.save()
        with open(self.profile.config_path) as f:
            buf = f.read()
            self.assertEqual(buf, '''[hello]
world = True

''')
        self.profile.g.set('global', 'hello', 12)
        self.profile.g.set('hello', 'world', 13)
        self.profile.save()
        with open(self.profile.g.config_path) as f:
            buf = f.read()
            self.assertEqual(buf, '''[global]
hello = 12

[hello]
world = 13

''')

    def testGet(self):
        self.testSet()
        self.assertEqual(self.profile.get('hello', 'world'), True)
        profile = Profile('ptpt')
        self.assertEqual(profile.get('hello', 'world'), 'True')
        self.assertEqual(profile.get('global', 'hello'), '12')
        self.assertEqual(profile.get('global', 'hello', g=False), None)
        self.assertEqual(profile.get('hello', 'world'), 'True')
        self.assertEqual(profile.get('hello', 'world', g=True), 'True')

    def testUnset(self):
        self.testSet()
        self.profile.g.unset('global', 'hello')
        self.profile.g.save()
        with open(self.profile.g.config_path) as f:
            buf = f.read()
            self.assertEqual(buf, '[hello]\nworld = 13\n\n')
        self.profile.unset('hello', 'world', g=True)
        self.profile.save()
        with open(self.profile.config_path) as f:
            buf = f.read()
            self.assertEqual(buf, '')
        with open(self.profile.g.config_path) as f:
            buf = f.read()
            self.assertEqual(buf, '')

    def testClear(self):
        self.profile.clear()
        self.assertFalse(os.path.isfile(self.profile.config_path))
        self.assertFalse(os.path.isdir(os.path.dirname(self.profile.config_path)))

    def testIsGlobal(self):
        self.assertFalse(self.profile.is_global)
        self.assertTrue(self.profile.g.is_global)

    def tearDown(self):
        rmtree(Profile.profile_root)
        pass

    def testGetAll(self):
        all = Profile.get_all()
        self.assertEqual([self.profile.name], all)

if __name__ == '__main__':
    unittest.main()
