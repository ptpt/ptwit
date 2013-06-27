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

    $ pip install ptwit


Authorization
-------------

For the first time you run ``ptwit`` command, you will be asked for
your Twitter application information, which you can find at
`https://dev.twitter.com/apps`. If you don't have one, register at
`https://dev.twitter.com/apps/new`.

You can also manually set your Twitter application information via the
commands below:

.. code-block:: bash

    $ ptwit config -g set consumer_key "CONSUMER KEY HERE"
    $ ptwit config -g set consumer_secret "CONSUMER SECRET HERE"

``ptwit`` supports multiple Twitter accounts. You can always use the
``login`` command to log into a new account:

.. code-block:: bash

    $ ptwit login

The command above will take you to the Twitter authorization page, and
ask you to give a name for this account.

You can easily switch between accounts you've already authorized:

.. code-block:: bash

    $ ptwit login ACCOUNT

To remove an account from your computer, use this command:

.. code-block:: bash

    $ ptwit config remove ACCOUNT


Twitter Commands
----------------

Get home timeline
~~~~~~~~~~~~~~~~~

.. code-block:: bash

    $ ptwit timeline            # latest tweets
    $ ptwit timeline -c 20      # latest 20 tweets

Get tweets of a Twitter user
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    $ ptwit tweets              # list your tweets
    $ ptwit tweets USER         # list someone's tweets

Get mentions or replies
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    $ ptwit mentions
    $ ptwit replies

Post a new tweet
~~~~~~~~~~~~~~~~

.. code-block:: bash

    $ ptwit post "YOUR STATUS"
    $ ptwit post < tweet.txt

Send direct message
~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    $ ptwit send USER "YOUR MESSAGE"
    $ cat message.txt | ptwit send USER

List followings
~~~~~~~~~~~~~~~

.. code-block:: bash

    $ ptwit followings

List followers
~~~~~~~~~~~~~~

.. code-block:: bash

    $ ptwit followers

Follow or unfollow Twitter users
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    $ ptwit follow USER
    $ ptwit unfollow USER

List your favorite tweets
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    $ ptwit faves

Get a Twitter user's information
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    $ ptwit whois USER

Search tweets
~~~~~~~~~~~~~

.. code-block:: bash

    $ ptwit search TERM


LICENSE
-------

``ptwit`` is under the MIT License. See LICENSE file for full license text.
