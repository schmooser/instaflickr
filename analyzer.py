#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
analyzer.py
Purpose: copy original photos from Instagram from iPhone to Flickr
Steps:
  1. Get photos from Flickr which uploaded from Instagram and have size 612x612 px
  2. Match them with original photos from iPhone
  3. Upload bigger versions instead of smaller ones


Session statuses:
    { "code" : 0, "name" : "All done" }
    { "code" : 1, "name" : "Downloading from Flickr" } 1 << 0
    { "code" : 2, "name" : "Waiting for BTSync key" }  1 << 1
    { "code" : 3, "name" : "Syncing via BTSync" }      1 << 2
    { "code" : 4, "name" : "Comparing photos" }        1 << 3
    { "code" : 5, "name" : "Uploading to Flickr" }     1 << 4

"""

import json
import os
import logging
import urllib2
import flickrapi
from pymongo import MongoClient
#from bson.objectid import ObjectId
from mongolog.handlers import MongoHandler

import bitops
import btsync


# params
params = json.load(open('instaflickr.json'))


# logging
#flickrapi.set_log_level(logging.DEBUG)
FORMAT = '%(levelname)s %(module)s %(funcName)s: %(message)s'
LOGLEVEL = logging.DEBUG
#logging.basicConfig()
logger = logging.getLogger('instaflickr')
logger.setLevel(LOGLEVEL)

fmt = logging.Formatter(FORMAT)

hdlr = logging.StreamHandler()
hdlr.setLevel(LOGLEVEL)
hdlr.setFormatter(fmt)

mngpar = params['mongo']
mnghdlr = MongoHandler(collection='log', db=mngpar['db'], host=mngpar['host'],
                       port=mngpar['port'], username=mngpar['username'], password=mngpar['password'],
                       level=LOGLEVEL)

logger.addHandler(hdlr)
logger.addHandler(mnghdlr)


# flickr constants
FLICKR_API_KEY = params['flickr']['api_key']
FLICKR_API_SECRET = params['flickr']['secret']


# btsync constants
btsync.BASEURL = params['btsync']['server']
btsync.USERNAME = params['btsync']['username']
btsync.PASSWORD = params['btsync']['password']
btsync.logger = logger
MAX_SIZE = params['site']['max_size']*1024*1024


# mongo vars
mongoclient = MongoClient(params['mongo']['uri'])
db = mongoclient[params['mongo']['db']]


# statuses
statuses = {}
for status in db.statuses.find({}, {'_id': 0}):
    statuses[int(status['code'])] = status['name']
    statuses[status['name']] = int(status['code'])


def flickr2json(func, **kwds):
    """Executes FlickrAPI function and returns result as JSON"""
    response = func(**kwds)
    return json.loads(response[len('jsonFlickrAPI('):-1])


class Flickr:
    """Flickr-related stuff"""

    FLICKR_IMAGES_DIR = '.'
    IPHONE_IMAGES_DIR = '.'
    FLICKR_SIZE_CODE = 'n'

    def __init__(self, token):
        self.flickr = flickrapi.FlickrAPI(api_key=FLICKR_API_KEY, secret=FLICKR_API_SECRET, format='json',
                                          token=token, store_token=False)
        self.matched = []

    def photos(self):
        """Returns list of photos"""
        photos = []
        i = 1
        while True:
            page = flickr2json(self.flickr.people_getPhotos, user_id='me', per_page=6, page=i)['photos']
            if page['total'] == 0 or i > 1:
                break
            #logger.debug(page)
            photos += page['photo']
            i += 1
        return photos

    def download_photos(self, photos, dir):
        """Downloads photos in local directory dir"""

        i = 0

        for photo in photos:
            i += 1

            info = flickr2json(self.flickr.photos_getInfo, photo_id=photo['id'])
            href = info['photo']['urls']['url'][0]['_content']
            url = construct_flickr_url(photo, 1, self.FLICKR_SIZE_CODE)

            # don't download already replaced photo
            if 'instagram' in [x['raw'] for x in info['photo']['tags']['tag']]:
                logger.info('{n}. Photo {id} {href} already replaced'.format(n=i, id=photo['id'], href=href))
                break
            else:
                # if 'via Instagram' in info['photo']['description']['_content']:
                if 'instagram' in str(info).lower() or \
                                'iPhone' in [x['raw'] for x in info['photo']['tags']['tag']]:
                    remote_photo = urllib2.urlopen(url)
                    local_photo = open(os.path.join(dir, '{}.jpg'.format(photo['id'])), 'wb')
                    local_photo.write(remote_photo.read())
                    logger.info('{}. Processed photo {} {}'.format(i, photo['id'], href))
                else:
                    logger.info('{}. Photo {} - {} doesn\'t seem to come from Instagram'.format(i, photo['id'], href))

    #def replace_photos(self):
    #    comparer = Comparer()
    #    self.matched = comparer.matched
    #    self.file_replaced = open('replaced.txt', 'a', 0)
    #    map(self.replace_photo, [(x[0], x[1]) for x in self.matched if x[2] == 'new'])
    #    self.file_replaced.close()
    #    self.write_matched()
    #
    #def replace_photo(self, photo):
    #    id = photo[1][:-4]
    #    res = self.flickr.replace(filename=os.path.join(self.IPHONE_IMAGES_DIR, photo[0]),
    #                              photo_id=id, format='rest')
    #    if '<rsp stat="ok">' in res:
    #        self.matched = [x if (x[0], x[1]) != photo
    #                        else (x[0], x[1], 'replaced') for x in self.matched]
    #        self.f2j(self.flickr.photos_addTags, photo_id=id, tags='instagram')
    #        self.file_replaced.write('{}\treplaced\n'.format(id))
    #        print('Photo {} has been replaced'.format(id))
    #        return True
    #    else:
    #        return False
    #
    #def write_matched(self):
    #    file_matched = open('matched.txt', 'w')
    #    file_matched.writelines('\t'.join(x)+'\n' for x in self.matched)
    #    file_matched.close()


def construct_flickr_url(photo, url_type=0, size='', format='jpg'):
    #logger.debug(photo)
    pattern = ('http://farm{farm-id}.staticflickr.com/{server-id}/{id}_{secret}.jpg',
               'http://farm{farm-id}.staticflickr.com/{server-id}/{id}_{secret}_[mstzb].jpg',
               'http://farm{farm-id}.staticflickr.com/{server-id}/{id}_{o-secret}_o.(jpg|gif|png)')
    res = pattern[url_type]
    res = res.replace('{farm-id}', str(photo['farm']))
    res = res.replace('{server-id}', photo['server'])
    res = res.replace('{id}', photo['id'])
    res = res.replace('{secret}', photo['secret'])
    if url_type == 1:
        res = res.replace('[mstzb]', size)
    if url_type == 2:
        res = res.replace('{o-secret}', photo['o-secret'])
        res = res.replace('(jpg|gif|png)', format)
    return res


def get_dirs(session):
    basedir = params['storage']['basedir']
    userdir = os.path.join(basedir, session['username'])
    #btsyncdir = os.path.join(userdir, 'btsync')
    btsyncdir = os.path.join('/home/rbd/instaflickr/assets', session['username'], 'btsync')
    flickrdir = os.path.join(userdir, 'flickr')
    return userdir, flickrdir, btsyncdir


def download_from_btsync(session):
    logger.debug('start')
    dir = get_dirs(session)[2]
    if 'key' not in session:
        return
    key = session['key']
    folder = btsync.request(method='get_folders', secret=key)
    if not folder:  # folder is already added to sync
        logger.debug('adding folder: %s', dir)
        response = btsync.request(method='add_folder', dir=dir, secret=key, selective_sync=1)
        if response['result'] != 0:
            logger.error('btsync error: %s', response)

    check_filename = lambda x: x['name'].lower()[-4:] == '.jpg'  # get only jpegs
    files = filter(check_filename, btsync.request(method='get_files', secret=key))

    db_files = []
    for file in db.btsync.find({'owner': session['username']}, {'_id': 0, 'owner': 0}):  # files already in db
        db_files.append(file)

    new_files = filter(lambda x: x['name'] not in [x['name'] for x in db_files], files)
    logger.info('number of new files: %d', len(new_files))

    changed_files = filter(lambda x: x not in db_files, files)
    logger.info('number of changed files: %d', len(changed_files))

    for file in changed_files:
        if file in new_files:
            continue
        db.btsync.remove({'owner': session['username'], 'name': file['name']})
        file['owner'] = session['username']
        db.btsync.save(file)

    new_files = [dict(x, owner=session['username']) for x in new_files]
    if new_files:
        db.btsync.insert(new_files)

    synced_files = []

    size = sum(map(lambda x: x['size'], filter(lambda x: x['download'] == 1, files)))
    logger.info('occupied space: %.2f MB', size/1024.0/1024.0)

    #not_synced = lambda x: x['download'] == 0

    total_size = 0
    for file in sorted(files, key=lambda x: x['name'], reverse=True):  # in descending order
        total_size += file['size']
        if total_size >= MAX_SIZE:  # if quota reached - stop loop
            break
        logger.debug('synced file: %s', file)
        if file['download'] == 0:  # if file is not being downloaded - download it
            response = btsync.request(method='set_file_prefs', secret=key, path=file['name'], download=1)
            logger.info('response from btsync on file %s: %s', file['name'], response)
        synced_files.append(file)

    if not filter(lambda x: x['have_pieces'] < x['total_pieces'], files):
        logger.info('All files synced')
        status = bitops.sub(session['status'], 3)  #
        save_status(session, status)

    #logger.debug('response from btsync: %s', response)


def initial_status(session):
    logger.debug('start')
    userdir, flickrdir, btsyncdir = get_dirs(session)
    if not os.path.exists(userdir):
        os.makedirs(userdir)
        os.makedirs(btsyncdir)
        os.makedirs(flickrdir)
    if 'key' in session:
        status = bitops.create(1, 3, 4, 5)  # Download from BTSync and synchronize
    else:
        status = bitops.create(1, 2)  # Downloading from Flickr and wait for a key
    save_status(session, status)


def wait_for_key(session):
    logger.debug('start')
    if 'key' in session:
        status = session['status']
        session['status'] = bitops.create(1, 3, 4, 5) | status
        save_status(session, status)


def download_from_flickr(session):
    logger.debug('start')
    flickr = Flickr(token=session['token'])
    dir = get_dirs(session)[1]

    # saving photos info to db
    photos = flickr.photos()  # all user photos
    db_photos = db.flickr.find({'owner': session['nsid']}, {'_id': 0})  # ids already in db
    photos = filter(lambda x: x not in db_photos, photos)  # new photos
    logger.debug('new photos: %s', photos)
    if photos:
        db.flickr.insert(photos)

    # downloading images from flickr
    photos = db.flickr.find({'owner': session['nsid']}, {'_id': 0})  # ids already in db
    downloaded_photos = os.listdir(dir)
    logger.debug('already downloaded photos: %s', downloaded_photos)
    photos = filter(lambda x: x['id']+'.jpg' not in downloaded_photos, photos)
    flickr.download_photos(photos, dir)


    status = bitops.sub(session['status'], 1)
    save_status(session, status)


def check_state(session):
    logger.debug('start')
    status = session['status']
    if 'key' not in session:
        status = bitops.sub(status, 3)
        status = bitops.sub(status, 4)
        status = bitops.sub(status, 5)
        status = bitops.add(status, 2)
        save_status(session, status)


def process(session):
    logger.debug('session: %s', session)

    if session['status'] == -1:  # new session, need to create folders
        initial_status(session)

    check_state(session)

    if session['status'] & 1 << 0 == 1 << 0:  # status includes Downloading from Flickr
        download_from_flickr(session)

    if session['status'] & 1 << 1 == 1 << 1:  # status includes Waiting for key
        wait_for_key(session)

    if session['status'] & 1 << 2 == 1 << 2:  # status includes Downloading from BTSync
        download_from_btsync(session)

    session['status'] = 0

    if session['status'] != 0:
        process(session)


def save_status(session, status):
    session['status'] = status
    db.sessions.save(session)


def main():
    sessions = db.sessions.find()
    #sessions = db.sessions.find({'username': 'schmooser'})
    for session in sessions:
        if 'status' not in session:
            session['status'] = -1
        process(session)


if __name__ == '__main__':
    main()



