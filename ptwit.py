#!/usr/bin/env python3

import os
import sys
import errno
from functools import update_wrapper
from datetime import datetime
from string import Formatter
import json
import re
import configparser
from html import unescape as html_unescape
from urllib.parse import parse_qsl
import typing as T

import twitter
import click
from click_default_group import DefaultGroup
from requests_oauthlib import OAuth1Session
from requests_oauthlib.oauth1_session import TokenRequestDenied


__version__ = "0.3"
MAX_COUNT = 200


class DefaultFormatter(Formatter):
    def get_value(self, key, args, kwargs):
        # Try standard formatting, if key not found then return None
        try:
            return Formatter.get_value(self, key, args, kwargs)
        except KeyError:
            return None


def fetch_access_token(
    client_key: str, client_secret: str, trial: int = 0
) -> T.Tuple[str, str]:
    """Fetch twitter access token using oauthlib."""

    REQUEST_TOKEN_URL = "https://api.twitter.com/oauth/request_token"
    AUTHORIZATION_URL = "https://api.twitter.com/oauth/authenticate"
    ACCESS_TOKEN_URL = "https://api.twitter.com/oauth/access_token"

    # Fetch request token
    oauth = OAuth1Session(client_key, client_secret=client_secret)
    fetch_response = oauth.fetch_request_token(REQUEST_TOKEN_URL)
    resource_owner_key = fetch_response.get("oauth_token")
    resource_owner_secret = fetch_response.get("oauth_token_secret")

    authorization_url = oauth.authorization_url(AUTHORIZATION_URL)
    click.echo(f"Opening {authorization_url}")
    click.launch(authorization_url)

    # Authorization
    pincode = click.prompt("Enter the pincode")
    oauth = OAuth1Session(
        client_key,
        client_secret=client_secret,
        resource_owner_key=resource_owner_key,
        resource_owner_secret=resource_owner_secret,
        verifier=pincode,
    )

    # Fetch access token
    try:
        oauth_tokens = oauth.fetch_access_token(ACCESS_TOKEN_URL)
    except TokenRequestDenied as err:
        if trial < 20:
            click.echo(err, err=True)
            return fetch_access_token(client_key, client_secret, trial=trial + 1)
        else:
            # Do not believe it is a typo any more
            raise err

    return oauth_tokens.get("oauth_token"), oauth_tokens.get("oauth_token_secret")


def time_ago(time: datetime) -> str:
    """Return a human-readable relative time from now."""

    diff = datetime.utcnow() - time

    if 1 < diff.days // 365:
        return f"{diff.days // 365} years ago"
    elif 1 == diff.days // 365:
        return "1 year ago"

    elif 1 < diff.days:
        return f"{diff.days} days ago"
    elif 1 == diff.days:
        return "1 day ago"

    elif 1 < diff.seconds // 3600:
        return f"{diff.seconds // 3600} hours ago"
    elif 1 == diff.seconds // 3600:
        return "1 hour ago"

    elif 1 < diff.seconds // 60:
        return f"{diff.seconds // 60} minutes ago"
    elif 1 == diff.seconds // 60:
        return "1 minute ago"

    else:
        return "just now"


class TwitterConfig:
    general_section: str = "general"
    filename: str
    config: configparser.RawConfigParser

    def __init__(self, filename: str):
        self.filename = filename
        self.config = configparser.RawConfigParser()

        try:
            with open(self.filename) as fp:
                self.config.read_file(fp)
        except IOError:
            pass

    def get(self, option: str, account=None, default=None):
        section = account or self.general_section
        try:
            return self.config.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    def set(self, option: str, value, account=None) -> "TwitterConfig":
        section = account or self.general_section
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, option, value)
        return self

    def unset(self, option: str, account=None) -> "TwitterConfig":
        section = account or self.general_section
        self.config.remove_option(section, option)
        items = self.config.items(section)
        if not items:
            self.config.remove_section(section)
        return self

    def remove_account(self, account: str) -> "TwitterConfig":
        section = account or self.general_section
        self.config.remove_section(section)
        return self

    def list_accounts(self) -> T.List[str]:
        return [
            section
            for section in self.config.sections()
            if section != self.general_section
        ]

    def save(self, filename=None) -> "TwitterConfig":
        filename = filename or self.filename
        with open(filename, "w") as fp:
            self.config.write(fp)
        return self


# http://stackoverflow.com/a/600612/114833
def mkdir(path: str) -> None:
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


@click.group(cls=DefaultGroup, default="timeline", default_if_no_args=True)
@click.option("--account", "-a", help="Use this account instead of the default one.")
@click.option(
    "--text",
    "format",
    flag_value="text",
    default=True,
    help="Print entries as human-readable text.",
)
@click.option(
    "--json", "format", flag_value="json", help="Print entires as JSON objects."
)
@click.pass_context
def ptwit(ctx: click.Context, account: T.Optional[str], format: str) -> None:
    config_dir = click.get_app_dir("ptwit")
    mkdir(config_dir)
    config = TwitterConfig(os.path.join(config_dir, "ptwit.conf"))

    if account is None:
        account = config.get("current_account")

    # Store the current account or user-specified account in context
    # object
    ctx.obj = {"config": config, "account": account, "format": format}

    if ctx.invoked_subcommand not in ("accounts", "login"):
        ctx.obj["api"] = _login(config, account)


def save_since_id_at(option_name: str) -> T.Callable:
    def save_since_id(ctx: click.Context, results):
        if results:
            config = ctx.obj["config"]
            account = ctx.obj["account"]
            # If no account stored in the beginning, we read current
            # account from config
            if not account:
                account = config.get("current_account")
            if not account:
                raise RuntimeError("Unable to find account anywhere")
            config.set(option_name, results[0].id, account=account).save()

    return save_since_id


def handle_results(*handlers):
    def wrapper(func):
        @click.pass_context
        def new_func(ctx: click.Context, *args, **kwargs):
            results = ctx.invoke(func, *args, **kwargs)
            for handler in handlers:
                handler(ctx, results)
            return results

        return update_wrapper(new_func, func)

    return wrapper


def pass_obj_args(*names: str):
    def wrapper(func):
        @click.pass_context
        def new_func(ctx: click.Context, *args, **kwargs):
            preceded_args = [ctx.obj[name] for name in names] + list(args)
            return ctx.invoke(func, *preceded_args, **kwargs)

        return update_wrapper(new_func, func)

    return wrapper


def pass_since_id_from(option_name: str) -> T.Callable:
    def wrapper(func):
        @click.pass_context
        def new_func(ctx: click.Context, *args, **kwargs):
            config = ctx.obj["config"]
            account = ctx.obj["account"]
            if not account:
                account = config.get("current_account")
            if not account:
                raise RuntimeError("Unable to find account anywhere")
            kwargs["since_id"] = config.get(option_name, account=account)
            return ctx.invoke(func, *args, **kwargs)

        return update_wrapper(new_func, func)

    return wrapper


_text_formatter = DefaultFormatter()


def parse_time(entry: str) -> datetime:
    return datetime.strptime(entry, "%a %b %d %H:%M:%S +0000 %Y")


def align_text(text: str, margin: str = "", skip_first_line: bool = False) -> str:
    lines = text.splitlines()
    aligned_lines = [
        line if (skip_first_line and n == 0) else (margin + line)
        for n, line in enumerate(lines)
    ]
    return "\n".join(aligned_lines)


def expand_urls(text: str, urls: T.List[T.Tuple[str, str]]) -> str:
    # shorten url must not surrounded by ASCII chars
    before = r"(?<![a-zA-z0-9])"
    after = r"(?![a-zA-Z0-9])"
    for shorten_url, expanded_url in dict(urls).items():
        text = re.sub(before + re.escape(shorten_url) + after, expanded_url, text)
    return text


def decorate_user_mentions(text: str, mentions: T.List[str], *args, **kwargs) -> str:
    for mention in set(mentions):
        text = re.sub(
            "@" + re.escape(mention) + r"(?![a-zA-Z0-9_])",
            click.style(f"@{mention}", *args, **kwargs),
            text,
        )
    return text


def decorate_hashtags(text: str, hashtags: T.List[str], *args, **kwargs) -> str:
    for hashtag in set(hashtags):
        text = re.sub(
            "#" + re.escape(hashtag) + r"(?!\w)",
            click.style(f"#{hashtag}", *args, **kwargs),
            text,
        )
    return text


FORMAT_TWEET = """\t{_username_} @{user[screen_name]}
\t{_aligned_text_}
\t{_time_ago_}
"""


FORMAT_RETWEET = """\t{_username_} @{user[screen_name]} ({_first_username_} Retweeted)
\t{_aligned_text_}
\t{_time_ago_}
"""


def format_tweet_as_text(tweet: twitter.Status) -> str:
    tweet = tweet.AsDict()
    assert not any(key[0] == "_" and key[-1] == "_" for key in tweet.keys())

    retweet = tweet.get("retweeted_status")
    if retweet:
        assert not any(key[0] == "_" and key[-1] == "_" for key in retweet.keys())
        retweet["_first_username_"] = tweet["user"]["name"]
        tweet = retweet

    username = tweet["user"]["name"]
    tweet["_username_"] = click.style(f" {username} ", fg="white", bg="black")

    created_at = parse_time(tweet["created_at"])
    tweet["_time_ago_"] = click.style(time_ago(created_at), fg="red")

    # Decorate text
    text = html_unescape(tweet["text"])

    urls = tweet.get("urls", []) + tweet.get("media", [])
    url_pairs = [(url["url"], url["expanded_url"]) for url in urls]
    text = expand_urls(text, url_pairs)

    mentions = [mention["screen_name"] for mention in tweet.get("user_mentions", [])]
    text = decorate_user_mentions(text, mentions, underline=True)

    hashtags = [hashtag["text"] for hashtag in tweet.get("hashtags", [])]
    text = decorate_hashtags(text, hashtags, underline=True)

    tweet["_aligned_text_"] = align_text(text, margin="\t", skip_first_line=True)

    return _text_formatter.format(
        FORMAT_RETWEET if retweet else FORMAT_TWEET, created_at, **tweet
    )


def format_tweet_as_json(tweet: twitter.Status) -> str:
    return json.dumps(tweet.AsDict(), ensure_ascii=False)


def print_tweet(ctx: click.Context, tweet: T.Optional[twitter.Status]) -> None:
    if not tweet:
        return
    format = ctx.obj["format"]
    if format == "json":
        click.echo(format_tweet_as_json(tweet))
    elif format == "text":
        click.echo(format_tweet_as_text(tweet))


def print_tweets(ctx: click.Context, tweets: T.List[twitter.Status]) -> None:
    format = ctx.obj["format"]
    if format == "json":
        output = "\n".join([format_tweet_as_json(tweet) for tweet in tweets])
        click.echo(output)
    elif format == "text":
        output = "\n".join([format_tweet_as_text(tweet) for tweet in tweets])
        if not tweets:
            pass
        elif len(tweets) == 1:
            click.echo(output)
        else:
            click.echo_via_pager(output)


FORMAT_USER = """\t{_username_} @{screen_name}
\tLocation:     {location}
\tURL:          {url}
\tFollowers:    {followers_count}
\tFollowing:    {friends_count}
\tStatus:       {statuses_count}
\tDescription:  {_aligned_description_}
\tJoined:       {0:%Y-%m-%d} ({_time_ago_})
"""


def format_user_as_text(user: twitter.User) -> str:
    user = user.AsDict()
    assert not any(key[0] == "_" and key[-1] == "_" for key in user.keys())

    created_at = parse_time(user["created_at"])

    user["_username_"] = click.style(f" {user['name']} ", fg="white", bg="black")

    user["_time_ago_"] = time_ago(created_at)

    description = user.get("description")
    if description is not None:
        margin = "\t" + " " * len("Description:  ")
        user["_aligned_description_"] = align_text(
            description, margin=margin, skip_first_line=True
        )

    return _text_formatter.format(FORMAT_USER, created_at, **user)


def format_user_as_json(user: twitter.User) -> str:
    return json.dumps(user.AsDict(), ensure_ascii=False)


def print_user(ctx: click.Context, user: twitter.User) -> None:
    if not user:
        return
    format == ctx.obj["format"]
    if format == "text":
        click.echo(format_user_as_text(user))
    elif format == "json":
        click.echo(format_user_as_json(user))


def print_users(ctx: click.Context, users: T.List[twitter.User]) -> None:
    format = ctx.obj["format"]
    if format == "text":
        output = "\n".join([format_user_as_text(user) for user in users])
        if not users:
            pass
        elif len(users) == 1:
            click.echo(output)
        else:
            click.echo_via_pager(output)
    elif format == "json":
        output = "\n".join([format_user_as_json(user) for user in users])
        click.echo(output)


FORMAT_MESSAGE = """\t{_sender_screen_name_}
\t{_aligned_text_}
\t{_time_ago_}
"""


def format_message_as_text(message: twitter.DirectMessage) -> str:
    message = message.AsDict()
    assert not any(key[0] == "_" and key[-1] == "_" for key in message.keys())

    created_at = parse_time(message["created_at"])
    message["_time_ago_"] = click.style(time_ago(created_at), fg="red")

    message["_sender_screen_name_"] = click.style(
        f" {message['sender_screen_name'] } ", fg="white", bg="black"
    )

    message["_aligned_text_"] = align_text(
        message["text"], margin="\t", skip_first_line=True
    )

    return _text_formatter.format(FORMAT_MESSAGE, created_at, **message)


def format_message_as_json(message: twitter.DirectMessage) -> str:
    return json.dumps(message.AsDict(), ensure_ascii=False)


def print_message(ctx: click.Context, message: twitter.DirectMessage) -> None:
    if not message:
        return
    format == ctx.obj["format"]
    if format == "text":
        click.echo(format_message_as_text(message))
    elif format == "json":
        click.echo(format_message_as_json(message))


def print_messages(ctx: click.Context, messages: T.List[twitter.DirectMessage]) -> None:
    format = ctx.obj["format"]
    if format == "text":
        output = "\n".join([format_message_as_text(message) for message in messages])
        if not messages:
            pass
        elif len(messages) == 1:
            click.echo(output)
        else:
            click.echo_via_pager(output)
    elif format == "json":
        output = "\n".join([format_user_as_json(message) for message in messages])
        click.echo(output)


def read_text(words: T.List[str]) -> str:
    if len(words) == 1 and words[0] == "-":
        text = click.get_text_stream("stdin").read()
    elif words:
        text = " ".join(words)
        click.confirm(f'Post "{text}"?', abort=True)
    else:
        text = click.edit()

    return text


@ptwit.command()
@click.argument("words", nargs=-1)
@handle_results(print_tweet)
@pass_obj_args("api")
def post(api: twitter.Api, words: T.List[str]) -> twitter.Status:
    """Post a tweet."""
    text = read_text(words)
    if not text or not text.strip():
        raise click.Abort()
    return api.PostUpdate(text)


def get_latest_tweet(api: twitter.Api) -> T.Optional[twitter.Status]:
    latest_tweet = api.GetUserTimeline(count=2, include_rts=False, exclude_replies=True)
    if latest_tweet:
        return latest_tweet[0]
    else:
        return None


@ptwit.command()
@click.option(
    "--drop", "-d", default=False, is_flag=True, help="Delete the latest tweet."
)
@handle_results(print_tweet)
@pass_obj_args("api")
def pop(api: twitter.Api, drop: bool) -> twitter.Status:
    """Edit or delete the latest tweet."""
    latest_tweet = get_latest_tweet(api)
    if not latest_tweet:
        click.echo("No tweet found.", err=True)
        return None

    # Delete the latest tweet
    if drop:
        return api.DestroyStatus(status_id=latest_tweet.id)

    text = click.edit(latest_tweet.text)

    # Do nothing if as you exited without saving
    if text is None:
        return latest_tweet

    # Delete the latest tweet if content is empty
    text = text.strip()
    if not text:
        return api.DestroyStatus(status_id=latest_tweet.id)

    # Post new tweet first and then delete the old tweet
    tweet = api.PostUpdate(text)
    api.DestroyStatus(status_id=latest_tweet.id)
    return tweet


@ptwit.command()
@click.option("--count", "-c", default=MAX_COUNT, type=click.INT)
@click.argument("users", nargs=-1)
@handle_results(print_tweets)
@pass_obj_args("api")
def tweets(
    api: twitter.Api, users: T.List[str], count: int = None
) -> T.List[twitter.Status]:
    """List user's tweets."""
    if not users:
        users = [api.VerifyCredentials().screen_name]

    tweets = []
    for user in users:
        tweets += api.GetUserTimeline(screen_name=user, count=count)
    return tweets


@ptwit.command()
@click.option("--count", "-c", type=click.INT)
@handle_results(print_tweets, save_since_id_at("timeline_since_id"))
@pass_since_id_from("timeline_since_id")
@pass_obj_args("api")
def timeline(
    api: twitter.Api, count: int = None, since_id: int = None
) -> T.List[twitter.Status]:
    """List timeline."""
    if count is None:
        count = MAX_COUNT
    else:
        since_id = None
    return api.GetHomeTimeline(count=count, since_id=since_id)


@ptwit.command()
@click.option("--count", "-c", type=click.INT)
@handle_results(print_tweets, save_since_id_at("mentions_since_id"))
@pass_since_id_from("mentions_since_id")
@pass_obj_args("api")
def mentions(api: twitter.Api, count=None, since_id=None) -> T.List[twitter.Status]:
    """List mentions."""
    if count is None:
        count = MAX_COUNT
    else:
        since_id = None
    return api.GetMentions(count=count, since_id=since_id)


@ptwit.command()
@click.option("--count", "-c", type=click.INT)
@handle_results(print_tweets, save_since_id_at("replies_since_id"))
@pass_since_id_from("replies_since_id")
@pass_obj_args("api")
def replies(
    api: twitter.Api, count: int = None, since_id: int = None
) -> T.List[twitter.Status]:
    """List replies."""
    if count is None:
        count = MAX_COUNT
    else:
        since_id = None
    return api.GetReplies(count=count, since_id=since_id)


@ptwit.command()
@click.option("--count", "-c", default=MAX_COUNT, type=click.INT)
@handle_results(print_messages, save_since_id_at("messages_since_id"))
@pass_since_id_from("messages_since_id")
@pass_obj_args("api")
def messages(
    api: twitter.Api, count: int = None, since_id: int = None
) -> T.List[twitter.DirectMessage]:
    """List messages."""
    if count is None:
        count = MAX_COUNT
    else:
        since_id = None
    return api.GetDirectMessages(count=count, since_id=since_id)


@ptwit.command()
@click.argument("user")
@click.argument("words", nargs=-1)
@pass_obj_args("api")
def send(api: twitter.Api, user: str, words: T.List[str]):
    """Send a message to a user."""
    text = read_text(words)
    if not text or not text.strip():
        raise click.Abort()
    return api.PostDirectMessage(text, screen_name=user)


@ptwit.command()
@click.argument("user")
@handle_results(print_users)
@pass_obj_args("api")
def followings(api: twitter.Api, user: str) -> T.List[twitter.User]:
    """List who you are following."""
    return api.GetFriends(user)


@ptwit.command()
@click.argument("user")
@handle_results(print_users)
@pass_obj_args("api")
def followers(api: twitter.Api, user: str) -> T.List[twitter.User]:
    """List your followers."""
    return api.GetFollowers(user)


@ptwit.command()
@click.argument("users", nargs=-1)
@handle_results(print_users)
@pass_obj_args("api")
def follow(api: twitter.Api, users: T.List[str]):
    """Follow users."""
    return [api.CreateFriendship(screen_name=user) for user in users]


@ptwit.command()
@click.argument("users", nargs=-1, required=True)
@handle_results(print_users)
@pass_obj_args("api")
def unfollow(api: twitter.Api, users: T.List[str]):
    """Unfollow users."""
    return [api.DestroyFriendship(screen_name=user) for user in users]


@ptwit.command()
@click.argument("user")
@handle_results(print_tweets)
@pass_obj_args("api")
def faves(api: twitter.Api, user: str):
    """List favourite tweets of a user."""
    return api.GetFavorites(screen_name=user)


@ptwit.command()
@click.option("--count", "-c", default=MAX_COUNT)
@click.argument("term", nargs=-1)
@handle_results(print_tweets)
@pass_obj_args("api")
def search(api: twitter.Api, count: int, term: T.List[str]) -> T.List[twitter.Status]:
    """Search Twitter."""
    if term:
        query = " ".join(term).encode("utf-8")
    else:
        query = click.prompt("Search")
    return api.GetSearch(term=query, count=count)


@ptwit.command()
@click.argument("users", nargs=-1)
@handle_results(print_users)
@pass_obj_args("api")
def whois(api: twitter.Api, users: T.List[str]) -> T.List[twitter.User]:
    """Show user profiles."""
    if not users:
        return [api.VerifyCredentials()]
    return [api.GetUser(screen_name=screen_name) for screen_name in users]


def print_accounts(ctx: click.Context, accounts: T.List[str]) -> None:
    config = ctx.obj["config"]
    current_account = config.get("current_account")
    for account in sorted(accounts):
        if account == current_account:
            click.echo(click.style(f"* {account}", fg="red"))
        else:
            click.echo(f"  {account}")


@ptwit.command()
@handle_results(print_accounts)
@click.pass_context
def accounts(ctx: click.Context) -> T.List[str]:
    """List all accounts."""
    return ctx.obj["config"].list_accounts()


@ptwit.command()
@click.argument("account")
@pass_obj_args("config")
def login(config: TwitterConfig, account: str) -> None:
    """Log into an account."""
    _login(config, account)
    current_account = config.get("current_account")
    click.echo(f'Switched to account "{current_account}"')


def choose_account_name(config: TwitterConfig, default: str) -> str:
    """Prompt for choosing config name."""

    while True:
        name = click.prompt("Enter an account name", default=default, show_default=True)
        name = name.strip()
        if name in config.list_accounts():
            click.echo(f'Account "{name}" existed', err=True)
        elif name:
            break

    return name


def _login(config: TwitterConfig, account: str = None) -> twitter.Api:
    consumer_key = config.get("consumer_key", account=account) or config.get(
        "consumer_key"
    )
    consumer_secret = config.get("consumer_secret", account=account) or config.get(
        "consumer_secret"
    )

    if not (consumer_key and consumer_secret):
        consumer_key = click.prompt("Consumer key").strip()
        consumer_secret = click.prompt("Consumer secret", hide_input=True).strip()
        assert consumer_key and consumer_secret

    token_key = config.get("token_key", account=account)
    token_secret = config.get("token_secret", account=account)

    if not (token_key and token_secret):
        if account:
            msg = f'New account "{account}" found.'
        else:
            msg = "No account found."
        msg += " Open a web browser to authenticate?"
        click.confirm(msg, default=True, abort=True)
        token_key, token_secret = fetch_access_token(consumer_key, consumer_secret)

    api = twitter.Api(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token_key=token_key,
        access_token_secret=token_secret,
    )

    # We put it here to verify consumer pair and token pair
    user = api.VerifyCredentials()

    # If it's get verified, we can safely store the consumer pair
    # globally
    if not config.get("consumer_key"):
        config.set("consumer_key", consumer_key)
    if not config.get("consumer_secret"):
        config.set("consumer_secret", consumer_secret)

    if not account:
        account = choose_account_name(config, user.screen_name)
        assert account, "an account name must be chosen"

    # Update consumer pair locally
    if config.get("consumer_key", account=account):
        config.set("consumer_key", consumer_key, account=account)
    if config.get("consumer_secret", account=account):
        config.set("consumer_secret", consumer_secret, account=account)

    # Update token pair locally
    config.set("token_key", token_key, account=account)
    config.set("token_secret", token_secret, account=account)

    # Update current account
    config.set("current_account", account)

    config.save()

    return api


def cli() -> None:
    try:
        ptwit()
    except twitter.error.TwitterError as err:
        click.echo(f"Twitter Error: {err}", err=True)
        sys.exit(2)
    except TokenRequestDenied as err:
        click.echo(err, err=True)
        sys.exit(3)


if __name__ == "__main__":
    cli()
