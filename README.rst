``ptwit``: A Command-line Twitter Client
============================================

Introduction
------------

``ptwit`` is a simple command-line-based Twitter client.

Screenshots
~~~~~~~~~~~

.. image:: http://farm8.staticflickr.com/7326/9144252605_46bb544fe8_z.jpg


Requirements
------------

* A Twitter account
* A Twitter application registered at https://dev.twitter.com/apps


Installation
------------

To install ``ptwit``, simply:

.. code-block:: bash

    pip install ptwit


Authorization
-------------

For the first time you run ``ptwit`` command, ``ptwit`` will ask for
your Twitter application information, which you can find at
`https://dev.twitter.com/apps`. If you don't have one, register at
`https://dev.twitter.com/apps/new`.

``ptwit`` supports multiple Twitter accounts. You can easily log into
a new account, or switch between accounts you've already authorized:

.. code-block:: bash

    ptwit login ACCOUNT

Usage
----------------

.. code-block::

   Usage: ptwit.py [OPTIONS] COMMAND [ARGS]...

   Options:
     --account TEXT  Use this account instead of the default one.
     --text          Print entries as human-readable text.
     --json          Print entires as JSON objects.
     --help          Show this message and exit.

   Commands:
     timeline*   List timeline.
     accounts    List all accounts.
     faves       List favourite tweets of a user.
     follow      Follow a user.
     followers   List your followers.
     followings  List who you are following.
     login       Log into an account.
     mentions    List mentions.
     messages    List messages.
     post        Post a tweet.
     replies     List replies.
     search      Search Twitter.
     send        Send a message to a user.
     tweets      List user's tweets.
     unfollow    Unfollow a user.
     whois       Show user profiles.

LICENSE
-------

``ptwit`` is under the MIT License. See LICENSE file for full license text.
