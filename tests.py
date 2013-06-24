import unittest
import os
import tempfile
from shutil import rmtree
from datetime import datetime

from ptwit import ptwit
from ptwit.ptwit import lookup, render_template
from ptwit.config import PtwitConfig


class TestPtwitConfig(unittest.TestCase):
    def setUp(self):
        _, self.filename = tempfile.mkstemp()

    def tearDown(self):
        os.remove(self.filename)

    def test_open(self):
        filename = tempfile.mktemp()
        # create if config file does not exist
        config = PtwitConfig(filename)
        self.assertTrue(os.path.isfile(filename))
        os.remove(filename)
        # if the path is a directory?
        dirname = tempfile.mkdtemp()
        self.assertRaises(IOError, PtwitConfig, dirname)
        os.removedirs(dirname)

    def test_set(self):
        config = PtwitConfig(self.filename)
        config.set('option', 'value')  # save hello=world to general section
        config.set('name', 'tao', account='Tao')
        config.set('name', 'mian', account='Mian')
        self.assertEqual(config.config.items('general'), [('option', 'value')])
        self.assertEqual(config.config.items('Tao'), [('name', 'tao')])
        self.assertEqual(config.config.items('Mian'), [('name', 'mian')])

    def test_get(self):
        config = PtwitConfig(self.filename)
        config.set('option', 'value')
        config.set('format', 'json', account='Tao')
        self.assertEqual(config.get('option'), 'value')
        self.assertEqual(config.get('format', account='Tao'), 'json')

    def test_unset(self):
        config = PtwitConfig(self.filename)
        config.set('option', 'value')
        config.set('format', 'json', account='Tao')
        config.unset('format', account='Tao')
        config.unset('option')
        self.assertIsNone(config.get('format', account='Tao'))
        self.assertIsNone(config.get('option'))

    def test_remove_account(self):
        config = PtwitConfig(self.filename)
        config.set('option', 'value', account='Tao')
        config.remove_account('Tao')

    def test_list_account(self):
        config = PtwitConfig(self.filename)
        self.assertEqual(config.list_accounts(), [])
        config.set('option', 'value')
        config.set('option', 'value', account='Tao')
        self.assertEqual(config.list_accounts(), ['Tao'])

    def test_save(self):
        config = PtwitConfig(self.filename)
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


class TestInput(unittest.TestCase):
    def setUp(self):
        _, self.filename = tempfile.mkstemp()

    def tearDown(self):
        os.remove(self.filename)
        ptwit.raw_input = raw_input

    def test_choose_name(self):
        config = PtwitConfig(self.filename)
        values = iter(['hello', 'world', '', 'ptpt'])

        def raw_input(prompt=''):
            return values.next()

        ptwit.raw_input = raw_input
        self.assertEqual('hello', ptwit.choose_config_name('default', config))
        self.assertEqual('world', ptwit.choose_config_name('default', config))
        self.assertEqual('default', ptwit.choose_config_name('default', config))
        config.set('hello', 'world', account='ptpt')
        self.assertRaises(ptwit.PtwitError, ptwit.choose_config_name, 'default', config)

    def test_get_consumer_and_token(self):
        consumer_key = 'consumer_key'
        consumer_secret = 'consumer_secret'
        token_key = 'token_key'
        token_secret = 'token_secret'

        old_get_consumer = ptwit.input_consumer_pair
        old_get_oauth = ptwit.get_oauth

        ptwit.input_consumer_pair = lambda: (consumer_key, consumer_secret)
        ptwit.get_oauth = lambda _, __: (token_key, token_secret)

        config = PtwitConfig(self.filename)

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


if __name__ == '__main__':
    unittest.main()
