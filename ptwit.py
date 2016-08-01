#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import (division, print_function)

import sys
import os
from functools import update_wrapper
from datetime import datetime
from string import Formatter

try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser

try:
    # Python 2
    from HTMLParser import HTMLParser
    _parser = HTMLParser()
    html_unescape = _parser.unescape
except ImportError:
    # Python 3
    from html import unescape as html_unescape

try:
    from urlparse import parse_qsl
except ImportError:
    from urllib.parse import parse_qsl

import twitter as twitter_api
import click


__version__ = '0.0.9'
__author__ = 'Tao Peng'
__license__ = 'MIT'
__copyright__ = 'Copyright (c) 2012-2016 Tao Peng'


_MAX_COUNT = 200

_CONFIG_FILE = os.path.expanduser('~/.ptwitrc')

FORMAT_TWEET = u'''\t\033[7m {user[name]} \033[0m (@{user[screen_name]})
\t{text}
\t\033[35m{time_ago}\033[0m
'''

FORMAT_SEARCH = u'''\t\033[7m {user[screen_name]} \033[0m
\t{text}
\t\033[35m{time_ago}\033[0m
'''

FORMAT_MESSAGE = u'''\t\033[7m {sender_screen_name} \033[0m
\t{text}
\t\033[35m{time_ago}\033[0m
'''

FORMAT_USER = u'''\033[7m {name} \033[0m (@{screen_name})
Location:     {location}
URL:          {url}
Followers:    {followers_count}
Following:    {friends_count}
Status:       {statuses_count}
Description:  {description}
Joined:       {0:%Y-%m-%d} ({time_ago})
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

    # Fetch request token
    oauth = OAuth1Session(client_key, client_secret=client_secret)
    fetch_response = oauth.fetch_request_token(REQUEST_TOKEN_URL)
    resource_owner_key = fetch_response.get('oauth_token')
    resource_owner_secret = fetch_response.get('oauth_token_secret')

    # Authorization
    authorization_url = oauth.authorization_url(AUTHORIZATION_URL)
    click.echo('Opening {0}'.format(authorization_url))
    click.launch(authorization_url)
    pincode = click.prompt('Enter the pincode')
    oauth = OAuth1Session(client_key,
                          client_secret=client_secret,
                          resource_owner_key=resource_owner_key,
                          resource_owner_secret=resource_owner_secret,
                          verifier=pincode)

    # Fetch access token
    oauth_tokens = oauth.fetch_access_token(ACCESS_TOKEN_URL)
    return oauth_tokens.get('oauth_token'), oauth_tokens.get('oauth_token_secret')


def oauth2_fetch_access_token(consumer_key, consumer_secret):
    """Fetch twitter access token using oauth2."""

    oauth_consumer = oauth2.Consumer(key=consumer_key, secret=consumer_secret)
    oauth_client = oauth2.Client(oauth_consumer)

    # Get request token
    resp, content = oauth_client.request(REQUEST_TOKEN_URL)
    if resp['status'] != '200':
        raise AuthorizationError(
            'Invalid respond from Twitter requesting temp token: {0}'.format(resp['status'])
        )
    request_token = dict(parse_qsl(content))

    # Authorization
    authorization_url = '{url}?oauth_token={token}'.format(
        url=AUTHORIZATION_URL,
        token=request_token['oauth_token'])
    click.echo('Opening: ', authorization_url)
    click.launch(authorization_url)
    pincode = click.prompt('Enter the pincode')

    # Fetch access token
    token = oauth2.Token(request_token['oauth_token'],
                         request_token['oauth_token_secret'])
    token.set_verifier(pincode)
    oauth_client = oauth2.Client(oauth_consumer, token)
    resp, content = oauth_client.request(ACCESS_TOKEN_URL,
                                         method='POST',
                                         body='oauth_verifier=%s' % pincode)
    access_token = dict(parse_qsl(content))
    if resp['status'] != '200':
        raise AuthorizationError('The request for a Token did not succeed: {0}'.format(resp['status']))
    else:
        return access_token['oauth_token'], access_token['oauth_token_secret']


try:
    import oauth2 as oauth2
    fetch_access_token = oauth2_fetch_access_token
except ImportError:
    from requests_oauthlib import OAuth1Session
    fetch_access_token = oauthlib_fetch_access_token


def time_ago(time):
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


class TwitterConfig(object):
    general_section = 'general'

    def __init__(self, filename):
        self.filename = filename
        self.config = ConfigParser.RawConfigParser()

        # create file if not exists
        if not os.path.exists(self.filename):
            open(self.filename, 'w').close()

        with open(self.filename) as fp:
            # Python 2/3
            if hasattr(self.config, 'read_file'):
                self.config.read_file(fp)
            else:
                self.config.readfp(fp)

    def get(self, option, account=None, default=None):
        section = account or self.general_section
        try:
            return self.config.get(section, option)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            return default

    def set(self, option, value, account=None):
        section = account or self.general_section
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, option, value)
        return self

    def unset(self, option, account=None):
        section = account or self.general_section
        self.config.remove_option(section, option)
        items = self.config.items(section)
        if not items:
            self.config.remove_section(section)
        return self

    def remove_account(self, account):
        section = account or self.general_section
        self.config.remove_section(section)
        return self

    def list_accounts(self):
        return [section for section in self.config.sections()
                if section != self.general_section]

    def save(self, filename=None):
        filename = filename or self.filename
        with open(filename, 'w') as fp:
            self.config.write(fp)


@click.group()
@click.option('--account')
@click.option('--format')
@click.pass_context
def twitter(ctx, account, format):
    config = TwitterConfig(_CONFIG_FILE)
    if account is None:
        account = config.get('default_account')
    ctx.obj['config'] = config
    ctx.obj['account'] = account
    ctx.obj['format'] = format
    ctx.obj['api'] = login(config, account)


def save_since_id_at(option_name):
    def save_since_id(ctx, results):
        if results:
            config = ctx.obj['config']
            account = ctx.obj['account']
            config.set(option_name, results[0].id, account=account).save()
    return save_since_id


def handle_results(*handlers):

    def wrapper(func):
        @click.pass_context
        def new_func(ctx, *args, **kwargs):
            results = ctx.invoke(func, *args, **kwargs)
            for handler in handlers:
                handler(ctx, results)
            return results
        return update_wrapper(new_func, func)

    return wrapper


def pass_api(func):
    @click.pass_context
    def new_func(ctx, *args, **kwargs):
        return ctx.invoke(func, ctx.obj['api'], *args, **kwargs)
    return update_wrapper(new_func, func)


def pass_since_id_from(option_name):

    def wrapper(func):
        @click.pass_context
        def new_func(ctx, *args, **kwargs):
            config = ctx.obj['config']
            account = ctx.obj['account']
            kwargs['since_id'] = config.get(option_name, account=account)
            return ctx.invoke(func, *args, **kwargs)
        return update_wrapper(new_func, func)

    return wrapper


formatter = DefaultFormatter()


def parse_time(entry):
    return datetime.strptime(entry, '%a %b %d %H:%M:%S +0000 %Y')


def print_tweet(ctx, tweet):
    tweet = tweet.AsDict()
    tweet['text'] = html_unescape(tweet['text'])
    created_at = parse_time(tweet['created_at'])
    format_string = FORMAT_TWEET
    click.echo(formatter.format(format_string,
                                created_at,
                                time_ago=time_ago(created_at),
                                **tweet))


def print_tweets(ctx, tweets):
    for tweet in tweets:
        print_tweet(ctx, tweet)


def print_user(ctx, user):
    user = user.AsDict()
    created_at = parse_time(user['created_at'])
    format_string = FORMAT_USER
    click.echo(formatter.format(format_string,
                                created_at,
                                time_ago=time_ago(created_at),
                                **user))


def print_users(ctx, users):
    for user in users:
        print_user(ctx, user)


def print_search(ctx, tweet):
    tweet = tweet.AsDict()
    tweet['text'] = html_unescape(tweet['text'])
    created_at = parse_time(tweet['created_at'])
    format_string = FORMAT_SEARCH
    click.echo(formatter.format(format_string,
                                created_at,
                                time_ago=time_ago(created_at),
                                **tweet))


def print_searches(ctx, searches):
    for search in searches:
        print_search(ctx, search)


def print_message(ctx, message):
    message = message.AsDict()
    created_at = parse_time(message['created_at'])
    format_string = FORMAT_MESSAGE
    click.echo(formatter.format(format_string,
                                created_at,
                                time_ago=time_ago(created_at),
                                **message))


def print_messages(ctx, messages):
    for message in messages:
        print_message(ctx, message)


@twitter.command()
@click.argument('text', type=click.File('rb'))
@handle_results(print_tweet)
@pass_api
def post(api, text):
    return api.PostUpdate(text)


@twitter.command()
@click.option('--count', default=_MAX_COUNT, type=click.INT)
@click.argument('user')
@handle_results(print_tweets)
@pass_api
def tweets(api, user, count=None):
    return api.GetUserTimeline(screen_name=user, count=count)


@twitter.command()
@click.option('--count', default=_MAX_COUNT, type=click.INT)
@handle_results(print_tweets, save_since_id_at('timeline_since_id'))
@pass_since_id_from('timeline_since_id')
@pass_api
def timeline(api, count=None, since_id=None):
    if count is not None:
        since_id = None
    return api.GetHomeTimeline(count=count, since_id=since_id)


@twitter.command()
@click.option('--count', default=_MAX_COUNT, type=click.INT)
@handle_results(print_tweets, save_since_id_at('mentions_since_id'))
@pass_since_id_from('mentions_since_id')
@pass_api
def mentions(api, count=None, since_id=None):
    if count is not None:
        since_id = None
    return api.GetMentions(count=count, since_id=since_id)


@twitter.command()
@click.option('--count', default=_MAX_COUNT, type=click.INT)
@handle_results(print_tweets, save_since_id_at('replies_since_id'))
@pass_since_id_from('replies_since_id')
@pass_api
def replies(api, count=None, since_id=None):
    if count is not None:
        since_id = None
    return api.GetReplies(count=count, since_id=since_id)


@twitter.command()
@click.option('--count', default=_MAX_COUNT, type=click.INT)
@handle_results(print_messages, save_since_id_at('messages_since_id'))
@pass_since_id_from('messages_since_id')
@pass_api
def messages(api, count=None, since_id=None):
    if count is not None:
        since_id = None
    return api.GetDirectMessages(count=count, since_id=since_id)


@twitter.command()
@click.argument('user')
@click.argument('text', type=click.File('rb'))
@pass_api
def send(api, user, text):
    return api.PostDirectMessage(text, screen_name=user)


@twitter.command()
@click.argument('user')
@handle_results(print_users)
@pass_api
def followings(api, user):
    return api.GetFriends(user)


@twitter.command()
@click.argument('user')
@handle_results(print_users)
@pass_api
def followers(api, user):
    return api.GetFollowers(user)


@twitter.command()
@click.argument('user')
@pass_api
def follow(api, user):
    user = api.CreateFriendship(user)
    click.echo('You have requested to follow @%s' % user.screen_name)


@twitter.command()
@click.argument('user')
@pass_api
def unfollow(api, user):
    user = api.DestroyFriendship(user)
    click.echo('You have unfollowed @%s' % user.screen_name)


@twitter.command()
@click.argument('user')
@handle_results(print_tweets)
@pass_api
def faves(api, user):
    return api.GetFavorites(screen_name=user)


@twitter.command()
@click.argument('term')
@handle_results(print_searches)
@pass_api
def search(api, term):
    term = ' '.join(term).encode('utf-8')
    return api.GetSearch(term=term)


@twitter.command()
@click.argument('user', nargs=-1)
@handle_results(print_users)
@pass_api
def whois(api, user):
    return [api.GetUser(screen_name=name) for name in user]


def choose_config_name(default, config):
    """Prompt for choosing config name."""

    name = default

    while True:
        try:
            name = click.prompt('Enter a config name', default=default, show_default=True).strip()
        except KeyboardInterrupt:
            sys.exit(10)
        if name in config.list_accounts():
            click.echo('Cannot create config "{name}": config exists'.format(name=name), err=True)
        elif name:
            break

    return name


def login(config, account):
    consumer_key = config.get('consumer_key', account=account) or config.get('consumer_key')
    consumer_secret = config.get('consumer_secret', account=account) or config.get('consumer_secret')

    token_key = config.get('token_key', account=account)
    token_secret = config.get('token_secret', account=account)

    if not (consumer_key and consumer_secret):
        consumer_key = click.prompt('Consumer key').strip()
        consumer_secret = click.prompt('Consumer secret', hidden=True).strip()

    if not (token_key and token_secret):
        token_key, token_secret = fetch_access_token(consumer_key, consumer_secret)

    api = twitter_api.Api(consumer_key=consumer_key,
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


if __name__ == '__main__':
    twitter(obj={})
