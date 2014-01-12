# -*- coding: utf-8 -*-

import json
import urllib
#import os.path
from flask import Flask, render_template, session, redirect, url_for, request, flash
from pymongo import MongoClient
from bson.objectid import ObjectId

import btsync
import flickr

params = json.load(open('instaflickr.json'))

app = Flask(__name__)
app.secret_key = 'qweoiruh1203y1qsbpiq234asboiuhhhhde'
app.debug = True
#app.config['ZODB_STORAGE'] = 'file://instaflickr.dbf'

mongoclient = MongoClient(params['mongo']['uri'])
db = mongoclient.instaflickr


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

    if 'username' not in session:
        return render_template('key.html', params=params)

    if request.method == 'POST':
        try:
            key = request.form['key']
            db_session = db.sessions.find_one({'_id': ObjectId(session['_id'])})
            app.logger.debug(db_session)
            db_session['key'] = key
            db.sessions.save(db_session)
            session['key'] = key
            flash('Key has been saved successfully', 'success')
            return redirect(url_for('key'))
        except KeyError, e:
            app.logger.error(e.name)

    if 'key' in session:
        key = session['key']
    else:
        key = None

    return render_template('key.html', params=params, key=key)


@app.route('/status')
def status():
    if 'username' not in session:
        return redirect(url_for('index'))

    pipelines = []
    pipelines.append({'$match': {'owner': session['nsid']}})
    pipelines.append({'$group': {'_id': '$instaflickr.status', 'count': {'$sum': 1}}})
    flickr = db.flickr.aggregate(pipelines)
    if flickr['ok'] == 1.0:
        flickr = flickr['result']

    pipelines = []
    pipelines.append({'$match': {'owner': session['username']}})
    pipelines.append({'$group': {'_id': '$download', 'count': {'$sum': 1}}})
    btsync = db.btsync.aggregate(pipelines)
    if btsync['ok'] == 1.0:
        btsync = btsync['result']

    statuses = [x for x in db.statuses.find({}, {'_id': 0})]

    statuses = dict(flickr=[x['statuses'] for x in statuses if x['module'] == 'flickr'][0],
                    btsync=[x['statuses'] for x in statuses if x['module'] == 'btsync'][0])
    statuses = dict(flickr=[x['name'] for x in sorted(statuses['flickr'], key=lambda x: x['code'])],
                    btsync=[x['name'] for x in sorted(statuses['btsync'], key=lambda x: x['code'])])

    return render_template('status.html', params=params, flickr=flickr, btsync=btsync, statuses=statuses)


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

        return render_template('login.html', params=params, flickr_url=url+'?'+query)
    else:  # check auth from flickr
        response = flickr.request_method('flickr.auth.getToken', {'frob': frob})
        res = flickr.flickr_json(response)

        if res['stat'] == 'ok':
            session['username'] = res['auth']['user']['username']
            session['fullname'] = res['auth']['user']['fullname']
            session['token'] = res['auth']['token']['_content']
            session['nsid'] = res['auth']['user']['nsid']

            db_session = db.sessions.find_one({'username': session['username']})

            if not db_session:
                id = db.sessions.insert({'username': session['username'],
                                         'fullname': session['fullname'],
                                         'perms': res['auth']['perms']['_content'],
                                         'token': session['token'],
                                         'nsid': res['auth']['user']['nsid']})
                app.logger.debug(id)
                db_session = {'_id': id}
            session['_id'] = str(db_session['_id'])

            if 'key' in db_session:
                session['key'] = db_session['key']

            if params['site']['debug']:
                return render_template('login.html', params=params, stat=res['stat'], response=response)
            else:
                return redirect(url_for('index'))
        else:
            return render_template('login.html', params=params, stat=res['stat'], response=response)


@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('fullname', None)
    session.pop('key', None)
    session.pop('token', None)
    session.pop('nsid', None)
    # print(url_for('index'))
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0')

