# -*- coding: utf-8 -*-

import os
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
    kw = dict((k, v) for k, v in kwargs.iteritems() if v is not None)
    args = urlencode(kw)
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


def btsync_files(secret, path=None):
    response = [x for x in request(method='get_files', secret=secret, path=path) if x['state'] != 'deleted']
    files = [dict(x, name=x['name'] if path is None else os.path.join(path, x['name']))
             for x in response if x['type'] == 'file']
    folders = filter(lambda x: x['type'] == 'folder', response)

    for folder in folders:
        files += btsync_files(secret, folder['name'] if path is None else os.path.join(path, folder['name']))

    return files
