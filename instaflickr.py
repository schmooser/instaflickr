# -*- coding: utf-8 -*-

import json
import urllib
import os.path
from flask import Flask, render_template, session, redirect, url_for, request, flash
from flaskext.zodb import ZODB

import btsync
import flickr


app = Flask(__name__)
app.config['ZODB_STORAGE'] = 'file://instaflickr.dbf'

db = ZODB(app)

params = json.load(open('instaflickr.json'))

flickr.SECRET = params['flickr']['secret']
flickr.PARAMS = params['flickr']

btsync.BASEURL = params['btsync']['server']
btsync.USERNAME = params['btsync']['username']
btsync.PASSWORD = params['btsync']['password']
btsync.logger = app.logger


@app.route('/')
def index():
    return render_template('index.html', params=params)


@app.route('/key', methods=['POST', 'GET'])
def key():

    # logging.debug('---headers---')
    # logging.debug(request.headers)
    # logging.debug('---args---')
    # logging.debug(request.args)
    # logging.debug('---form---')
    # logging.debug(request.form)

    if 'username' not in session:
        return render_template('key.html', params=params)
 
    key_name = 'key_'+session['username']

    if request.method == 'POST':
        try:
            key = request.form['key']
            db[key_name] = key
            session['key'] = key
            flash('Key has been saved successfully', 'success')
            return redirect(url_for('key'))
        except KeyError, e:
            app.logger.error(e.name)

    if db.has_key(key_name):
        key = db[key_name]
    else:
        key = None

    return render_template('key.html', params=params, key=key)


@app.route('/analyze')
def analyze():
    if 'username' not in session:
        return redirect(url_for('index'))

    if 'key' not in session:
        return redirect(url_for('key'))

    key = session['key']

    folder = btsync.request(method='get_folders', secret=key)
    app.logger.debug(folder)

    if folder:
        # this folder is already been synced - start analyzing photos
        return render_template('analyze.html', params=params, success=True)
    else:
        # a new folder to sync or wrong key
        dir = os.path.join(params['btsync']['basedir'], session['username'], 'originals')
        # todo: create directory here
        new_folder = btsync.request(method='add_folder', dir=dir, secret=key, selective_sync=1)

        if 'result' in new_folder:
            flash(message='Error {code}: {message}'.format(code=new_folder['result'], message=new_folder['message']),
                  category='danger')

            return render_template('analyze.html', params=params)

        return render_template('analyze.html', params=params, success=True)





    #sf = bts.add_sync_folder(name=os.path.join(params['btsync']['basedir'], session['username'], 'iPhone'),
    #                         secret=session['key'])


@app.route('/login')
def login():

    if 'username' in session:
        return redirect(url_for('index'))

    frob = request.args.get('frob', None)

    if frob is None:  # displaying login page
        url = params['flickr']['urls']['auth']
        url_params = {'api_key': flickr.PARAMS['api_key'],
                      'perms': flickr.PARAMS['perms'],
                      'format': flickr.PARAMS['format']}
        url_params = flickr.add_api_sig(url_params)
        query = urllib.urlencode(url_params)

        return render_template('login.html', params=params,
                               flickr_url=url+'?'+query)
    else:  # check auth from flickr
        response = flickr.request_method('flickr.auth.getToken', {'frob': frob})
        res = flickr.flickr_json(response)
        if res['stat'] == 'ok':
            session['username'] = res['auth']['user']['username']
            session['fullname'] = res['auth']['user']['fullname']
            session['flickr_response'] = res['auth']
            db['session_'+session['username']] = res['auth']
            key_name = 'key_'+session['username']
            if db.has_key(key_name):
                session['key'] = db[key_name]
            if params['site']['debug']:
                return render_template('login.html', params=params,
                                       stat=res['stat'], response=response)
            else:
                return redirect(url_for('index'))
        else:
            return render_template('login.html', params=params,
                                   stat=res['stat'], response=response)


@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('fullname', None)
    session.pop('flickr_response', None)
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.debug = True
    app.secret_key = 'qweoiruh1203y1qsbpiq234asboiuhhhhde'
    app.run(host='0.0.0.0')

