#!/usr/bin/env python
"""
instaflickr.py
Purpose: copy original photos from Instagram from iPhone to Flickr
Steps:
  1. Get photos from Flickr which uploaded from Instagram and have size 612x612 px
  2. Match them with original photos from iPhone
  3. Upload bigger versions instead of smaller ones
"""

__author__ = 'rbd'

import os
import sys
import argparse
import operator
import math
import flickrapi
import urllib2
import json
from PIL import Image
from PIL import ImageChops
from PIL import ImageFilter
from os.path import join


IPHONE_IMAGES_DIR = '/Users/rbd/Pictures/iPhone'
FLICKR_IMAGES_DIR = 'flickr'
FLICKR_API_KEY = 'f162f2bd093e4b60d2167158a4d67513'
FLICKR_API_SECRET = '894b1682db64ea85'
FLICKR_SIZE_CODE = 'n'
COMPARER_IMAGE_SIZE = 10, 10  # should be corresponded to FLICKR_SIZE_CODE
COMPARER_THRESHOLD = 50  # threshold less that images threats the same


class Flickr:
    """Flickr-related tasks"""

    def __init__(self):
        self.connect()
        self.matched = []

    def connect(self):
        self.flickr = flickrapi.FlickrAPI(FLICKR_API_KEY, FLICKR_API_SECRET, format='json')
        (token, frob) = self.flickr.get_token_part_one(perms='write')
        if not token:
            raw_input("Press ENTER after you authorized this program")
        self.flickr.get_token_part_two((token, frob))

    def f2j(self, func, **kwds):
        """Executes FlickrAPI function and returns result as JSON"""
        rsp = func(**kwds)
        return json.loads(rsp[len('jsonFlickrAPI('):-1])

    def download_photos(self, page=1):
        """Downloads photos in local directory FLICKR_IMAGES_DIR"""

        downloaded_photos = os.listdir(FLICKR_IMAGES_DIR)
        photos = self.f2j(self.flickr.people_getPhotos, user_id='me', per_page=100, page=page)
        for photo in photos['photos']['photo']:
            if photo['id']+'.jpg' in downloaded_photos:
                continue
            url = self.construct_url(photo, 1, FLICKR_SIZE_CODE)
            info = self.f2j(self.flickr.photos_getInfo, photo_id=photo['id'])
            for tag in info['photo']['tags']['tag']:
                if tag['raw'] == 'instagram':
                    break
            else:
                if 'via Instagram' in info['photo']['description']['_content']:
                    remote_photo = urllib2.urlopen(url)
                    local_photo = open(join(FLICKR_IMAGES_DIR,
                                            '{}.jpg'.format(photo['id'])),
                                       'wb')
                    local_photo.write(remote_photo.read())
                    print('Processed photo {} - {}'.format(photo['id'], url))

    def replace_photos(self):
        try:
            file_matched = open('matched.txt', 'r')
            self.matched = [tuple(x.split('\t'))
                            for x in file_matched.read().splitlines()]
            file_matched.close()
        except IOError:
            pass
        map(self.replace_photo, [(x[0], x[1]) for x in self.matched if x[2] != 'replaced'])
        self.write_matched()

    def replace_photo(self, photo):
        id = photo[1][:-4]
        res = self.flickr.replace(filename=join(IPHONE_IMAGES_DIR, photo[0]),
                                  photo_id=id, format='rest')
        if '<rsp stat="ok">' in res:
            self.matched = [x if (x[0], x[1]) != photo
                            else (x[0], x[1], 'replaced') for x in self.matched]
            self.f2j(self.flickr.photos_addTags, photo_id=id, tags='instagram')
            print res
        return res

    def write_matched(self):
        file_matched = open('matched.txt', 'w')
        file_matched.writelines('\t'.join(x)+'\n' for x in self.matched)
        file_matched.close()

    def construct_url(self, photo, url_type=0, size='', format='jpg'):
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


class Comparer:
    """Compare photos"""

    def __init__(self):
        self.photos = []
        self.matched = []
        self.iphone_images_dir = IPHONE_IMAGES_DIR \
            if IPHONE_IMAGES_DIR[0] == '/' \
            else join(os.getcwd(), IPHONE_IMAGES_DIR)
        self.flickr_images_dir = FLICKR_IMAGES_DIR \
            if FLICKR_IMAGES_DIR[0] == '/' \
            else join(os.getcwd(), FLICKR_IMAGES_DIR)

    def _img_diff(self, im1, im2):
        diff = ImageChops.difference(im1, im2).convert('1')
        h1 = diff.histogram()
        return h1[0]

    def _rms(self, im1, im2):
        h1 = im1.histogram()
        h2 = im2.histogram()
        rms = math.sqrt(reduce(operator.add, map(lambda a, b: (a-b)**2, h1, h2))/len(h1))
        # print im1, im2, rms
        return rms

    def compare_photos(self, iphone_img, flickr_img):
        resize_mode = Image.ANTIALIAS
        im1 = Image.open(join(self.iphone_images_dir, iphone_img))
        im1 = im1.resize(COMPARER_IMAGE_SIZE, resize_mode)
        # im1 = im1.filter(ImageFilter.SHARPEN)
        im2 = Image.open(join(self.flickr_images_dir, flickr_img))
        im2 = im2.resize(COMPARER_IMAGE_SIZE, resize_mode)
        # im2 = im2.filter(ImageFilter.BLUR)
        # return self._rms(im1, im2)
        return self._img_diff(im1, im2)

    def calibrate(self):
        """Function compares identical images - for calibration"""
        try:
            file_matched = open('matched.txt', 'r')
            self.matched = [tuple(x.split('\t'))
                            for x in file_matched.read().splitlines()]
            file_matched.close()
        except IOError:
            return

        for pair in self.matched:
            iphone_img = pair[0]
            flickr_img = pair[1]

            cmp = self.compare_photos(iphone_img=iphone_img, flickr_img=flickr_img)
            print(iphone_img, flickr_img, cmp)
            # if cmp < COMPARER_THRESHOLD:
            if cmp == 100:
                print('MATCHED')
            else:
                print('NOT MATCHED')

    def compare_dirs(self):
        """Compares dirs file by file"""
        try:
            file_matched = open('matched.txt', 'r')
            self.matched = [tuple(x.split('\t'))
                            for x in file_matched.read().splitlines()]
        except IOError:
            pass

        file_matched = open('matched.txt', 'a', 0)

        def squared_img(img):
            img = Image.open(img)
            return img.size[0] == img.size[1]

        iphone_imgs = [x for x in sorted(os.listdir(self.iphone_images_dir), reverse=True)
                       if '.jpg' in x.lower() and
                          squared_img(join(self.iphone_images_dir, x)) and
                          x.lower() not in [y[0].lower() for y in self.matched]]
        flickr_imgs = [x for x in sorted(os.listdir(self.flickr_images_dir), reverse=True)
                       if '.jpg' in x.lower() and
                          x.lower() not in [y[1].lower() for y in self.matched]]

        print len(iphone_imgs)
        print len(flickr_imgs)

        for flickr_img in flickr_imgs:
            i = 0
            for iphone_img in iphone_imgs:
                cmp = self.compare_photos(iphone_img=iphone_img, flickr_img=flickr_img)
                i += 1
                # if cmp < COMPARER_THRESHOLD:
                if cmp == 100:
                    file_matched.write('{}\t{}\tnew\n'.format(iphone_img, flickr_img))
                    print(iphone_img, flickr_img, cmp)
                    iphone_imgs.remove(iphone_img)
                    break
                if i > 40:
                    print('{} not matched'.format(flickr_img))
                    break

        file_matched.close()

    def create_html(self, mode='new'):
        html_file = open('matched.html', 'w')
        try:
            file_matched = open('matched.txt', 'r')
            self.matched = [tuple(x.split('\t'))
                            for x in file_matched.read().splitlines()]
            file_matched.close()
        except IOError:
            pass

        size = 160, 160
        html_file.write('<html><body>')
        html_file.writelines('<p>{} <img src="file://{}" height={} width={}>'
                             ' <img src="file://{}" height={} width={}></p>\n'.format(
                             x[0],
                             os.path.join(self.iphone_images_dir, x[0]), size[0], size[1],
                             os.path.join(self.flickr_images_dir, x[1]), size[0], size[1])
                             for x in self.matched if x[2] == mode or mode == 'all')
        html_file.write('</body></html>')
        html_file.close()
        print('HTML created')


class Photo:
    def __init__(self, filename):
        self.photo = Image.open(filename)
        self.exif = self.photo._getexif()


def main():
    parser = argparse.ArgumentParser(description='Instagram-Flickr synchronizr')
    parser.add_argument('--mode',
                        help='Operational mode. '
                             'download -- downloads photos from Flickr, '
                             'compare -- compares photos, '
                             'replace -- replaces matched photos in Flickr',
                        required=True)
    parser.add_argument('--page', help='Page for download mode')
    args = vars(parser.parse_args())

    if args['mode'] == 'download':
        flickr = Flickr()
        flickr.download_photos(args['page'])
    elif args['mode'] == 'compare':
        comparer = Comparer()
        comparer.compare_dirs()
        comparer.create_html(mode='new')
    elif args['mode'] == 'replace':
        flickr = Flickr()
        flickr.replace_photos()

    # flickr.download_photos()
    # comparer.compare_dirs()
    # comparer.create_html(mode='new')
    # comparer.calibrate()


def photo_test():
    comparer = Comparer()
    dir = comparer.iphone_images_dir
    images = [x for x in os.listdir(dir) if '.jpg' in x.lower()]
    print images[0]
    photo1 = Photo(join(dir, images[0]))
    print photo1.exif


if __name__ == '__main__':
    main()
    # photo_test()