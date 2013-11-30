# -*- coding: utf-8 -*-

import urllib2
from urllib import urlencode
import json
import base64

BASEURL = 'http://hostname.com:port/api'
USERNAME = 'user'
PASSWORD = 'password'
logger = None


class BTSyncException(Exception):
    def __init__(self, errno, strerror):
        self.errno = errno
        self.strerror = strerror

    def __str__(self):
        return '[Errno {errno} {strerror}]'.format(errno=self.errno, strerror=repr(self.strerror))


def request(**kwargs):
    args = urlencode(kwargs)
    url = BASEURL+'?'+args
    logger.debug('requesting url: http://{username}:{password}@{url}'.format(username=USERNAME, password=PASSWORD,
                                                                             url=url[7:]))

    request = urllib2.Request(url)
    base64string = base64.encodestring('%s:%s' % (USERNAME, PASSWORD)).replace('\n', '')
    request.add_header("Authorization", "Basic %s" % base64string)
    response = json.load(urllib2.urlopen(request))

    if not response:
        raise BTSyncException(1, 'Empty response')

    if 'error' in response:
        raise BTSyncException(2, 'Response with error %d' % response['error'])

    if 'result' in response:
        raise BTSyncException(3, 'Response with result %d' % response['result'])

    return response
