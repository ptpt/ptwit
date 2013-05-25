#!/usr/bin/env python

import sys
import os
import time
import twitter
import argparse
import ConfigParser
from HTMLParser import HTMLParser
from datetime import datetime


CONFIG_DIR = os.path.expanduser('~/.ptwit')

FORMAT_TWEET = '\t\033[7m %user.name% \033[0m  (@%user.screen_name%)\n\t%text%\n'

FORMAT_SEARCH = '\t\033[7m %user.screen_name% \033[0m\n\t%text%\n'

FORMAT_MESSAGE = '[%sender_screen_name%] %text%\n'

FORMAT_USER = '''@%screen_name%
Name:        %name%
Location:    %location%
URL:         %url%
Followers:   %followers_count%
Following:   %friends_count%
Status:      %statuses_count%
Description: %description%
'''


class PtwitError(Exception):
    """ Application error. """

    pass


def lookup(key, dictionary):
    """
    Lookup a flatten key in a dictionary recursively.
    The key is a series of keys concatenated by dot.

    for example:
    lookup('user.name', dictionary) does the same thing as dictionary['user']['name'] does.
    """
    if key in dictionary:
        if isinstance(dictionary[key], basestring):
            return unicode(dictionary[key])
        else:
            return dictionary[key]
    else:
        subkeys = key.split('.', 1)
        if len(subkeys) is not 2:
            return None
        if subkeys[0] in dictionary and \
                isinstance(dictionary[subkeys[0]], dict):
            return lookup(subkeys[1], dictionary[subkeys[0]])
        else:
            return None


def render_template(template, data, time=None):
    """
    Render template using a dictionary data.

    All strings between a pair of percent sign will be replaced by the
    value found in the data dictionary.
    """
    state = -1
    text = ''
    for i in xrange(len(template)):
        if template[i] == '%':
            if state < 0:
                # open percent sign
                state = i + 1
            else:
                # close percent sign
                tag = template[state:i]
                if tag == '':
                    # if two percent signs found together,
                    # replace them with a single percent sign
                    text += '%'
                else:
                    if time and tag in list('aAbBcdHIJmMpSUwWxXyYZ'):
                        # time variables
                        value = time.strftime('%' + tag)
                    else:
                        # data variables
                        value = unicode(lookup(tag, data))
                    # concatenate them and store the result
                    text += '%' + tag + '%' if value is None else value
                # remember to mark percent sign state as closed
                state = -1
        elif state == -1:
            text = text + template[i]
    if state >= 0:
        text = text + '%' + template[state:]
    return text


def get_oauth(consumer_key, consumer_secret):
    """ Take consumer key and secret, return authorized tokens. """

    import webbrowser
    import oauth2 as oauth
    from urlparse import parse_qsl

    oauth_consumer = oauth.Consumer(key=consumer_key, secret=consumer_secret)
    oauth_client = oauth.Client(oauth_consumer)

    # get request token
    resp, content = oauth_client.request(twitter.REQUEST_TOKEN_URL)
    if resp['status'] != '200':
        raise PtwitError(
            'Invalid respond from Twitter requesting temp token: %s' %
            resp['status'])
    request_token = dict(parse_qsl(content))

    # get pincode
    authorization_url = '%s?oauth_token=%s' % \
        (twitter.AUTHORIZATION_URL, request_token['oauth_token'])
    print 'Opening:', authorization_url
    webbrowser.open_new_tab(authorization_url)
    time.sleep(1)
    pincode = raw_input('Enter the pincode: ')

    # get access token
    token = oauth.Token(request_token['oauth_token'],
                        request_token['oauth_token_secret'])
    token.set_verifier(pincode)
    oauth_client = oauth.Client(oauth_consumer, token)
    resp, content = oauth_client.request(twitter.ACCESS_TOKEN_URL,
                                         method='POST',
                                         body='oauth_verifier=%s' % pincode)
    access_token = dict(parse_qsl(content))
    if resp['status'] != '200':
        raise PtwitError('The request for a Token did not succeed: %s' %
                         resp['status'])
    else:
        return access_token['oauth_token'], access_token['oauth_token_secret']


def input_consumer_pair():
    """ Input consumer key/secret pair """

    return raw_input('Consumer key: ').strip(), \
        raw_input('Consumer secret: ').strip()


class ConfigError(Exception):
    """ Config error """

    pass


class Config(object):
    config_root = CONFIG_DIR
    _global = None

    def __init__(self, name=None):
        self.name = name
        conf_dir = os.path.join(Config.config_root, name or '')
        if not os.path.isdir(conf_dir):
            os.makedirs(conf_dir)
        self.config_path = os.path.join(
            conf_dir, 'user.conf' if self.name else 'global.conf')
        self._config = None
        self._modified = False

    @property
    def config(self):
        """ Return this instance's config object. """
        if not self._config:
            self._config = ConfigParser.RawConfigParser()
            with open(self.config_path,
                      'r' if os.path.isfile(self.config_path) else 'w+') as fp:
                self._config.readfp(fp)
        return self._config

    @property
    def is_global(self):
        """ Determine if current instance is global. """
        return self.name is None

    @classmethod
    def get_global(cls):
        """ Get the unique global config instance. """
        if cls._global is None:
            cls._global = Config()
        return cls._global

    def set(self, section, option, value):
        """ Set the value of specified option. """
        if value != self.get(section, option):
            if not self.config.has_section(section):
                self.config.add_section(section)
            self.config.set(section, option, value)
            self._modified = True

    def unset(self, section, option=None):
        """ Remove the value of specified option. """
        if option is None:
            self.config.remove_section(section)
        else:
            self.config.remove_option(section, option)
            if not len(self.config.options(section)):
                self.config.remove_section(section)
        self._modified = True

    def get(self, section, option):
        """ Return the value of specified option. """
        try:
            return self.config.get(section, option)
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            return None

    @classmethod
    def get_all(cls):
        """ Return all configurations. """
        if os.path.isdir(cls.config_root):
            return [config for config in os.listdir(cls.config_root)
                    if os.path.isdir(os.path.join(cls.config_root, config))
                    and not config.startswith('.')]
        else:
            return []

    def save(self, force=False):
        """ Save changed settings. """
        if force or self._modified:
            with open(self.config_path, 'wb') as fp:
                self.config.write(fp)
            self._modified = False

    def clear(self):
        """ Delete config folder. """
        config_folder = os.path.dirname(self.config_path)
        if os.path.isdir(config_folder):
            from shutil import rmtree
            rmtree(config_folder)
        else:
            raise ConfigError('Config "%s" doesn\'t exist.' % config_folder)


class ConfigCommandsError(Exception):
    """ ConfigCommands error. """
    pass


class ConfigCommands(object):
    def __init__(self, args, config):
        self.args = args
        self.config = config

    def set(self):
        """ Command: set SECTION.OPTION VALUE """
        config = Config.get_global() if self.args.g else self.config
        try:
            section, option = self.args.option.split('.', 1)
        except ValueError:
            raise ConfigCommandsError(
                'You must specify a option like this "SECTION.OPTION".')
        value = self.args.value
        if self.args.g and section.lower() in ('profile', 'config') and \
                option.lower() == 'default':
            if value not in Config.get_all():
                raise ConfigCommandsError(
                    'Config %s doesn\'t exist.' % value)
        config.set(section, option, value)
        config.save()

    def unset(self):
        """ Command: unset SECTION.OPTION [SECTION.OPTION ...] """
        config = Config.get_global() if self.args.g else self.config
        pack = [v.split('.', 1) for v in self.args.option]
        for option in pack:
            if len(option) == 1:
                config.unset(option[0], None)
            elif len(option) == 2:
                config.unset(option[0], option[1])
        config.save()

    def all(self):
        """ List all configs. """
        for config in Config.get_all():
            print config

    def get(self):
        """ Command: get SECTION.OPTION """
        config = Config.get_global() if self.args.g else self.config
        nonexist = False
        if self.args.option:
            pack = [v.split('.', 1) for v in self.args.option]
            try:
                for section, option in pack:
                    value = config.get(section, option)
                    if value is None:
                        print >> sys.stderr, \
                            '"%s.%s" is not found.' % (section, option)
                        nonexist = True
                    else:
                        print value
            except ValueError:
                raise ConfigCommandsError(
                    'You must specify a option like this "SECTION.OPTION".')
        else:
            config.config.write(sys.stdout)
        if nonexist:
            raise ConfigCommandsError('Some options is not found.')

    def remove(self):
        """ Command: remove CONFIG """
        nonexist = False
        for name in self.args.profile:
            if name in Config.get_all():
                Config(name).clear()
            else:
                print >> sys.stderr, 'Config "%s" doesn\'t exist.' % name
                nonexist = True
        if nonexist:
            raise ConfigCommandsError('Some configs doesn\'t exist.')

    def login(self):
        """ Command: login [CONFIG] """
        if not self.args.config_name:
            global_config = Config.get_global()

            consumer_key, consmer_secret, consumer_key, token_secret = \
                get_consumer_and_token(global_config)
            api = twitter.Api(consumer_key=consumer_key,
                              consumer_secret=consmer_secret,
                              access_token_key=consumer_key,
                              access_token_secret=token_secret)
            user_config_name = \
                choose_config_name(api.VerifyCredentials().screen_name)
            user_config = Config(user_config_name)
            global_config.set('config', 'default', user_config_name.lower())

            # set consumer pairs both in the user config and global config
            if not global_config.get('consumer', 'key'):
                global_config.set('consumer', 'key', consumer_key)
            user_config.set('consumer', 'key', consumer_key)
            if not global_config.get('consumer', 'secret'):
                global_config.set('consumer', 'secret', consmer_secret)
            user_config.set('consumer', 'secret', consmer_secret)

            # set token pairs
            user_config.set('token', 'key', consumer_key)
            user_config.set('token', 'secret', token_secret)

            # save configs
            user_config.save()
            global_config.save()

        elif self.args.config_name in Config.get_all():
            # login the existing config
            self.args.g = True
            self.args.call = 'set'
            self.args.option = 'profile.default'
            self.args.value = self.args.config_name
            self.call()
        else:
            raise ConfigCommandsError('Config "%s" doesn\'t exist' % self.args.config_name)

    def call(self, function=None):
        if function is None:
            getattr(self, self.args.call)()
        else:
            getattr(self, function)()


class TwitterCommands(object):
    html_parser = HTMLParser()

    def __init__(self, api, args, config):
        self.api = api
        self.args = args
        self.config = config

    def _print_user(self, user):
        user = user.AsDict()
        template = self.args.specified_format or \
            self.config.get('format', 'user') or \
            FORMAT_USER
        print render_template(template, user).encode('utf-8')

    def _print_users(self, users):
        for user in users:
            self._print_user(user)

    def _print_tweet(self, tweet):
        tweet = tweet.AsDict()
        tweet['text'] = self.html_parser.unescape(tweet['text'])
        template = self.args.specified_format or \
            self.config.get('format', 'tweet') or \
            FORMAT_TWEET
        created_at = datetime.strptime(
            tweet['created_at'],
            '%a %b %d %H:%M:%S +0000 %Y')
        print render_template(template, tweet, time=created_at).encode('utf-8')

    def _print_tweets(self, tweets):
        for tweet in tweets:
            self._print_tweet(tweet)

    def _print_search(self, tweet):
        tweet = tweet.AsDict()
        tweet['text'] = self.html_parser.unescape(tweet['text'])
        template = self.args.specified_format or \
            self.config.get('format', 'search') or \
            FORMAT_SEARCH
        print render_template(
            template, tweet,
            time=datetime.strptime(tweet['created_at'],
                                   '%a, %d %b %Y %H:%M:%S +0000'))

    def _print_searches(self, tweets):
        for tweet in tweets:
            self._print_search(tweet)

    def _print_message(self, message):
        message = message.AsDict()
        template = self.args.specified_format or \
            self.config.get('format', 'message') or \
            FORMAT_MESSAGE
        print render_template(
            template, message,
            time=datetime.strptime(
                message['created_at'],
                '%a %b %d %H:%M:%S +0000 %Y')).encode('utf-8')

    def _print_messages(self, messages):
        for message in messages:
            self._print_message(message)

    # def public(self):
    #     self._print_tweets(self.api.GetPublicTimeline())

    def post(self):
        if len(self.args.post):
            post = ' '.join(self.args.post)
        else:
            post = sys.stdin.read()
        # convert to unicode
        post = post.decode('utf-8')
        self._print_tweet(self.api.PostUpdate(post))

    def tweets(self):
        tweets = self.api.GetUserTimeline(
            self.args.user,
            count=self.args.count,
            page=self.args.page)
        self._print_tweets(tweets)

    def default(self):
        self.timeline()

    def timeline(self):
        if self.args.count is None and self.args.page is None:
            tweets = self.api.GetFriendsTimeline(
                page=self.args.page,
                since_id=self.config.get('since', 'timeline'))
        else:
            tweets = self.api.GetFriendsTimeline(
                page=self.args.page,
                count=self.args.count)
        self._print_tweets(tweets)
        if len(tweets):
            self.config.set('since', 'timeline', tweets[0].id)
            self.config.save()

    def mentions(self):
        if self.args.count is None and self.args.page is None:
            tweets = self.api.GetMentions(
                since_id=self.config.get('since', 'mentions'),
                page=self.args.page)
        else:
            tweets = self.api.GetMentions(
                # todo: twitter.GetMentions doesn't support count parameter
                # count=self.args.count,
                page=self.args.page)
        self._print_tweets(tweets)
        if len(tweets):
            self.config.set('since', 'mentions', tweets[0].id)
            self.config.save()

    def replies(self):
        if self.args.count is None and self.args.page is None:
            tweets = self.api.GetReplies(
                since_id=self.config.get('since', 'replies'),
                page=self.args.page)
        else:
            tweets = self.api.GetReplies(
                # count=self.args.count,
                page=self.args.page)
        self._print_tweets(tweets)
        if len(tweets):
            self.config.set('since', 'replies', tweets[0].id)
            self.config.save()

    def messages(self):
        if self.args.count is None and self.args.page is None:
            messages = self.api.GetDirectMessages(
                since_id=self.config.get('since', 'messages'),
                page=self.args.page)
        else:
            messages = self.api.GetDirectMessages(
                page=self.args.page)
        self._print_messages(messages)
        if len(messages):
            self.config.set('since', 'messages', messages[0].id)
            self.config.save()

    def send(self):
        user = self.args.user
        if len(self.args.message):
            message = ' '.join(self.args.message)
        else:
            message = sys.stdin.read()
        # convert to unicode
        message = message.decode('utf-8')
        self._print_message(self.api.PostDirectMessage(user, message))

    def following(self):
        self._print_users(self.api.GetFriends(self.args.user))

    def followers(self):
        if self.args.user:
            user = self.api.GetUser(self.args.user)
            self._print_users(self.api.GetFollowers(user=user))
        else:
            self._print_users(self.api.GetFollowers())

    def follow(self):
        user = self.api.CreateFriendship(self.args.user)
        print 'You have requested to follow @%s' % user.screen_name

    def unfollow(self):
        user = self.api.DestroyFriendship(self.args.user)
        print 'You have unfollowed @%s' % user.screen_name

    def faves(self):
        self._print_tweets(self.api.GetFavorites(user=self.args.user,
                                                 page=self.args.page))

    def search(self):
        term = ' '.join(self.args.term)
        # convert to unicode
        term = term.decode('utf-8')
        tweets = self.api.GetSearch(term=term)  # todo: can't encode unicode; fix it
        self._print_searches(tweets)

    def whois(self):
        users = [self.api.GetUser(user) for user in self.args.users]
        self._print_users(users)

    def call(self, function):
        getattr(self, function)()


def parse_args(argv):
    """Parse command arguments."""

    parser = argparse.ArgumentParser(description='Twitter command-line.',
                                     prog='ptwit')

    # global options
    parser.add_argument('-p', dest='specified_profile', metavar='profile',
                        action='store', help='specify a profile')
    parser.add_argument('-c', dest='specified_config', metavar='config',
                        action='store', help='specify a config')
    parser.add_argument('-f', dest='specified_format', metavar='format',
                        help='print format')

    # todo: default command

    #### twitter commands
    subparsers = parser.add_subparsers(title='twitter commands')

    # login
    p = subparsers.add_parser('login', help='login')
    p.add_argument('config_name', nargs='?', metavar='CONFIG')
    p.set_defaults(type=ConfigCommands, function='login')

    # public
    # p = subparsers.add_parser('public', help='list public timeline')
    # p.set_defaults(type=TwitterCommands, function='public')

    # followings
    p = subparsers.add_parser('following', help='list following')
    p.add_argument('user', nargs='?', metavar='USER')
    p.set_defaults(type=TwitterCommands, function='following')

    # followers
    p = subparsers.add_parser('followers', help='list followers')
    p.add_argument('user', nargs='?', metavar='USER')
    p.set_defaults(type=TwitterCommands, function='followers')

    # follow
    p = subparsers.add_parser('follow', help='follow someone')
    p.add_argument('user', metavar='USER')
    p.set_defaults(type=TwitterCommands, function='follow')

    # unfollow
    p = subparsers.add_parser('unfollow', help='unfollow someone')
    p.add_argument('user', metavar='USER')
    p.set_defaults(type=TwitterCommands, function='unfollow')

    # tweets
    p = subparsers.add_parser('tweets', help='list tweets')
    p.add_argument('-c', dest='count', type=int)
    p.add_argument('-p', dest='page', type=int)
    p.add_argument('user', nargs='?', metavar='USER')
    p.set_defaults(type=TwitterCommands, function='tweets')

    # timeline
    p = subparsers.add_parser('timeline', help='list friends timeline')
    p.add_argument('-c', dest='count', type=int)
    p.add_argument('-p', dest='page', type=int)
    p.set_defaults(type=TwitterCommands, function='timeline')

    # faves
    p = subparsers.add_parser('faves', help='list favourites')
    p.add_argument('-p', dest='page', type=int)
    p.add_argument('user', nargs='?', metavar='USER')
    p.set_defaults(type=TwitterCommands, function='faves')

    # post
    p = subparsers.add_parser('post', help='post a tweet')
    p.add_argument('post', nargs='*', metavar='TEXT')
    p.set_defaults(type=TwitterCommands, function='post')

    # mentions
    p = subparsers.add_parser('mentions', help='list mentions')
    p.add_argument('-p', dest='page', type=int)
    p.add_argument('-c', dest='count', type=int)
    p.set_defaults(type=TwitterCommands, function='mentions')

    # messages
    p = subparsers.add_parser('messages', help='list messages')
    p.add_argument('-p', dest='page', type=int)
    p.add_argument('-c', dest='count', type=int)
    p.set_defaults(type=TwitterCommands, function='messages')

    # send
    p = subparsers.add_parser('send', help='send direct message')
    p.add_argument('user', metavar='USER')
    p.add_argument('message', nargs='*', metavar='TEXT')
    p.set_defaults(type=TwitterCommands, function='send')

    # replies
    p = subparsers.add_parser('replies', help='list replies')
    p.add_argument('-p', dest='page', type=int)
    p.add_argument('-c', dest='count', type=int)
    p.set_defaults(type=TwitterCommands, function='replies')

    # whois
    p = subparsers.add_parser('whois', help='show user information')
    p.add_argument('users', nargs='+', metavar='USER')
    p.set_defaults(type=TwitterCommands, function='whois')

    # search
    p = subparsers.add_parser('search', help='search twitter')
    p.add_argument('term', nargs='+', metavar='TERM')
    p.set_defaults(type=TwitterCommands, function='search')

    #### profile commands
    profile_parser = subparsers.add_parser('profile', help='manage profiles')
    profile_parser.add_argument('-g',
                                action='store_true',
                                dest='g',
                                help='apply global configuration only')
    pp = profile_parser.add_subparsers(title='profile',
                                       help='profile commands')

    # todo default profile command

    # profile set
    p = pp.add_parser('set', help='set option')
    p.add_argument('option', metavar='SECTION.OPTION')
    p.add_argument('value', metavar='VALUE')
    p.set_defaults(type=ConfigCommands, function='set')

    # profile get
    p = pp.add_parser('get', help='get option')
    p.add_argument('option', metavar='SECTION.OPTION', nargs='*')
    p.set_defaults(type=ConfigCommands, function='get')

    # profile unset
    p = pp.add_parser('unset', help='unset option')
    p.add_argument('option', metavar='SECTION.OPTION', nargs='+')
    p.set_defaults(type=ConfigCommands, function='unset')

    # profile list all
    p = pp.add_parser('all', help='list all profiles')
    p.set_defaults(type=ConfigCommands, function='all')

    # profile remove profiles
    p = pp.add_parser('remove', help='remove profiles')
    p.add_argument('profile', nargs='+', metavar='PROFILE')
    p.set_defaults(type=ConfigCommands, function='remove')

    #### config commands
    config_parser = subparsers.add_parser('config', help='manage config')
    config_parser.add_argument('-g', action='store_true', dest='g',
                               help='apply global configuration only')
    pp = config_parser.add_subparsers(title='config',
                                      help='config commands')

    # config set
    p = pp.add_parser('set', help='set option')
    p.add_argument('option', metavar='SECTION.OPTION')
    p.add_argument('value', metavar='VALUE')
    p.set_defaults(type=ConfigCommands, function='set')

    # config get
    p = pp.add_parser('get', help='get option')
    p.add_argument('option', metavar='SECTION.OPTION', nargs='*')
    p.set_defaults(type=ConfigCommands, function='get')

    # config unset
    p = pp.add_parser('unset', help='unset option')
    p.add_argument('option', metavar='SECTION.OPTION', nargs='+')
    p.set_defaults(type=ConfigCommands, function='unset')

    # config list all
    p = pp.add_parser('all', help='list all configs')
    p.set_defaults(type=ConfigCommands, function='all')

    # config remove profiles
    p = pp.add_parser('remove', help='remove config')
    p.add_argument('config', nargs='+', metavar='CONFIG')
    p.set_defaults(type=ConfigCommands, function='remove')

    return parser.parse_args(argv)


def get_consumer_and_token(config):
    """Get consumer pairs and token pairs from config or prompt."""

    global_config = Config.get_global()
    consumer_key = config.get('consumer', 'key')

    # read consumer pairs from user config, and then global config
    if not consumer_key and not config.is_global:
        consumer_key = global_config.get('consumer', 'key')
    consumer_secret = config.get('consumer', 'secret')
    if not consumer_secret and not config.is_global:
        consumer_secret = global_config.get('consumer', 'secret')
    token_key = config.get('token', 'key')
    token_secret = config.get('token', 'secret')

    try:
        # if consumer pairs still not found, then let user input
        if not (consumer_key and consumer_secret):
            # todo: rename to input_consumer
            consumer_key, consumer_secret = input_consumer_pair()

        # if token pairs still not found, get them from twitter oauth server
        if not (token_key and token_secret):
            token_key, token_secret = get_oauth(consumer_key, consumer_secret)
    except (KeyboardInterrupt, EOFError):
        sys.exit(0)

    return consumer_key, consumer_secret, token_key, token_secret


def choose_config_name(default):
    """ Prompt for choosing config name. """

    name = default

    while True:
        try:
            name = raw_input(
                'Enter a config name (%s): ' % default).strip()
        except KeyboardInterrupt:
            sys.exit(0)
        if not name:
            name = default
        if name in Config.get_all():
            raise PtwitError('Config "%s" exists.' % name)
        elif name:
            break

    return name


def main(argv):
    """ Parse arguments and issue commands. """

    args = parse_args(argv)

    global_config = Config.get_global()

    # get default user from global profile's default section
    user_config_name = args.specified_profile or \
        global_config.get('config', 'default') or \
        global_config.get('profile', 'default')
    user_config = Config(user_config_name) if user_config_name else None

    # if it is profile subcommands, them handle profile commands and quit
    if args.type == ConfigCommands:
        commands = ConfigCommands(args, user_config or global_config)
        commands.call(args.function)
        sys.exit(0)

    # try to get customer pairs and token pairs from profiles or prompt
    consumer_key, consumer_secret, token_key, token_secret = \
        get_consumer_and_token(user_config or global_config)
    api = twitter.Api(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token_key=token_key,
        access_token_secret=token_secret)

    # if user profile not found, create it
    if not user_config:
        user_config_name = choose_config_name(
            api.VerifyCredentials().screen_name)
        user_config = Config(user_config_name)

    # if global profile's default section is empty, oh, you will be
    # the default user
    if not global_config.get('profile', 'default'):
        global_config.set('profile', 'default', user_config_name)

    # set consumer pairs both in the user profile and global profile
    if not global_config.get('consumer', 'key'):
        global_config.set('consumer', 'key', consumer_key)
    user_config.set('consumer', 'key', consumer_key)
    if not global_config.get('consumer', 'secret'):
        global_config.set('consumer', 'secret', consumer_secret)
    user_config.set('consumer', 'secret', consumer_secret)

    # set token pairs in the user profile
    user_config.set('token', 'key', token_key)
    user_config.set('token', 'secret', token_secret)

    # save both profile
    user_config.save()
    global_config.save()

    # handle twitter commands
    if args.type == TwitterCommands:
        commands = TwitterCommands(api, args, user_config)
        commands.call(args.function)
        sys.exit(0)


def cmd():
    try:
        main(sys.argv[1:])
    except (twitter.TwitterError, PtwitError, ConfigError, ConfigCommandsError) as err:
        print >> sys.stderr, 'Error: %s' % err.message
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    cmd()
