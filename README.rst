ptwit: a simple command line twitter client.
============================================

ptwit is a simple command-line-based twitter client.

Requirements
------------
* A twitter account.
* A twitter application registered at https://dev.twitter.com/apps

Installation
------------
To install ptwit, simply::

    pip install ptwit

The first time you issue a ptwit command will prompt to input a consumer key and a consumer secret,
both of which can be obtained from your registered application at https://dev.twitter.com/apps

Usage
-----

Login::

   ptwit login

This command will open a twitter authentication page asking for your permission,
and then presenting a 7-digit pincode if you permit it. Feed ptwit the pincode to finish the login process.

Get friends timeline::

   ptwit timeline

Get someone's tweets::

   ptwit tweets someone
   
Get mentions or replies::

   ptwit mentions
   ptwit replies

Commands above always list the latest 20 new tweets, which means the tweets you've fetched will not be listed again.

If you want to list a specified number of tweets, use switch `-c`::

   ptwit timeline -c 30

Or specified page (20 tweets per page)::

   ptwit tweets -p 2 someone

Post a new tweet::

   ptwit post hello world
   ptwit post < tweet.txt

Get public timeline::

   ptwit public


Send message to someone::

   ptwit send someone hello, ptwit is awesome
   cat message.txt | ptwit send someone
