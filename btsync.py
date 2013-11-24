# -*- coding: utf-8 -*-

import urllib2
from urllib import urlencode
import json
import base64

BASEURL = 'http://hostname.com:port/api'
USERNAME = 'user'
PASSWORD = 'password'
logger = None


def request(**kwargs):
    args = urlencode(kwargs)
    url = BASEURL+'?'+args
    logger.debug(url)

    request = urllib2.Request(url)
    base64string = base64.encodestring('%s:%s' % (USERNAME, PASSWORD)).replace('\n', '')
    request.add_header("Authorization", "Basic %s" % base64string)
    response = urllib2.urlopen(request)

    return json.load(response)
