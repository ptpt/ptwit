#!/usr/bin/env python

__author__ = 'Tao Peng <pt@taopeng.me>'
__version__ = '0.0.1'

import sys
import os
from shutil import rmtree
import webbrowser
import twitter
import argparse
import ConfigParser
from time import strftime, strptime

PTWIT_PROFILE_DIR = os.path.expanduser('~/.%s' % os.path.basename(__file__))
PTWIT_FORMAT_TWEET = '[%user.screen_name%] %text%'
PTWIT_FORMAT_MESSAGE = '[%sender_screen_name%] %text%'
PTWIT_FORMAT_USER =\
    '''@%screen_name%
Name:        %name%
Location:    %location%
URL:         %url%
Followers:   %followers_count%
Following:   %friends_count%
Status:      %statuses_count%
Description: %description%
'''


def lookup(key, dictionary):
    """
    Lookup `dictionary' with `key' recursively.
    e.g. lookup('user.name',
                {'user':{'name':'pt',
                         'age':24},
                 'status':'hello world'})
    will return 'pt'.
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


def format_dictionary(format, dictionary, date=None):
    """
    Format a string out of format-string and dictionary.

    Arguments:
    format: format control string
    dictionary: dictionary where values are taken from
    date: None or a function, which takes `dictionary' as input and
    get its date information (if existed).
    The date information is use to fill up format string,
    such as %y%, %m%, etc.

    Returns:
    A formatted string
    """
    state = -1
    text = ''
    for i in xrange(len(format)):
        if format[i] == '%':
            if state < 0:
                state = i + 1
            else:
                tag = format[state:i]
                if tag == '':
                    text += '%'
                else:
                    if date and tag in list('aAbBcdHIJmMpSUwWxXyYZ'):
                        value = strftime('%' + tag, date)
                    else:
                        value = unicode(lookup(tag, dictionary))
                    text += '%' + tag + '%' if value is None else value
                state = -1
        elif state == -1:
            text = text + format[i]
    if state >= 0:
        text = text + '%' + format[state:]
    return text


def get_oauth(consumer_key, consumer_secret):
    """
    Take consumer key and secret, return authorized tokens
    """
    try:
        from urlparse import parse_qsl
    except ImportError:
        from urlparse import parse_qsl
    import oauth2 as oauth

    oauth_consumer = oauth.Consumer(key=consumer_key, secret=consumer_secret)
    oauth_client = oauth.Client(oauth_consumer)
    resp, content = oauth_client.request(twitter.REQUEST_TOKEN_URL)
    if resp['status'] != '200':
        print >> sys.stderr, \
            'Invalid respond from Twitter requesting temp token: %s' % \
            resp['status']
        sys.exit(2)
    request_token = dict(parse_qsl(content))
    authorization_url = '%s?oauth_token=%s' % \
        (twitter.AUTHORIZATION_URL, request_token['oauth_token'])
    print 'Opening:', authorization_url
    webbrowser.open_new_tab(authorization_url)
    pincode = raw_input('Enter the pincode: ')
    token = oauth.Token(request_token['oauth_token'],
                        request_token['oauth_token_secret'])
    token.set_verifier(pincode)
    oauth_client = oauth.Client(oauth_consumer, token)
    resp, content = oauth_client.request(twitter.ACCESS_TOKEN_URL,
                                         method='POST',
                                         body='oauth_verifier=%s' % pincode)
    access_token = dict(parse_qsl(content))
    if resp['status'] != '200':
        print >> sys.stderr, \
            'The request for a Token did not succeed: %s' % resp['status']
        sys.exit(2)
    else:
        return access_token['oauth_token'], access_token['oauth_token_secret']


def get_consumer():
    return raw_input('Consumer key: ').strip(), \
        raw_input('Consumer secret: ').strip()


def get_dir_create(dir):
    """
    Return `dir_name`. If `dir_name' not existed, then create it.
    """
    if not os.path.isdir(dir):
        try:
            os.mkdir(dir)
        except OSError:
            print >> sys.stderr, 'unable to create %s' % dir
            sys.exit(1)
    return dir


class Profile(object):
    global_path = PTWIT_PROFILE_DIR

    def __init__(self, profile_name=None, create_dir=False):
        self.profile_name = profile_name
        if create_dir:
            self._path = get_dir_create(os.path.join(Profile.global_path,
                                                     profile_name or ''))
        else:
            self._path = os.path.join(Profile.global_path, profile_name or '')
        self._config_path = os.path.join(
            self._path,
            'global.conf' if self.profile_name is None else 'user.conf')
        self._config = None
        self._config_modified = False

    @classmethod
    def get_all(cls):
        return [profile for profile in os.listdir(cls.global_path)
                if os.path.isdir(os.path.join(cls.global_path, profile)) and \
                    not profile.startswith('.')]

    @property
    def config(self):
        if self._config is None:
            self._config = self.read_config()
        return self._config

    @property
    def path(self):
        return self._path

    @property
    def is_global(self):
        return self.profile_name is None

    def read_config(self):
        self._config = ConfigParser.RawConfigParser()
        try:
            with open(self._config_path) as f:
                self._config.readfp(f)
        except IOError:
            pass
        return self._config

    def set(self, section, option, value):
        config = self.config
        if value != self.get(section, option):
            if not config.has_section(section):
                config.add_section(section)
            config.set(section, option, value)
            self._config_modified = True

    def get(self, section, option):
        config = self.config
        try:
            return config.get(section, option)
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            return None

    def remove(self, section, option=None):
        config = self.config
        if option is None:
            config.remove_section(section)
        else:
            config.remove_option(section, option)
            if not len(config.options(section)):
                config.remove_section(section)
        self._config_modified = True

    def save(self):
        if self._config_modified:
            with open(self._config_path, 'wb') as f:
                self.config.write(f)
            self._config_modified = False

    def clear(self):
        if os.path.isdir(self._path):
            try:
                rmtree(self._path)
            except OSError:
                print >> sys.stderr, 'Unable to delete "%s"' % self._path
        else:
            raise Exception('"%s" not found' % self._path)


class ProfileCommands(object):
    def __init__(self, args, user_profile, global_profile):
        self.args = args
        self.user_profile = user_profile
        self.global_profile = global_profile

    def set(self):
        section = self.args.section
        option = self.args.option
        value = self.args.value
        if self.args.use_global_profile:
            self.global_profile.set(section, option, value)
            self.global_profile.save()
        else:
            self.user_profile.set(section, option, value)
            self.user_profile.save()

    def remove(self):
        section = self.args.section
        option = self.args.option
        if self.args.use_global_profile:
            self.global_profile.remove(section, option)
            self.global_profile.save()
        else:
            self.user_profile.remove(section, option)
            self.user_profile.save()

    def list(self):
        for profile in Profile.get_all():
            print profile

    def config(self):
        profile_name = self.args.profile
        if profile_name is None:
            if self.args.use_global_profile or self.user_profile is None:
                profile = self.global_profile
            else:
                profile = self.user_profile
        else:
            profile = Profile(profile_name)
        profile.config.write(sys.stdout)
        return None

    def clear(self):
        for profile_name in self.args.profiles:
            profile = Profile(profile_name)
            profile.clear()
            #todo: clear a non-existed profile will be Error:

    def login(self):
        if self.args.profile_name is None:
            consumer_key, consumer_secret, token_key, token_secret = \
                get_consumer_and_token(None, self.global_profile)
            api = twitter.Api(
                consumer_key=consumer_key,
                consumer_secret=consumer_secret,
                access_token_key=token_key,
                access_token_secret=token_secret)
            user_profile = Profile(choose_profile_name(api.VerifyCredentials().screen_name),
                                   create_dir=True)
            user_profile.set('consumer', 'key', consumer_key)
            user_profile.set('consumer', 'secret', consumer_secret)
            user_profile.set('token', 'key', token_key)
            user_profile.set('token', 'secret', token_secret)
            user_profile.save()
            self.global_profile.set('profile', 'default',
                                           user_profile.profile_name.lower())
            self.global_profile.save()
        elif self.args.profile_name in Profile.get_all():
            self.args.use_global_profile = True
            self.args.call = 'set'
            self.args.section = 'profile'
            self.args.option = 'default'
            self.args.value = self.args.profile_name
            self.call()
        else:
            raise Exception('profile "%s" doesn\'t exist' % \
                                self.args.profile_name)

    def call(self, function=None):
        if function is None:
            getattr(self, self.args.call)()
        else:
            getattr(self, function)()


class TwitterCommands(object):
    def __init__(self, api, args, user_config=None, global_config=None):
        self.api = api
        self.args = args
        self.user_config = user_config
        self.global_config = global_config

    def _print_user(self, user):
        user = user.AsDict()
        format = self.args.specified_format or \
            self.user_config.get('format', 'user') or \
            self.global_config.get('format', 'user') or \
            PTWIT_FORMAT_USER
        print format_dictionary(format, user).encode('utf-8')

    def _print_users(self, users):
        for user in users:
            self._print_user(user)

    def _print_tweet(self, tweet):
        tweet = tweet.AsDict()
        format = self.args.specified_format or \
            self.user_config.get('format', 'tweet') or \
            self.global_config.get('format', 'tweet') or \
            PTWIT_FORMAT_TWEET
        print format_dictionary(
            format, tweet,
            date=strptime(tweet['created_at'],
                          '%a %b %d %H:%M:%S +0000 %Y')).encode('utf-8')

    def _print_tweets(self, tweets):
        for tweet in tweets:
            self._print_tweet(tweet)

    def _print_search(self, tweet):
        tweet = tweet.AsDict()
        format = self.args.specified_format or \
            self.user_config.get('format', 'tweet') or \
            self.global_config.get('format', 'tweet') or \
            PTWIT_FORMAT_TWEET
        print format_dictionary(
            format, tweet,
            date=strptime(tweet['created_at'], '%a, %d %b %Y %H:%M:%S +0000'))

    def _print_searches(self, tweets):
        for tweet in tweets:
            self._print_search(tweet)

    def _print_message(self, message):
        message = message.AsDict()
        format = self.args.specified_format or \
            self.user_config.get('format', 'message') or \
            self.global_config.get('format', 'tweet') or \
            PTWIT_FORMAT_MESSAGE
        print format_dictionary(
            format, message,
            date=strptime(message['created_at'],
                          '%a %b %d %H:%M:%S +0000 %Y')).encode('utf-8')

    def _print_messages(self, messages):
        for message in messages:
            self._print_message(message)

    def public(self):
        self._print_tweets(self.api.GetPublicTimeline())

    def post(self):
        if len(self.args.post):
            post = ' '.join(self.args.post)
        else:
            post = sys.stdin.read()
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
                since_id=self.user_config.get('since', 'timeline'))
        else:
            tweets = self.api.GetFriendsTimeline(
                page=self.args.page,
                count=self.args.count)
        self._print_tweets(tweets)
        if len(tweets):
            self.user_config.set('since', 'timeline', tweets[0].id)
            self.user_config.save()

    def mentions(self):
        if self.args.count is None and self.args.page is None:
            tweets = self.api.GetMentions(
                since_id=self.user_config.get('since', 'mentions'),
                page=self.args.page)
        else:
            tweets = self.api.GetMentions(
                # todo: twitter.GetMentions doesn't support count parameter right now
                # count=self.args.count,
                page=self.args.page)
        self._print_tweets(tweets)
        if len(tweets):
            self.user_config.set('since', 'mentions', tweets[0].id)
            self.user_config.save()

    def replies(self):
        if self.args.count is None and self.args.page is None:
            tweets = self.api.GetReplies(
                since_id=self.user_config.get('since', 'replies'),
                page=self.args.page)
        else:
            tweets = self.api.GetReplies(
                # count=self.args.count,
                page=self.args.page)
        self._print_tweets(tweets)
        if len(tweets):
            self.user_config.set('since', 'replies', tweets[0].id)
            self.user_config.save()

    def messages(self):
        if self.args.count is None and self.args.page is None:
            messages = self.api.GetDirectMessages(
                since_id=self.user_config.get('since', 'messages'),
                page=self.args.page)
        else:
            messages = self.api.GetDirectMessages(
                page=self.args.page)
        self._print_messages(messages)
        if len(messages):
            self.user_config.set('since', 'messages', messages[0].id)
            self.user_config.save()

    def send(self):
        user = self.args.user
        if len(self.args.message):
            message = ' '.join(self.args.message)
        else:
            message = sys.stdin.read()
        self._print_message(self.api.PostDirectMessage(user, message))

    def friends(self):
        self._print_users(self.api.GetFriends(self.args.user))

    def followers(self):
        self._print_users(self.api.GetFollowers(page=self.args.page))

    def follow(self):
        user = self.api.CreateFriendship(self.args.user)
        print 'you have requested to follow @%s' % user.screen_name

    def unfollow(self):
        user = self.api.DestroyFriendship(self.args.user)
        print 'you have unfollowed @%s' % user.screen_name

    def faves(self):
        self._print_tweets(self.api.GetFavorites(user=self.args.user,
                                                 page=self.args.page))

    def search(self):
        tweets = self.api.GetSearch(term=' '.join(self.args.term))
        self._print_searches(tweets)

    def whois(self):
        users = [self.api.GetUser(user) for user in self.args.users]
        self._print_users(users)

    def call(self, function):
        getattr(self, function)()


def parse_args(argv):
    parser = argparse.ArgumentParser(description='Twitter command-line.',
                                     prog=os.path.basename(__file__))
    parser.add_argument('-p', dest='specified_profile', metavar='profile',
                        action='store', help='specify a profile')
    parser.add_argument('-f', dest='specified_format', metavar='format',
                        help='print format')
    # todo: default command
    # twitter commands
    subparsers = parser.add_subparsers(title='twitter commands')
    # login
    p = subparsers.add_parser('login', help='login')
    p.add_argument('profile_name', nargs='?')
    p.set_defaults(type=ProfileCommands, function='login')
    # public
    p = subparsers.add_parser('public', help='list public timeline')
    p.set_defaults(type=TwitterCommands, function='public')
    # friends
    p = subparsers.add_parser('friends', help='list friends')
    p.add_argument('user', nargs='?')
    p.set_defaults(type=TwitterCommands, function='friends')
    # followers
    p = subparsers.add_parser('followers', help='list followers')
    p.add_argument('-p', dest='page', type=int)
    p.set_defaults(type=TwitterCommands, function='followers')
    # follow
    p = subparsers.add_parser('follow', help='follow someone')
    p.add_argument('user')
    p.set_defaults(type=TwitterCommands, function='follow')
    # unfollow
    p = subparsers.add_parser('unfollow', help='unfollow someone')
    p.add_argument('user')
    p.set_defaults(type=TwitterCommands, function='unfollow')
    # tweets
    p = subparsers.add_parser('tweets', help='list tweets')
    p.add_argument('-c', dest='count', type=int)
    p.add_argument('-p', dest='page', type=int)
    p.add_argument('user', nargs='?')
    p.set_defaults(type=TwitterCommands, function='tweets')
    # timeline
    p = subparsers.add_parser('timeline', help='list friends timeline')
    p.add_argument('-c', dest='count', type=int)
    p.add_argument('-p', dest='page', type=int)
    p.set_defaults(type=TwitterCommands, function='timeline')
    # faves
    p = subparsers.add_parser('faves', help='list favourites')
    p.add_argument('-p', dest='page', type=int)
    p.add_argument('user', nargs='?')
    p.set_defaults(type=TwitterCommands, function='faves')
    # post
    p = subparsers.add_parser('post', help='post a tweet')
    p.add_argument('post', nargs='*')
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
    p.add_argument('user')
    p.add_argument('message', nargs='*')
    p.set_defaults(type=TwitterCommands, function='send')
    # replies
    p = subparsers.add_parser('replies', help='list replies')
    p.add_argument('-p', dest='page', type=int)
    p.add_argument('-c', dest='count', type=int)
    p.set_defaults(type=TwitterCommands, function='replies')
    # whois
    p = subparsers.add_parser('whois', help='show user information')
    p.add_argument('users', nargs='+')
    p.set_defaults(type=TwitterCommands, function='whois')
    # search
    p = subparsers.add_parser('search', help='search twitter')
    p.add_argument('term', nargs='+')
    p.set_defaults(type=TwitterCommands, function='search')
    # profile commands
    profile_parser = subparsers.add_parser('profile', help='manage profiles')
    profile_parser.add_argument('-g', action='store_true',
                                dest='use_global_profile',
                                help='apply global configuration only')
    profile_subparsers = profile_parser.add_subparsers(title='profile',
                                                       help='profile commands')
    # todo default profile command
    # profile set
    p = profile_subparsers.add_parser('set', help='set option')
    p.add_argument('section')
    p.add_argument('option')
    p.add_argument('value')
    p.set_defaults(type=ProfileCommands, function='set')
    # profile remove
    p = profile_subparsers.add_parser('remove', help='remove option')
    p.add_argument('section')
    p.add_argument('option', nargs='?')
    p.set_defaults(type=ProfileCommands, function='remove')
    # profile list
    p = profile_subparsers.add_parser('list', help='list profiles')
    p.set_defaults(type=ProfileCommands, function='list')
    # profile config
    p = profile_subparsers.add_parser('config',
                                      help='show a profile\'s configurations')
    p.add_argument('profile', nargs='?')
    p.set_defaults(type=ProfileCommands, function='config')
    # profile clear
    p = profile_subparsers.add_parser('clear', help='clear profiles')
    p.add_argument('profiles', nargs='+')
    p.set_defaults(type=ProfileCommands, function='clear')
    return parser.parse_args(argv)


def get_consumer_and_token(user_profile, global_profile):
    if user_profile is None:
        consumer_key = global_profile.get('consumer', 'key')
        consumer_secret = global_profile.get('consumer', 'secret')
        token_key = None
        token_secret = None
    else:
        consumer_key = user_profile.get('consumer', 'key') or \
            global_profile.get('consumer', 'key')
        consumer_secret = user_profile.get('consumer', 'secret') or \
            global_profile.get('consumer', 'secret')
        token_key = user_profile.get('token', 'key')
        token_secret = user_profile.get('token', 'secret')
    try:
        # login
        if not (consumer_key and consumer_secret):
            consumer_key, consumer_secret = get_consumer()
        if not (token_key and token_secret):
            token_key, token_secret = get_oauth(consumer_key, consumer_secret)
    except (KeyboardInterrupt, EOFError):
        sys.exit(0)
    return consumer_key, consumer_secret, token_key, token_secret


def choose_profile_name(default_name):
    while True:
        try:
            profile_name = raw_input('Enter a profile name (%s): ' % \
                                         default_name).strip()
        except KeyboardInterrupt:
            sys.exit(0)
        if not profile_name:
            profile_name = default_name
        if profile_name in Profile.get_all():
            print >> sys.stderr, \
                'The profile "%s" exists' % profile_name
        elif profile_name:
            break
    return profile_name


def main(argv):
    args = parse_args(argv)
    global_profile = Profile(create_dir=True)
    user_profile_name = args.specified_profile or \
        global_profile.get('profile', 'default')
    user_profile = None if user_profile_name is None \
        else Profile(user_profile_name)
    if args.type == ProfileCommands:
        commands = ProfileCommands(args, user_profile, global_profile)
        commands.call(args.function)
        sys.exit(0)
    consumer_key, consumer_secret, token_key, token_secret = \
        get_consumer_and_token(user_profile, global_profile)
    api = twitter.Api(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token_key=token_key,
        access_token_secret=token_secret)
    if not user_profile:
        user_profile = Profile(choose_profile_name(api.VerifyCredentials().screen_name),
                               create_dir=True)
    global_profile.set('profile', 'default',
                              user_profile.profile_name.lower())
    user_profile.set('consumer', 'key', consumer_key)
    user_profile.set('consumer', 'secret', consumer_secret)
    user_profile.set('token', 'key', token_key)
    user_profile.set('token', 'secret', token_secret)
    user_profile.save()
    global_profile.save()
    if args.type == TwitterCommands:
        commands = TwitterCommands(api, args, user_profile, global_profile)
        commands.call(args.function)
    else:
        raise Exception('Invalid command')

if __name__ == '__main__':
    #todo: handle encoded text
    try:
        main(sys.argv[1:])
    except Exception as e:
        print >> sys.stderr, 'Error: ' + e.message
        sys.exit(1)
    sys.exit(0)
