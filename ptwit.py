#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division, print_function

__version__ = '0.0.9'
__author__ = 'Tao Peng'
__license__ = 'MIT'
__copyright__ = 'Copyright (c) 2012-2015 Tao Peng'

import sys
import os
import time
import argparse
try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser
try:
    from HTMLParser import HTMLParser
except ImportError:
    import html.parser as HTMLParser
from datetime import datetime
from string import Formatter
try:
    from urlparse import parse_qsl
except ImportError:
    from urllib.parse import parse_qsl
import webbrowser

import twitter


MAX_COUNT = 200

CONFIG_FILE = os.path.expanduser('~/.ptwitrc')

FORMAT_TWEET = u'''\t\033[7m {user[name]} \033[0m (@{user[screen_name]})
\t{text}
\t\033[35m{from_now}\033[0m
'''

FORMAT_SEARCH = u'''\t\033[7m {user[screen_name]} \033[0m
\t{text}
\t\033[35m{from_now}\033[0m
'''

FORMAT_MESSAGE = u'''\t\033[7m {sender_screen_name} \033[0m
\t{text}
\t\033[35m{from_now}\033[0m
'''

FORMAT_USER = u'''\033[7m {name} \033[0m (@{screen_name})
Location:     {location}
URL:          {url}
Followers:    {followers_count}
Following:    {friends_count}
Status:       {statuses_count}
Description:  {description}
Joined on:    {0:%Y-%m-%d} ({from_now})
'''

REQUEST_TOKEN_URL = 'https://api.twitter.com/oauth/request_token'
AUTHORIZATION_URL = 'https://api.twitter.com/oauth/authenticate'
ACCESS_TOKEN_URL = 'https://api.twitter.com/oauth/access_token'


class DefaultFormatter(Formatter):
    def get_value(self, key, args, kwargs):
        # Try standard formatting, if key not found then return None
        try:
            return Formatter.get_value(self, key, args, kwargs)
        except KeyError:
            return None


class AuthorizationError(Exception):
    """Application error."""
    pass


def oauthlib_fetch_access_token(client_key, client_secret):
    """Fetch twitter access token using oauthlib."""
    # fetch request token
    oauth = OAuth1Session(client_key, client_secret=client_secret)
    fetch_response = oauth.fetch_request_token(REQUEST_TOKEN_URL)
    resource_owner_key = fetch_response.get('oauth_token')
    resource_owner_secret = fetch_response.get('oauth_token_secret')
    # authorization
    authorization_url = oauth.authorization_url(AUTHORIZATION_URL)
    print('Opening: ', authorization_url)
    webbrowser.open_new_tab(authorization_url)
    time.sleep(1)
    pincode = raw_input('Enter the pincode: ')
    oauth = OAuth1Session(client_key,
                          client_secret=client_secret,
                          resource_owner_key=resource_owner_key,
                          resource_owner_secret=resource_owner_secret,
                          verifier=pincode)
    # fetch access token
    oauth_tokens = oauth.fetch_access_token(ACCESS_TOKEN_URL)
    return oauth_tokens.get('oauth_token'), oauth_tokens.get('oauth_token_secret')


def oauth2_fetch_access_token(consumer_key, consumer_secret):
    """Fetch twitter access token using oauth2."""
    oauth_consumer = oauth2.Consumer(key=consumer_key, secret=consumer_secret)
    oauth_client = oauth2.Client(oauth_consumer)
    # get request token
    resp, content = oauth_client.request(REQUEST_TOKEN_URL)
    if resp['status'] != '200':
        raise AuthorizationError(
            'Invalid respond from Twitter requesting temp token: {0}'.format(resp['status'])
        )
    request_token = dict(parse_qsl(content))
    # authorization
    authorization_url = '{url}?oauth_token={token}'.format(
        url=AUTHORIZATION_URL,
        token=request_token['oauth_token'])
    print('Opening: ', authorization_url)
    webbrowser.open_new_tab(authorization_url)
    time.sleep(1)
    pincode = raw_input('Enter the pincode: ')
    # fetch access token
    token = oauth2.Token(request_token['oauth_token'],
                         request_token['oauth_token_secret'])
    token.set_verifier(pincode)
    oauth_client = oauth2.Client(oauth_consumer, token)
    resp, content = oauth_client.request(ACCESS_TOKEN_URL,
                                         method='POST',
                                         body='oauth_verifier=%s' % pincode)
    access_token = dict(parse_qsl(content))
    if resp['status'] != '200':
        raise AuthorizationError(
            'The request for a Token did not succeed: {0}'.format(resp['status']))
    else:
        return access_token['oauth_token'], access_token['oauth_token_secret']


try:
    import oauth2 as oauth2
    fetch_access_token = oauth2_fetch_access_token
except ImportError:
    from requests_oauthlib import OAuth1Session
    fetch_access_token = oauthlib_fetch_access_token


def from_now(time):
    """Return a human-readable relative time from now."""

    diff = datetime.utcnow() - time

    # -999999999 <= days <= 999999999
    if diff.days == 1:
        return '1 day ago'
    elif diff.days > 1:
        return '%d days ago' % diff.days

    # Equivalent to (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6
    # Negative value means the time is in the future
    elif diff.total_seconds() < 0:
        return 'just now'

    # 0 <= seconds < 3600*24 (the number of seconds in one day)
    elif diff.seconds < 60:
        return 'just now'
    elif diff.seconds // 60 == 1:
        return '1 minute ago'
    elif diff.seconds < 3600:
        return '%d minutes ago' % (diff.seconds // 60)

    elif diff.seconds // 3600 == 1:
        return '1 hour ago'
    else:
        return '%d hours ago' % (diff.seconds // 3600)


class PtwitConfig(object):
    def __init__(self, filename):
        self.filename = filename
        self.config = ConfigParser.RawConfigParser()
        # create file if not exists
        if not os.path.exists(self.filename):
            open(self.filename, 'w').close()
        with open(self.filename) as fp:
            self.config.readfp(fp)

    def get(self, option, account=None, default=None):
        section = account or 'general'
        try:
            return self.config.get(section, option)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            return default

    def set(self, option, value, account=None):
        section = account or 'general'
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, option, value)
        return self

    def unset(self, option, account=None):
        section = account or 'general'
        self.config.remove_option(section, option)
        if len(self.config.items(section)) == 0:
            self.config.remove_section(section)
        return self

    def remove_account(self, account):
        section = account or 'general'
        self.config.remove_section(section)
        return self

    def list_accounts(self):
        return [section for section in self.config.sections() if section != 'general']

    def save(self, filename=None):
        filename = filename or self.filename
        with open(filename, 'w') as fp:
            self.config.write(fp)


class ConfigCommands(object):
    def __init__(self, args, config, account):
        self.args = args
        self.config = config
        self.account = account

    def set(self):
        """Command: set OPTION VALUE"""
        account = None if self.args.g else self.account
        self.config.set(self.args.option, self.args.value, account=account)
        self.config.save()

    def unset(self):
        """Command: unset OPTION..."""
        account = None if self.args.g else self.account
        for option in self.args.options:
            self.config.unset(option, account=account)
        self.config.save()

    def accounts(self):
        """List all accounts."""
        for config in self.config.list_accounts():
            print(config)

    def get(self):
        """Command: get OPTION..."""
        account = None if self.args.g else self.account
        if self.args.options:
            for option in self.args.options:
                value = self.config.get(option, account=account)
                if value:
                    print(value)
                else:
                    print('Option "%s" is not found.' % option, file=sys.stderr)
        else:
            self.config.config.write(sys.stdout)

    def remove(self):
        """Command: remove account..."""
        for account in self.args.accounts:
            if account in self.config.list_accounts():
                self.config.remove_account(account)
            else:
                print('Account "%s" doesn\'t exist.' % account, file=sys.stderr)
        self.config.save()

    def login(self):
        """Command: login [ACCOUNT]"""
        if self.args.account:
            self.config.set('default_account', self.args.account)
            self.config.save()
        else:
            login(self.config, None)

    def call(self, function=None):
        if function is None:
            getattr(self, self.args.call)()
        else:
            getattr(self, function)()


class TwitterCommands(object):
    html_parser = HTMLParser()
    formatter = DefaultFormatter()

    def __init__(self, api, args, config, account):
        self.api = api
        self.args = args
        self.config = config
        self.account = account

    def _print_user(self, user):
        user = user.AsDict()
        created_at = datetime.strptime(
            user['created_at'],
            '%a %b %d %H:%M:%S +0000 %Y')
        format_string = self.args.format or \
            self.config.get('user_format', account=self.account) or \
            FORMAT_USER
        print(self.formatter.format(format_string,
                                    created_at,
                                    from_now=from_now(created_at),
                                    **user).encode('utf-8'))

    def _print_users(self, users):
        for user in users:
            self._print_user(user)

    def _print_tweet(self, tweet):
        tweet = tweet.AsDict()
        tweet['text'] = self.html_parser.unescape(tweet['text'])
        format_string = self.args.format or \
            self.config.get('tweet_format', account=self.account) or \
            FORMAT_TWEET
        created_at = datetime.strptime(
            tweet['created_at'],
            '%a %b %d %H:%M:%S +0000 %Y')
        print(self.formatter.format(format_string,
                                    created_at,
                                    from_now=from_now(created_at),
                                    **tweet).encode('utf-8'))

    def _print_tweets(self, tweets):
        for tweet in tweets:
            self._print_tweet(tweet)

    def _print_search(self, tweet):
        tweet = tweet.AsDict()
        tweet['text'] = self.html_parser.unescape(tweet['text'])
        format_string = self.args.format or \
            self.config.get('search_format', account=self.account) or \
            FORMAT_SEARCH
        created_at = datetime.strptime(
            tweet['created_at'],
            '%a %b %d %H:%M:%S +0000 %Y')
        print(self.formatter.format(format_string,
                                    created_at,
                                    from_now=from_now(created_at),
                                    **tweet).encode('utf-8'))

    def _print_searches(self, tweets):
        for tweet in tweets:
            self._print_search(tweet)

    def _print_message(self, message):
        message = message.AsDict()
        format_string = self.args.format or \
            self.config.get('message_format', account=self.account) or \
            FORMAT_MESSAGE
        created_at = datetime.strptime(
            message['created_at'],
            '%a %b %d %H:%M:%S +0000 %Y')
        print(self.formatter.format(format_string,
                                    created_at,
                                    from_now=from_now(created_at),
                                    **message).encode('utf-8'))

    def _print_messages(self, messages):
        for message in messages:
            self._print_message(message)

    def post(self):
        if len(self.args.post):
            post = ' '.join(self.args.post)
        else:
            post = sys.stdin.read()
        # convert to unicode
        post = post.decode('utf-8')
        self._print_tweet(self.api.PostUpdate(post))

    def tweets(self):
        # todo: since_id here
        tweets = self.api.GetUserTimeline(
            screen_name=self.args.user,
            count=self.args.count)
        self._print_tweets(tweets)

    def default(self):
        self.timeline()

    def timeline(self):
        if self.args.count is None:
            tweets = self.api.GetHomeTimeline(
                count=MAX_COUNT,
                since_id=self.config.get('timeline_since', account=self.account))
        else:
            tweets = self.api.GetHomeTimeline(count=self.args.count)
        self._print_tweets(tweets)
        if len(tweets):
            self.config.set('timeline_since', tweets[0].id, account=self.account)
            self.config.save()

    def mentions(self):
        if self.args.count is None:
            tweets = self.api.GetMentions(
                count=MAX_COUNT,
                since_id=self.config.get('mentions_since', account=self.account))
        else:
            tweets = self.api.GetMentions(count=self.args.count)
        self._print_tweets(tweets)
        if len(tweets):
            self.config.set('mentions_since', tweets[0].id, account=self.account)
            self.config.save()

    def replies(self):
        if self.args.count is None:
            tweets = self.api.GetReplies(
                count=MAX_COUNT,
                since_id=self.config.get('replies_since', account=self.account))
        else:
            tweets = self.api.GetReplies(count=self.args.count)
        self._print_tweets(tweets)
        if len(tweets):
            self.config.set('replies_since', tweets[0].id, account=self.account)
            self.config.save()

    def messages(self):
        if self.args.count is None:
            messages = self.api.GetDirectMessages(
                count=MAX_COUNT,
                since_id=self.config.get('messages_since', account=self.account))
        else:
            messages = self.api.GetDirectMessages(count=self.args.count)
        self._print_messages(messages)
        if len(messages):
            self.config.set('messages_since', messages[0].id, account=self.account)
            self.config.save()

    def send(self):
        user = self.args.user
        if len(self.args.message):
            message = ' '.join(self.args.message)
        else:
            message = sys.stdin.read()
        # convert to unicode
        message = message.decode('utf-8')
        self._print_message(self.api.PostDirectMessage(message, screen_name=user))

    def followings(self):
        # todo: list followings who is following you, too
        self._print_users(self.api.GetFriends(self.args.user))

    def followers(self):
        # todo: list followers who you follows, too
        if self.args.user:
            user = self.api.GetUser(self.args.user)
            self._print_users(self.api.GetFollowers(user=user))
        else:
            self._print_users(self.api.GetFollowers())

    def follow(self):
        user = self.api.CreateFriendship(self.args.user)
        print('You have requested to follow @%s' % user.screen_name)

    def unfollow(self):
        user = self.api.DestroyFriendship(self.args.user)
        print('You have unfollowed @%s' % user.screen_name)

    def faves(self):
        tweets = self.api.GetFavorites(screen_name=self.args.user)
        self._print_tweets(tweets)

    def search(self):
        term = ' '.join(self.args.term)
        # convert to unicode
        term = term.decode('utf-8')
        tweets = self.api.GetSearch(term=term)
        self._print_searches(tweets)

    def whois(self):
        users = [self.api.GetUser(screen_name=user) for user in self.args.users]
        self._print_users(users)

    def call(self, function):
        getattr(self, function)()


def parse_args(argv):
    """Parse command arguments."""

    parser = argparse.ArgumentParser(description='Twitter command-line.', prog='ptwit')

    # global options
    parser.add_argument('-a', dest='specified_account', metavar='ACCOUNT',
                        action='store', help='specify a account')
    parser.add_argument('-f', dest='format', metavar='FORMAT',
                        help='print format')

    # todo: default command

    #### twitter commands
    subparsers = parser.add_subparsers(title='twitter commands')

    # login
    p = subparsers.add_parser('login', help='login')
    p.add_argument('account', nargs='?', metavar='ACCOUNT')
    p.set_defaults(type=ConfigCommands, function='login')

    # public
    # p = subparsers.add_parser('public', help='list public timeline')
    # p.set_defaults(type=TwitterCommands, function='public')

    # followings
    p = subparsers.add_parser('followings', help='list followings')
    p.add_argument('user', nargs='?', metavar='USER')
    p.set_defaults(type=TwitterCommands, function='followings')

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

    #### config commands
    config_parser = subparsers.add_parser('config', help='manage config')
    config_parser.add_argument('-g', action='store_true', dest='g',
                               help='apply global configuration only')
    pp = config_parser.add_subparsers(title='config', help='config commands')

    # config set
    p = pp.add_parser('set', help='set option')
    p.add_argument('option', metavar='OPTION')
    p.add_argument('value', metavar='VALUE')
    p.set_defaults(type=ConfigCommands, function='set')

    # config get
    p = pp.add_parser('get', help='get options')
    p.add_argument('options', metavar='OPTION', nargs='*')
    p.set_defaults(type=ConfigCommands, function='get')

    # config unset
    p = pp.add_parser('unset', help='unset options')
    p.add_argument('options', metavar='OPTION', nargs='+')
    p.set_defaults(type=ConfigCommands, function='unset')

    # config list all accounts
    p = pp.add_parser('accounts', help='list all accounts')
    p.set_defaults(type=ConfigCommands, function='accounts')

    # config remove accounts
    p = pp.add_parser('remove', help='remove accounts')
    p.add_argument('accounts', nargs='+', metavar='ACCOUNT')
    p.set_defaults(type=ConfigCommands, function='remove')

    return parser.parse_args(argv)


def choose_config_name(default, config):
    """Prompt for choosing config name."""

    name = default

    while True:
        try:
            name = raw_input('Enter a config name (%s): ' % default).strip()
        except KeyboardInterrupt:
            sys.exit(10)
        if not name:
            name = default
        if name in config.list_accounts():
            print('Cannot create config "{name}": config exists'.format(name=name), file=sys.stderr)
        elif name:
            break

    return name


def login(config, account):
    consumer_key = config.get('consumer_key', account=account) \
        or config.get('consumer_key')
    consumer_secret = config.get('consumer_secret', account=account) \
        or config.get('consumer_secret')
    token_key = config.get('token_key', account=account)
    token_secret = config.get('token_secret', account=account)
    if not (consumer_key and consumer_secret):
        consumer_key = raw_input('Consumer key: ').strip()
        consumer_secret = raw_input('Consumer secret: ').strip()
    if not (token_key and token_secret):
        token_key, token_secret = fetch_access_token(consumer_key, consumer_secret)
    api = twitter.Api(consumer_key=consumer_key,
                      consumer_secret=consumer_secret,
                      access_token_key=token_key,
                      access_token_secret=token_secret)
    if not account:
        user = api.VerifyCredentials()
        account = choose_config_name(user.screen_name, config)
        config.set('default_account', account)
    if not config.get('consumer_key'):
        config.set('consumer_key', consumer_key)
    if config.get('consumer_key', account=account):
        config.set('consumer_key', consumer_key, account=account)
    if not config.get('consumer_secret'):
        config.set('consumer_secret', consumer_secret)
    if config.get('consumer_secret', account=account):
        config.set('consumer_secret', consumer_secret, account=account)
    config.set('token_key', token_key, account=account)
    config.set('token_secret', token_secret, account=account)
    config.save()
    return api


def main(argv=None):
    """Parse arguments and issue commands."""
    if argv is None:
        argv = sys.argv[1:]
    args = parse_args(argv)
    config = PtwitConfig(CONFIG_FILE)
    account = args.specified_account or config.get('default_account')
    if args.type == ConfigCommands:
        commands = ConfigCommands(args, config, account)
        commands.call(args.function)
        return 0
    api = login(config, account)
    assert args.type == TwitterCommands
    commands = TwitterCommands(api, args, config, account)
    commands.call(args.function)
    return 0


def cmd():
    try:
        status = main()
    except twitter.TwitterError as err:
        print('Twitter Error (code {0}): {1}'.format(err['code'], err['message']),
              file=sys.stderr)
        status = 1
    except AuthorizationError as err:
        print('Authorization Error: {0}'.format(err.message),
              file=sys.stderr)
        status = 2
    except KeyboardInterrupt:
        status = 3
    sys.exit(status)


if __name__ == '__main__':
    cmd()
