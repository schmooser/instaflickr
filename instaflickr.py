
import json
from hashlib import md5
import urlparse as urlparse  # replaced with url.parse in Python 3
import urllib
from flask import Flask
from flask import render_template
from flask import request

import flickr


app = Flask(__name__)

params = json.load(open('instaflickr.json'))

flickr.SECRET = params['flickr']['secret']
flickr.PARAMS = params['flickr']

@app.route("/")
def index():
    return render_template('index.html')


@app.route("/hello/")
@app.route("/hello/<name>")
def hello(name=None):
    return render_template('block.html', name=name, params=params)


@app.route("/login")
def login():
    frob = request.args.get('frob', None)
    if frob is None:  # displaying login page
        url = params['flickr']['urls']['auth']
        url_params = {'api_key': params['flickr']['api_key'],
                      'perms': params['flickr']['perms']}
        url_params = flickr.add_api_sig(url_params)
        query = urllib.urlencode(url_params)

        return render_template('login.html', params=params,
                               flickr_url=url+'?'+query)
    else:  # check auth from flickr
        response = flickr.request_method('flickr.auth.getToken',
                                         {'frob': frob})
        return render_template('login.html', params=params,
                                response=response)

if __name__ == "__main__":
    app.debug = True
    app.run(host='0.0.0.0')

