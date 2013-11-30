#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Purpose: copy original photos from Instagram from iPhone to Flickr

Steps:
  1. Get photos from Flickr
  2. Get photos from BTSync
  3. Upload matched photos to Flickr

Session statuses:
    { "code" : 0, "name" : "All done" }
    { "code" : 1, "name" : "Downloading from Flickr" }
    { "code" : 2, "name" : "Waiting for BTSync key" }
    { "code" : 3, "name" : "Syncing via BTSync" }
    { "code" : 4, "name" : "Comparing photos" }
    { "code" : 5, "name" : "Uploading to Flickr" }
"""

import os
import logging
import json
import urllib2

import flickrapi
from pymongo import MongoClient
#from mongolog.handlers import MongoHandler

import bitops
import btsync


# params
params = json.load(open('instaflickr.json'))


# logging
#flickrapi.set_log_level(logging.DEBUG)
FORMAT = '%(asctime)s %(levelname)-10s %(module)-10s %(funcName)-20s: %(message)s'
LOGLEVEL = logging.DEBUG

logger = logging.getLogger(__name__)
logger.setLevel(LOGLEVEL)


def logger_setup(logger):
    formatter = logging.Formatter(fmt=FORMAT, datefmt='%Y-%m-%d %H:%M:%S')

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(LOGLEVEL)
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler('instaflickr.log')
    file_handler.setLevel(LOGLEVEL)
    file_handler.setFormatter(formatter)

    #par = params['mongo']
    #mongo_handler = MongoHandler(collection='log', db=par['db'], host=par['host'],
    #                             port=par['port'], username=par['username'], password=par['password'],
    #                             level=LOGLEVEL)

    logger.addHandler(stream_handler)
    #logger.addHandler(mongo_handler)
    logger.addHandler(file_handler)


# flickr constants
FLICKR_API_KEY = params['flickr']['api_key']
FLICKR_API_SECRET = params['flickr']['secret']


# btsync constants
btsync.BASEURL = params['btsync']['server']
btsync.USERNAME = params['btsync']['username']
btsync.PASSWORD = params['btsync']['password']
btsync.logger = logger
MAX_SIZE = params['site']['max_size'] * 1024 * 1024


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
    logger.debug('start')
    response = func(**kwds)
    # logger.debug('response: %s', response)
    return json.loads(response[len('jsonFlickrAPI('):-1])


class Flickr:
    """Flickr-related stuff"""

    FLICKR_SIZE_CODE = 'n'

    def __init__(self, token):
        self.flickr = flickrapi.FlickrAPI(api_key=FLICKR_API_KEY, secret=FLICKR_API_SECRET, format='json',
                                          token=token, store_token=False)
        self.matched = []

    def photos(self):
        """Returns list of photos"""
        logger.debug('start')
        photos = []
        i = 1
        while True:
            page = flickr2json(self.flickr.people_getPhotos, user_id='me', per_page=500, page=i)['photos']
            #logger.debug(page)
            if page['total'] == 0:
                break
            photos += page['photo']
            i += 1
        return photos

    def download_photos(self, photos, dir):
        """Download photos in local directory dir"""
        logger.debug('start')
        logger.debug('processing %d photos', len(photos))
        i = 0
        for index, photo in enumerate(photos):
            i += 1
            info = flickr2json(self.flickr.photos_getInfo, photo_id=photo['id'])
            href = info['photo']['urls']['url'][0]['_content']
            url = construct_flickr_url(photo, 1, self.FLICKR_SIZE_CODE)

            # don't download already replaced photo
            if 'instagram' in [x['raw'] for x in info['photo']['tags']['tag']]:
                logger.info('%d. Photo %s already replaced', i, href)
                photos[index]['instaflickr'] = {'status': 3}
                continue
            else:
                if 'instagram' in str(info).lower() or 'iPhone' in [x['raw'] for x in info['photo']['tags']['tag']]:
                    remote_photo = urllib2.urlopen(url)
                    local_photo = os.path.join(dir, photo['id'] + '.jpg')
                    logger.debug('local photo: %s', local_photo)
                    local_photo = open(local_photo, 'wb')
                    local_photo.write(remote_photo.read())
                    logger.info('%d. Downloaded photo %s', i, href)
                    photos[index]['instaflickr'] = {'status': 1}
                else:
                    logger.info('%d Photo %s doesn\'t seem to come from Instagram', i, href)
                    photos[index]['instaflickr'] = {'status': 2}

        return photos

    def replace_photo(self, photo, dir):
        id = photo['id']
        res = self.flickr.replace(filename=os.path.join(dir, photo['name']),
                                  photo_id=id, format='rest')
        if '<rsp stat="ok">' in res:
            flickr2json(self.flickr.photos_addTags, photo_id=id, tags='instagram')
            logger.info('Photo {id} has been replaced'.format(photo['id']))
            return True
        else:
            return False


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
    btsyncdir = os.path.join(userdir, 'btsync')
    #btsyncdir = os.path.join('/home/rbd/instaflickr/assets', session['username'], 'btsync')
    flickrdir = os.path.join(userdir, 'flickr')
    return userdir, flickrdir, btsyncdir


def download_from_btsync(session):
    """Download from btsync and saves data to DB
       In db.btsync `download` flag has the following meaning:
         0 - not synced via btsync
         1 - synced via btsync
         2 - processed and uploaded to Flickr but synced via btsync
         3 - processed and uploaded to Flickr and unsynced via btsync
    """
    logger.debug('start')

    status = session['status']

    dir = get_dirs(session)[2]
    if dir[0] != '/':  # used relative path
        dir = os.path.join(os.getcwd(), dir)

    if 'key' not in session:
        return
    key = session['key']

    folder = btsync.request(method='get_folders', secret=key)
    if not folder:  # folder is already added to sync
        logger.debug('adding folder: %s', dir)
        response = btsync.request(method='add_folder', dir=dir, secret=key, selective_sync=1)
        if response['result'] != 0:
            logger.error('btsync error: %s', response)
        return  # process files on the next run when some images will be downloaded

    check_filename = lambda x: x['name'].lower()[-4:] == '.jpg'  # get only jpegs
    files = filter(check_filename, btsync.request(method='get_files', secret=key))

    db_files = []
    for file in db.btsync.find({'owner': session['username']}):  # files already in db
        db_files.append(file)

    new_files = filter(lambda x: x['name'] not in [x['name'] for x in db_files], files)
    new_files = [dict(owner=session['username'], name=x['name'], size=x['size'], download=x['download'])
                 for x in new_files]
    logger.info('found %d new files', len(new_files))
    if new_files:
        db.btsync.insert(new_files)
        status = bitops.add(status, 1)

    db_files += new_files

    def download(*statuses):
        #logger.debug(session)
        def f(x):
            return x['download'] in statuses
        return f

        logger.debug(session)
        logger.debug(session)

    # unsync processed files and remove them from disk to save the space
    for file in filter(download(2), db_files):
        logger.debug('stopping sync file %s', file['name'])
        response = btsync.request(method='set_file_prefs', secret=key, path=file['name'], download=0)
        logger.debug('response from btsync on file %s: %s', file['name'], response)
        os.remove(os.path.join(dir, file['name']))
        file['download'] = 3
        db.btsync.save(file)

    # sync new files to processing

    #size = sum([os.path.getsize(f) for f in os.listdir(dir) if os.path.isfile(f)])
    size = sum([x['size'] for x in filter(download(1), db_files)])
    logger.info('occupied space: %.2f MB', size / 1024.0 / 1024.0)

    for file in sorted(filter(download(0), db_files), key=lambda x: x['name'], reverse=True):  # in descending order
        size += file['size']
        if size >= MAX_SIZE:  # if quota reached - stop loop
            break
        logger.debug('synced file: %s', file)
        response = btsync.request(method='set_file_prefs', secret=key, path=file['name'], download=1)
        logger.info('response from btsync on file %s: %s', file['name'], response)
        file['download'] = 1
        db.btsync.save(file)

    if not filter(download(0, 1, 2), db_files):
        logger.info('All files synced, uploaded to Flickr and cleaned up')
        status = bitops.sub(status, 3)  #

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
    """Download photos from Flickr.

    Statuses in db.flickr collection:
        0 - not downloaded
        1 - downloaded
        2 - not from instagram
        3 - replaced
    """
    logger.debug('start')
    flickr = Flickr(token=session['token'])
    dir = get_dirs(session)[1]

    # saving photos info to db
    photos = flickr.photos()  # all user photos
    logger.info('%s has %d photos', session['username'], len(photos))
    db_photos = [x for x in db.flickr.find({'owner': session['nsid']})]  # photos already in db
    photos = [x for x in photos if x['id'] not in [y['id'] for y in db_photos]]  # new photos
    logger.info('found %d new photos', len(photos))
    if photos:
        db.flickr.insert([dict(x, instaflickr={'status': 0}) for x in photos])

    # downloading images from flickr
    photos = [x for x in db.flickr.find({'owner': session['nsid'], 'instaflickr': {'status': 0}})]
    logger.info('%d photos to download', len(photos))
    photos = flickr.download_photos(photos, dir)
    for photo in photos:
        db.flickr.save(photo)

    status = bitops.sub(session['status'], 1)
    save_status(session, status)


def upload_to_flickr(session):
    """Upload matched photos to Flickr"""
    logger.debug('start')
    flickr = Flickr(token=session['token'])
    dir = get_dirs(session)[2]
    matches = db.matches.find({'status': 1, 'owner': session['username']})
    photos = db.btsync.find({'download': 1, 'owner': session['username']})

    logger.info('found %d files to upload', matches.count())

    for match in matches:
        if flickr.replace_photo(match['photo'], dir):
            match['status'] = 2
            db.matches.save(match)
            photo = filter(lambda x: x['name'] == match['photo']['name'], photos)[0]
            db.btsync.save(photo)

    status = bitops.sub(session['status'], 4)
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
    logger.debug('start')
    logger.debug('session: %s', session)
    logger.debug('%s\'s session status: %d (%s)', session['username'], session['status'], str(bin(session['status'])))

    if session['status'] == -1:  # new session, need to create folders
        initial_status(session)

    check_state(session)

    if session['status'] & 1 << 0 == 1 << 0:  # status includes Downloading from Flickr
        download_from_flickr(session)

    if session['status'] & 1 << 1 == 1 << 1:  # status includes Waiting for key
        wait_for_key(session)

    if session['status'] & 1 << 2 == 1 << 2:  # status includes Downloading from BTSync
        download_from_btsync(session)

    if session['status'] & 1 << 4 == 1 << 4:  # status includes Uploading to Flickr
        upload_to_flickr(session)


def save_status(session, status):
    logger.debug('start')
    logger.info('%s\'s session old status: %d (%s)', session['username'], session['status'], str(bin(session['status'])))
    logger.info('%s\'s session new status: %d (%s)', session['username'], status, str(bin(status)))
    session['status'] = status
    #db.sessions.save(session)


def main():
    logger_setup(logger)
    sessions = db.sessions.find()
    #sessions = db.sessions.find({'username': 'schmooser'})
    for session in sessions:
        if 'status' not in session:
            session['status'] = -1
        process(session)


if __name__ == '__main__':
    main()



