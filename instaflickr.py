#!/usr/bin/env python
import os
import flickrapi
import json
import urllib2
import Image

FLICKR_API_KEY = 'f162f2bd093e4b60d2167158a4d67513'
FLICKR_API_SECRET = '894b1682db64ea85'
FLICKR_SIZE_CODE = 'n'

ORIGINAL_IMAGES_DIR = '/Users/rbd/Pictures'
IMAGE_SIZE = 320, 320


def construct_flickr_url(photo, url_type=0, size='', format='jpg'):
    pattern = ('http://farm{farm-id}.staticflickr.com/{server-id}/{id}_{secret}.jpg',
               'http://farm{farm-id}.staticflickr.com/{server-id}/{id}_{secret}_[mstzb].jpg',
               'http://farm{farm-id}.staticflickr.com/{server-id}/{id}_{o-secret}_o.(jpg|gif|png)')
    res = pattern[url_type]
    res = res.replace('{farm-id}', str(photo['farm']))
    res = res.replace('{server-id}', photo['server'])
    res = res.replace('{id}', photo['id'])
    res = res.replace('{secret}', photo['secret'])
    if url_type==1:
        res = res.replace('[mstzb]', size)
    if url_type==2:
        res = res.replace('{o-secret}', photo['o-secret'])
        res = res.replace('(jpg|gif|png)', format)
    return res


def people_getPhotos(**kwds):
    rsp = flickr.people_getPhotos(**kwds)
    rsp = rsp[len('jsonFlickrApi('):-1]
    return json.loads(rsp)


def photos_getInfo(**kwds):
    rsp = flickr.photos_getInfo(**kwds)
    rsp = rsp[len('jsonFlickrApi('):-1]
    return json.loads(rsp)

flickr = flickrapi.FlickrAPI(FLICKR_API_KEY, FLICKR_API_SECRET, format='json')

(token, frob) = flickr.get_token_part_one(perms='write')
if not token: raw_input("Press ENTER after you authorized this program")
flickr.get_token_part_two((token, frob))


def save_flickr_photos():
    res = people_getPhotos(user_id='me', per_page=5)

    for photo in res['photos']['photo']:
        #print photo
        photo_url = construct_flickr_url(photo, 1, FLICKR_SIZE_CODE)
        print photo_url
        photo_info = photos_getInfo(photo_id=photo['id'])

        for tag in photo_info['photo']['tags']['tag']:
            if tag['raw'] == 'instagram_original':
                break
        else:
            if 'via Instagram' in photo_info['photo']['description']['_content']:
                remote_photo = urllib2.urlopen(photo_url)
                local_photo = open('img/flickr/%s.jpg' % photo['id'], 'wb')
                local_photo.write(remote_photo.read())
                print 'Processed photo %s' % photo['id']


def create_iphone_thumbnails():
    for img in os.listdir(ORIGINAL_IMAGES_DIR):
        print 'Processing %s' % img

        if img[-4:] != '.jpg':
            continue

        img = Image.open('%s/%s' % (ORIGINAL_IMAGES_DIR, img))
        img = img.resize(IMAGE_SIZE, Image.ANTIALIAS)
        img.save('img/iphone/%s' % img, 'JPEG', quality=90)
        img.close()

        print 'Done'


def bridge_flickr_to_iphone():
    pass


def upload_to_flickr():
    pass


if __name__ == '__main__':
    # save_flickr_photos()
    print "I've been running"


# print rsp[0][0]

# r1 = flickr.__flickr_call(
# 	        method='flickr.people.getPhotos',
# 	        user_id='me',
# 	        per_page=5,
# 	        format='json')

# print r1
