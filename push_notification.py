import sys
import http.client, urllib
from pushoverkeys import token, user

def push_notification(title, body):
  # create connection
  conn = http.client.HTTPSConnection("api.pushover.net:443")

  # make POST request to send message
  conn.request("POST", "/1/messages.json",
               urllib.parse.urlencode({
                 "token": token,
                 "user": user,
                 "title": title,
                 "message": body,
                 "url": "",
                 "priority": "1"
               }), {"Content-type": "application/x-www-form-urlencoded"})

  # get response
  conn.getresponse()


if __name__ == '__main__':
  title = sys.argv[1]
  body = sys.argv[2]
  push_notification(title, body)