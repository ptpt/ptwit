#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import (division, print_function)

import os
import sys
import errno
from functools import update_wrapper
from datetime import datetime
from string import Formatter
import json

try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser

try:
    # Python 2
    from HTMLParser import HTMLParser
    html_unescape = HTMLParser().unescape
except ImportError:
    # Python 3
    from html import unescape as html_unescape

try:
    from urlparse import parse_qsl
except ImportError:
    from urllib.parse import parse_qsl

import twitter
import click
from click_default_group import DefaultGroup
from requests_oauthlib import OAuth1Session


__version__ = '0.1'
__author__ = 'Tao Peng'
__license__ = 'MIT'
__copyright__ = 'Copyright (c) 2012-2016 Tao Peng'


PY2 = sys.version_info[0] == 2

_MAX_COUNT = 200

FORMAT_TWEET = u'''\t{_username_} (@{user[screen_name]})
\t{text}
\t{_time_ago_}
'''

FORMAT_MESSAGE = u'''\t{_sender_screen_name_}
\t{text}
\t{_time_ago_}
'''

FORMAT_USER = u'''\t{_username_} (@{screen_name})
\tLocation:     {location}
\tURL:          {url}
\tFollowers:    {followers_count}
\tFollowing:    {friends_count}
\tStatus:       {statuses_count}
\tDescription:  {description}
\tJoined:       {0:%Y-%m-%d} ({_time_ago_})
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


def fetch_access_token(client_key, client_secret):
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


def time_ago(time):
    """Return a human-readable relative time from now."""

    diff = datetime.utcnow() - time

    if 1 < diff.days // 365:
        return '{0} years ago'.format(diff.days // 365)
    elif 1 == diff.days // 365:
        return '1 year ago'

    elif 1 < diff.days:
        return '{0} days ago'.format(diff.days)
    elif 1 == diff.days:
        return '1 day ago'

    elif 1 < diff.seconds // 3600:
        return '{0} hours ago'.format(diff.seconds // 3600)
    elif 1 == diff.seconds // 3600:
        return '1 hour ago'

    elif 1 < diff.seconds // 60:
        return '{0} minutes ago'.format(diff.seconds // 60)
    elif 1 == diff.seconds // 60:
        return '1 minute ago'

    else:
        return 'just now'


class TwitterConfig(object):
    general_section = 'general'

    def __init__(self, filename):
        self.filename = filename
        self.config = ConfigParser.RawConfigParser()

        try:
            with open(self.filename) as fp:
                # Python 2/3
                if hasattr(self.config, 'read_file'):
                    self.config.read_file(fp)
                else:
                    self.config.readfp(fp)
        except IOError:
            pass

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


# http://stackoverflow.com/a/600612/114833
def mkdir(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


@click.group(cls=DefaultGroup, default='timeline', default_if_no_args=True)
@click.option('--account', '-a',
              help='Use this account instead of the default one.')
@click.option('--text', 'format', flag_value='text', default=True,
              help='Print entries as human-readable text.')
@click.option('--json', 'format', flag_value='json',
              help='Print entires as JSON objects.')
@click.pass_context
def ptwit(ctx, account, format):
    config_dir = click.get_app_dir('ptwit')
    mkdir(config_dir)
    config = TwitterConfig(os.path.join(config_dir, 'ptwit.conf'))

    if account is None:
        account = config.get('current_account')

    ctx.obj = {'config': config,
               'account': account,
               'format': format}

    if ctx.invoked_subcommand not in ('accounts', 'login'):
        ctx.obj['api'] = _login(config, account)
        if not ctx.obj['api']:
            raise click.Abort()


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


def pass_obj_args(*names):

    def wrapper(func):
        @click.pass_context
        def new_func(ctx, *args, **kwargs):
            preceded_args = [ctx.obj[name] for name in names]
            args = preceded_args + list(args)
            return ctx.invoke(func, *args, **kwargs)
        return update_wrapper(new_func, func)

    return wrapper


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


_formatter = DefaultFormatter()


def parse_time(entry):
    return datetime.strptime(entry, '%a %b %d %H:%M:%S +0000 %Y')


def format_tweet_as_text(tweet):
    tweet = tweet.AsDict()
    assert not any(key[0] == '_' and key[-1] == '_' for key in tweet.keys())

    username = tweet['user']['name']
    tweet['_username_'] = click.style(' ' + username + ' ', bg='black', fg='white')
    created_at = parse_time(tweet['created_at'])
    tweet['_time_ago_'] = click.style(time_ago(created_at), fg='red')
    tweet['text'] = html_unescape(tweet['text'])

    return _formatter.format(FORMAT_TWEET, created_at, **tweet)


def format_tweet_as_json(tweet):
    return json.dumps(tweet.AsDict())


def print_tweet(ctx, tweet):
    format = ctx.obj['format']
    if format == 'json':
        click.echo(format_tweet_as_json(tweet))
    elif format == 'text':
        click.echo(format_tweet_as_text(tweet))


def print_tweets(ctx, tweets):
    format = ctx.obj['format']
    if format == 'json':
        output = '\n'.join([format_tweet_as_json(tweet) for tweet in tweets])
        click.echo(output)
    elif format == 'text':
        output = '\n'.join([format_tweet_as_text(tweet) for tweet in tweets])
        if not tweets:
            pass
        elif len(tweets) == 1:
            click.echo(output)
        else:
            click.echo_via_pager(output)


def format_user_as_text(user):
    user = user.AsDict()
    assert not any(key[0] == '_' and key[-1] == '_' for key in user.keys())

    created_at = parse_time(user['created_at'])
    user['_username_'] = click.style(' ' + user['name'] + ' ', fg='white', bg='black')
    user['_time_ago_'] = time_ago(created_at)

    return _formatter.format(FORMAT_USER, created_at, **user)


def format_user_as_json(user):
    return json.dumps(user.AsDict())


def print_user(ctx, user):
    format == ctx.obj['format']
    if format == 'text':
        click.echo(format_user_as_text(user))
    elif format == 'json':
        click.echo(format_user_as_json(user))


def print_users(ctx, users):
    format = ctx.obj['format']
    if format == 'text':
        output = '\n'.join([format_user_as_text(user) for user in users])
        if not users:
            pass
        elif len(users) == 1:
            click.echo(output)
        else:
            click.echo_via_pager(output)
    elif format == 'json':
        output = '\n'.join([format_user_as_json(user) for user in users])
        click.echo(output)


def format_message_as_text(message):
    message = message.AsDict()
    assert not any(key[0] == '_' and key[-1] == '_' for key in message.keys())

    created_at = parse_time(message['created_at'])
    message['_time_ago_'] = click.style(time_ago(created_at), fg='red')
    message['_sender_screen_name_'] = click.style(' ' + message['sender_screen_name'] + ' ',
                                                  fg='white', bg='black')

    return _formatter.format(FORMAT_MESSAGE, created_at, **message)


def format_message_as_json(message):
    return json.dumps(message.AsDict())


def print_message(ctx, message):
    format == ctx.obj['format']
    if format == 'text':
        click.echo(format_message_as_text(message))
    elif format == 'json':
        click.echo(format_message_as_json(message))


def print_messages(ctx, messages):
    format = ctx.obj['format']
    if format == 'text':
        output = '\n'.join([format_message_as_text(message) for message in messages])
        if not messages:
            pass
        elif len(messages) == 1:
            click.echo(output)
        else:
            click.echo_via_pager(output)
    elif format == 'json':
        output = '\n'.join([format_user_as_json(message) for message in messages])
        click.echo(output)


def read_text(words):
    if len(words) == 1 and words[0] == '-':
        text = click.get_text_stream('stdin').read()
    elif words:
        text = ' '.join(words)
        if not click.confirm('Post "{0}"?'.format(text)):
            return None
    else:
        text = click.edit()

    return text


@ptwit.command()
@click.argument('words', nargs=-1)
@handle_results(print_tweet)
@pass_obj_args('api')
def post(api, words):
    """Post a tweet."""
    text = read_text(words)
    if not text or not text.strip():
        raise click.Abort()
    return api.PostUpdate(text)


@ptwit.command()
@click.option('--count', '-c', default=_MAX_COUNT, type=click.INT)
@click.argument('users', nargs=-1)
@handle_results(print_tweets)
@pass_obj_args('api')
def tweets(api, users, count=None):
    """List user's tweets."""
    if not users:
        users = [api.VerifyCredentials().screen_name]

    tweets = []
    for user in users:
        tweets += api.GetUserTimeline(screen_name=user, count=count)
    return tweets


@ptwit.command()
@click.option('--count', '-c', type=click.INT)
@handle_results(print_tweets, save_since_id_at('timeline_since_id'))
@pass_since_id_from('timeline_since_id')
@pass_obj_args('api')
def timeline(api, count=None, since_id=None):
    """List timeline."""
    if count is None:
        count = _MAX_COUNT
    else:
        since_id = None
    return api.GetHomeTimeline(count=count, since_id=since_id)


@ptwit.command()
@click.option('--count', '-c', type=click.INT)
@handle_results(print_tweets, save_since_id_at('mentions_since_id'))
@pass_since_id_from('mentions_since_id')
@pass_obj_args('api')
def mentions(api, count=None, since_id=None):
    """List mentions."""
    if count is None:
        count = _MAX_COUNT
    else:
        since_id = None
    return api.GetMentions(count=count, since_id=since_id)


@ptwit.command()
@click.option('--count', '-c', type=click.INT)
@handle_results(print_tweets, save_since_id_at('replies_since_id'))
@pass_since_id_from('replies_since_id')
@pass_obj_args('api')
def replies(api, count=None, since_id=None):
    """List replies."""
    if count is None:
        count = _MAX_COUNT
    else:
        since_id = None
    return api.GetReplies(count=count, since_id=since_id)


@ptwit.command()
@click.option('--count', '-c', default=_MAX_COUNT, type=click.INT)
@handle_results(print_messages, save_since_id_at('messages_since_id'))
@pass_since_id_from('messages_since_id')
@pass_obj_args('api')
def messages(api, count=None, since_id=None):
    """List messages."""
    if count is None:
        count = _MAX_COUNT
    else:
        since_id = None
    return api.GetDirectMessages(count=count, since_id=since_id)


@ptwit.command()
@click.argument('user')
@click.argument('words', nargs=-1)
@pass_obj_args('api')
def send(api, user, words):
    """Send a message to a user."""
    text = read_text(words)
    if not text or not text.strip():
        raise click.Abort()
    return api.PostDirectMessage(text, screen_name=user)


@ptwit.command()
@click.argument('user')
@handle_results(print_users)
@pass_obj_args('api')
def followings(api, user):
    """List who you are following."""
    return api.GetFriends(user)


@ptwit.command()
@click.argument('user')
@handle_results(print_users)
@pass_obj_args('api')
def followers(api, user):
    """List your followers."""
    return api.GetFollowers(user)


@ptwit.command()
@click.argument('user')
@handle_results(print_user)
@pass_obj_args('api')
def follow(api, user):
    """Follow a user."""
    return api.CreateFriendship(user)


@ptwit.command()
@click.argument('user')
@handle_results(print_user)
@pass_obj_args('api')
def unfollow(api, user):
    """Unfollow a user."""
    return api.DestroyFriendship(user)


@ptwit.command()
@click.argument('user')
@handle_results(print_tweets)
@pass_obj_args('api')
def faves(api, user):
    """List favourite tweets of a user."""
    return api.GetFavorites(screen_name=user)


@ptwit.command()
@click.argument('term', nargs=-1)
@handle_results(print_tweets)
@pass_obj_args('api')
def search(api, term):
    """Search Twitter."""
    term = ' '.join(term).encode('utf-8')
    return api.GetSearch(term=term)


@ptwit.command()
@click.argument('users', nargs=-1)
@handle_results(print_users)
@pass_obj_args('api')
def whois(api, users):
    """Show user profiles."""
    if not users:
        return [api.VerifyCredentials()]
    return [api.GetUser(screen_name=screen_name) for screen_name in users]


def print_accounts(ctx, accounts):
    config = ctx.obj['config']
    current_account = config.get('current_account')
    for account in sorted(accounts):
        if account == current_account:
            click.echo(click.style('* {0}'.format(account), fg='red'))
        else:
            click.echo('  {0}'.format(account))


@ptwit.command()
@handle_results(print_accounts)
@click.pass_context
def accounts(ctx):
    """List all accounts."""
    return ctx.obj['config'].list_accounts()


@ptwit.command()
@click.argument('account')
@pass_obj_args('config')
def login(config, account):
    """Log into an account."""
    api = _login(config, account)
    if api:
        current_account = config.get('current_account')
        click.echo('Switched to account "{0}"'.format(current_account))


def choose_account_name(config, default):
    """Prompt for choosing config name."""

    while True:
        name = click.prompt('Enter an account name', default=default, show_default=True)
        name = name.strip()
        if name in config.list_accounts():
            click.echo('Account "{0}" existed'.format(name), err=True)
        elif name:
            break

    return name


def _login(config, account=None):
    consumer_key = config.get('consumer_key', account=account) or config.get('consumer_key')
    consumer_secret = config.get('consumer_secret', account=account) or config.get('consumer_secret')

    token_key = config.get('token_key', account=account)
    token_secret = config.get('token_secret', account=account)

    if not (consumer_key and consumer_secret):
        consumer_key = click.prompt('Consumer key').strip()
        consumer_secret = click.prompt('Consumer secret', hide_input=True).strip()
        assert consumer_key and consumer_secret

    if not config.get('consumer_key'):
        config.set('consumer_key', consumer_key)
    if not config.get('consumer_secret'):
        config.set('consumer_secret', consumer_secret)

    if not (token_key and token_secret):
        if account:
            msg = 'New account "{0}" found. Open a web browser to authenticate?'.format(account)
        else:
            msg = 'No account found. Open a web browser to authenticate?'

        if click.confirm(msg, default=True):
            token_key, token_secret = fetch_access_token(consumer_key, consumer_secret)
        else:
            config.save()
            return None

    api = twitter.Api(consumer_key=consumer_key,
                      consumer_secret=consumer_secret,
                      access_token_key=token_key,
                      access_token_secret=token_secret)

    if not account:
        user = api.VerifyCredentials()
        account = choose_account_name(config, user.screen_name)
        assert account

    if config.get('consumer_key', account=account):
        config.set('consumer_key', consumer_key, account=account)
    if config.get('consumer_secret', account=account):
        config.set('consumer_secret', consumer_secret, account=account)
    config.set('token_key', token_key, account=account)
    config.set('token_secret', token_secret, account=account)
    config.set('current_account', account)

    config.save()

    return api


def cli():
    try:
        ptwit()
    except twitter.error.TwitterError as err:
        click.echo('Twitter Error: {0}'.format(err), err=True)
        sys.exit(2)


if __name__ == '__main__':
    cli()
