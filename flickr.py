# -*- coding: utf-8 -*-

from hashlib import md5
import urllib2
import json
from urllib import urlencode

SECRET = 'flickr_secret_key'
PARAMS = None


def add_api_sig(params):
    m = md5(SECRET)
    m.update(''.join(sorted([str(x)+str(params[x]) for x in params.keys()])))
    api_sig = m.hexdigest()
    params['api_sig'] = api_sig
    return params
    

def request_method(method, values):
    attrs = {}
    for attr in PARAMS['methods'][method]:
        if attr in PARAMS:
            attrs[attr] = PARAMS[attr]
        if attr in values:
            attrs[attr] = values[attr]
    attrs['method'] = method
    attrs = add_api_sig(attrs)
    url = PARAMS['urls']['rest']+'?'+urlencode(attrs)
    response = urllib2.urlopen(url)
    return response.read()


def flickr_json(data):
    data = data[len('jsonFlickrApi('):-1]
    return json.loads(data)
    
    

