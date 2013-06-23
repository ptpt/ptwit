#!/usr/bin/env python

import sys
import os
import time
import twitter
import argparse
import ConfigParser
from HTMLParser import HTMLParser
from datetime import datetime


PROFILE_DIR = os.path.expanduser('~/.ptwit')

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
                # it's open persent sign
                state = i + 1
            else:
                # it's close persent sign
                tag = template[state:i]
                if tag == '':
                    # if two persent signs found together,
                    # replace them with a single persent sign
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
                # remember to mark persent sign state as closed
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


class ProfileError(Exception):
    """ Profile error """

    pass


class Profile(object):
    profile_root = PROFILE_DIR
    _global = None

    def __init__(self, name=None):
        self.name = name
        conf_dir = os.path.join(Profile.profile_root, name or '')
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
        """ Get the unique global profile instance. """
        if cls._global is None:
            cls._global = Profile()
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
        """ Return the value of sepcified option. """
        try:
            return self.config.get(section, option)
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            return None

    @classmethod
    def get_all(cls):
        """ Return all configurations. """
        if os.path.isdir(cls.profile_root):
            return [profile for profile in os.listdir(cls.profile_root)
                    if os.path.isdir(os.path.join(cls.profile_root, profile))
                    and not profile.startswith('.')]
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
            raise ProfileError('Profile "%s" doesn\'t exist.' % config_folder)


class ProfileCommandsError(Exception):
    """ ProfileCommands error. """
    pass


class ProfileCommands(object):
    def __init__(self, args, profile):
        self.args = args
        self.profile = profile

    def set(self):
        """ Command: set SECTION.OPTION VALUE """
        profile = Profile.get_global() if self.args.g else self.profile
        try:
            section, option = self.args.option.split('.', 1)
        except ValueError:
            raise ProfileCommandsError(
                'You must specify a option like this "SECTION.OPTION".')
        value = self.args.value
        if self.args.g and section.lower() == 'profile' and \
                option.lower() == 'default':
            if value not in Profile.get_all():
                raise ProfileCommandsError(
                    'Profile %s doesn\'t exist.' % value)
        profile.set(section, option, value)
        profile.save()

    def unset(self):
        """ Command: unset SECTION.OPTION [SECTION.OPTION ...] """
        profile = Profile.get_global() if self.args.g else self.profile
        pack = [v.split('.', 1) for v in self.args.option]
        for option in pack:
            if len(option) == 1:
                profile.unset(option[0], None)
            elif len(option) == 2:
                profile.unset(option[0], option[1])
        profile.save()

    def all(self):
        """ List all profiles. """
        for profile in Profile.get_all():
            print profile

    def get(self):
        """ Command: get SECTION.OPTION """
        profile = Profile.get_global() if self.args.g else self.profile
        nonexist = False
        if self.args.option:
            pack = [v.split('.', 1) for v in self.args.option]
            try:
                for section, option in pack:
                    value = profile.get(section, option)
                    if value is None:
                        print >> sys.stderr, \
                            '"%s.%s" is not found.' % (section, option)
                        nonexist = True
                    else:
                        print value
            except ValueError:
                raise ProfileCommandsError(
                    'You must specify a option like this "SECTION.OPTION".')
        else:
            profile.config.write(sys.stdout)
        if nonexist:
            raise ProfileCommandsError('Some options is not found.')

    def remove(self):
        """ Command: remove PROFILE """
        nonexist = False
        for name in self.args.profile:
            if name in Profile.get_all():
                profile = Profile(name)
                profile.clear()
            else:
                print >> sys.stderr, 'Profile "%s" doesn\'t exist.' % name
                nonexist = True
        if nonexist:
            raise ProfileCommandsError('Some profiles doesn\'t exist.')

    def login(self):
        """ Command: login [PROFILE] """
        if not self.args.profile_name:
            global_profile = Profile.get_global()

            ckey, csecret, tkey, tsecret = \
                get_consumer_and_token(global_profile)
            api = twitter.Api(consumer_key=ckey,
                              consumer_secret=csecret,
                              access_token_key=tkey,
                              access_token_secret=tsecret)
            user_profile_name = \
                choose_profile_name(api.VerifyCredentials().screen_name)
            user_profile = Profile(user_profile_name)
            global_profile.set('profile', 'default', user_profile_name.lower())

            # set consumer pairs both in the user profile and global profile
            if not global_profile.get('consumer', 'key'):
                global_profile.set('consumer', 'key', ckey)
            user_profile.set('consumer', 'key', ckey)
            if not global_profile.get('consumer', 'secret'):
                global_profile.set('consumer', 'secret', csecret)
            user_profile.set('consumer', 'secret', csecret)

            # set token pairs
            user_profile.set('token', 'key', tkey)
            user_profile.set('token', 'secret', tsecret)

            # save profiles
            user_profile.save()
            global_profile.save()

        elif self.args.profile_name in Profile.get_all():
            # login the existing profile
            self.args.g = True
            self.args.call = 'set'
            self.args.option = 'profile.default'
            self.args.value = self.args.profile_name
            self.call()
        else:
            raise ProfileCommandsError('profile "%s" doesn\'t exist' %
                                       self.args.profile_name)

    def call(self, function=None):
        if function is None:
            getattr(self, self.args.call)()
        else:
            getattr(self, function)()


class TwitterCommands(object):
    html_parser = HTMLParser()

    def __init__(self, api, args, profile):
        self.api = api
        self.args = args
        self.profile = profile

    def _print_user(self, user):
        user = user.AsDict()
        template = self.args.specified_format or \
            self.profile.get('format', 'user') or \
            FORMAT_USER
        print render_template(template, user).encode('utf-8')

    def _print_users(self, users):
        for user in users:
            self._print_user(user)

    def _print_tweet(self, tweet):
        tweet = tweet.AsDict()
        tweet['text'] = self.html_parser.unescape(tweet['text'])
        template = self.args.specified_format or \
            self.profile.get('format', 'tweet') or \
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
            self.profile.get('format', 'search') or \
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
            self.profile.get('format', 'message') or \
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
            count=self.args.count)
        self._print_tweets(tweets)

    def default(self):
        self.timeline()

    def timeline(self):
        if self.args.count is None:
            tweets = self.api.GetHomeTimeline(
                since_id=self.profile.get('since', 'timeline'))
        else:
            tweets = self.api.GetHomeTimeline(count=self.args.count)
        self._print_tweets(tweets)
        if len(tweets):
            self.profile.set('since', 'timeline', tweets[0].id)
            self.profile.save()

    def mentions(self):
        if self.args.count is None:
            tweets = self.api.GetMentions(
                since_id=self.profile.get('since', 'mentions'))
        else:
            tweets = self.api.GetMentions(
                # todo: twitter.GetMentions doesn't support count parameter
                count=self.args.count,
            )
        self._print_tweets(tweets)
        if len(tweets):
            self.profile.set('since', 'mentions', tweets[0].id)
            self.profile.save()

    def replies(self):
        if self.args.count is None:
            tweets = self.api.GetReplies(
                since_id=self.profile.get('since', 'replies'))
        else:
            tweets = self.api.GetReplies(
                # count=self.args.count,
            )
        self._print_tweets(tweets)
        if len(tweets):
            self.profile.set('since', 'replies', tweets[0].id)
            self.profile.save()

    def messages(self):
        if self.args.count is None:
            messages = self.api.GetDirectMessages(
                since_id=self.profile.get('since', 'messages'))
        else:
            messages = self.api.GetDirectMessages()
        self._print_messages(messages)
        if len(messages):
            self.profile.set('since', 'messages', messages[0].id)
            self.profile.save()

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
        self._print_tweets(self.api.GetFavorites(user=self.args.user))

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
    parser.add_argument('-f', dest='specified_format', metavar='format',
                        help='print format')

    # todo: default command

    # twitter commands
    subparsers = parser.add_subparsers(title='twitter commands')

    # login
    p = subparsers.add_parser('login', help='login')
    p.add_argument('profile_name', nargs='?', metavar='PROFILE')
    p.set_defaults(type=ProfileCommands, function='login')

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
    p.add_argument('user', nargs='?', metavar='USER')
    p.set_defaults(type=TwitterCommands, function='tweets')

    # timeline
    p = subparsers.add_parser('timeline', help='list friends timeline')
    p.add_argument('-c', dest='count', type=int)
    p.set_defaults(type=TwitterCommands, function='timeline')

    # faves
    p = subparsers.add_parser('faves', help='list favourites')
    p.add_argument('user', nargs='?', metavar='USER')
    p.set_defaults(type=TwitterCommands, function='faves')

    # post
    p = subparsers.add_parser('post', help='post a tweet')
    p.add_argument('post', nargs='*', metavar='TEXT')
    p.set_defaults(type=TwitterCommands, function='post')

    # mentions
    p = subparsers.add_parser('mentions', help='list mentions')
    p.add_argument('-c', dest='count', type=int)
    p.set_defaults(type=TwitterCommands, function='mentions')

    # messages
    p = subparsers.add_parser('messages', help='list messages')
    p.add_argument('-c', dest='count', type=int)
    p.set_defaults(type=TwitterCommands, function='messages')

    # send
    p = subparsers.add_parser('send', help='send direct message')
    p.add_argument('user', metavar='USER')
    p.add_argument('message', nargs='*', metavar='TEXT')
    p.set_defaults(type=TwitterCommands, function='send')

    # replies
    p = subparsers.add_parser('replies', help='list replies')
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

    # profile commands
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
    p.set_defaults(type=ProfileCommands, function='set')

    # profile get
    p = pp.add_parser('get', help='get option')
    p.add_argument('option', metavar='SECTION.OPTION', nargs='*')
    p.set_defaults(type=ProfileCommands, function='get')

    # profile unset
    p = pp.add_parser('unset', help='unset option')
    p.add_argument('option', metavar='SECTION.OPTION', nargs='+')
    p.set_defaults(type=ProfileCommands, function='unset')

    # profile list all
    p = pp.add_parser('all', help='list all profiles')
    p.set_defaults(type=ProfileCommands, function='all')

    # profile remove profiles
    p = pp.add_parser('remove', help='remove profiles')
    p.add_argument('profile', nargs='+', metavar='PROFILE')
    p.set_defaults(type=ProfileCommands, function='remove')

    return parser.parse_args(argv)


def get_consumer_and_token(profile):
    """Get consumer pairs and token pairs from profile or prompt."""

    global_profile = Profile.get_global()
    consumer_key = profile.get('consumer', 'key')

    # read consumer pairs from user profile, and then global profile
    if not consumer_key and not profile.is_global:
        consumer_key = global_profile.get('consumer', 'key')
    consumer_secret = profile.get('consumer', 'secret')
    if not consumer_secret and not profile.is_global:
        consumer_secret = global_profile.get('consumer', 'secret')
    token_key = profile.get('token', 'key')
    token_secret = profile.get('token', 'secret')

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


def choose_profile_name(default):
    """ Prompt for choosing profile name. """

    while True:
        try:
            name = raw_input(
                'Enter a profile name (%s): ' % default).strip()
        except KeyboardInterrupt:
            sys.exit(0)
        if not name:
            name = default
        if name in Profile.get_all():
            raise PtwitError('Profile "%s" exists.' % name)
        elif name:
            break
    return name


def main(argv):
    """ Parse arguments and issue commands. """

    args = parse_args(argv)

    global_profile = Profile.get_global()

    # get default user from global profile's default section
    user_profile_name = args.specified_profile or \
        global_profile.get('profile', 'default')
    user_profile = Profile(user_profile_name) if user_profile_name else None

    # if it is profile subcommands, them handle profile commands and quit
    if args.type == ProfileCommands:
        commands = ProfileCommands(args, user_profile or global_profile)
        commands.call(args.function)
        sys.exit(0)

    # try to get customer pairs and token pairs from profiles or prompt
    ckey, csecret, tkey, tsecret = \
        get_consumer_and_token(user_profile or global_profile)
    api = twitter.Api(
        consumer_key=ckey,
        consumer_secret=csecret,
        access_token_key=tkey,
        access_token_secret=tsecret)

    # if user profile not found, create it
    if not user_profile:
        user_profile_name = choose_profile_name(
            api.VerifyCredentials().screen_name)
        user_profile = Profile(user_profile_name)

    # if global profile's default section is empty, oh, you will be
    # the default user
    if not global_profile.get('profile', 'default'):
        global_profile.set('profile', 'default', user_profile_name)

    # set consumer pairs both in the user profile and global profile
    if not global_profile.get('consumer', 'key'):
        global_profile.set('consumer', 'key', ckey)
    user_profile.set('consumer', 'key', ckey)
    if not global_profile.get('consumer', 'secret'):
        global_profile.set('consumer', 'secret', csecret)
    user_profile.set('consumer', 'secret', csecret)

    # set token pairs in the user profile
    user_profile.set('token', 'key', tkey)
    user_profile.set('token', 'secret', tsecret)

    # save both profile
    user_profile.save()
    global_profile.save()

    # handle twitter comamnds
    if args.type == TwitterCommands:
        commands = TwitterCommands(api, args, user_profile)
        commands.call(args.function)
        sys.exit(0)


def cmd():
    try:
        main(sys.argv[1:])
    except (twitter.TwitterError, PtwitError,
            ProfileError, ProfileCommandsError) as err:
        print >> sys.stderr, 'Error: %s' % err.message
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    cmd()
