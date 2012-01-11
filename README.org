* Requirements
  1. A twitter acount
  2. A twitter application registered at [[https://dev.twitter.com/apps]]
* Installation
  Install =oauth2= and =python-twitter=.
  #+BEGIN_SRC example
  pip install oauth2
  pip install python-twitter
  #+END_SRC example

  Download =ptwit=.
  #+BEGIN_SRC example
  git clone git://github.com/ptpt/ptwit.git
  #+END_SRC example

  Have fun :)

* Usage:
** Twitter commands
   Login:
   #+BEGIN_SRC example
   ptwit login
   #+END_SRC

   Get friends timeline:
   #+BEGIN_SRC example
   ptwit timeline
   #+END_SRC

   Post status:
   #+BEGIN_SRC example
   ptwit post hello world
   ptwit post < tweet.txt
   #+END_SRC

   Get public timeline:
   #+BEGIN_SRC example
   ptwit public
   #+END_SRC

   Get mentions or replies:
   #+BEGIN_SRC example
   ptwit mentions
   ptwit replies
   #+END_SRC

   Send message:
   #+BEGIN_SRC example
   ptwit send someone hello, ptwit is awesome
   cat message.txt | ptwit send someone
   #+END_SRC
