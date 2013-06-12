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
FLICKR_IMAGES_DIR = join(os.getcwd(), 'flickr')
FLICKR_API_KEY = 'f162f2bd093e4b60d2167158a4d67513'
FLICKR_API_SECRET = '894b1682db64ea85'
FLICKR_SIZE_CODE = 'n'
COMPARER_IMAGE_SIZE = 10, 10


class Flickr:
    """Flickr-related stuff"""

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
        photos = self.f2j(self.flickr.people_getPhotos, user_id='me', per_page=500, page=page)
        i = 0

        for photo in photos['photos']['photo']:
            i += 1

            if photo['id']+'.jpg' in downloaded_photos:
                print('{}. Photo {} already downloaded'.format(i, photo['id']))
                continue

            info = self.f2j(self.flickr.photos_getInfo, photo_id=photo['id'])
            href = info['photo']['urls']['url'][0]['_content']
            url = self.construct_url(photo, 1, FLICKR_SIZE_CODE)

            # don't download already replaced photo
            if 'instagram' in [x['raw'] for x in info['photo']['tags']['tag']]:
                print('{}. Photo {} - {} already replaced'.format(i, photo['id'], href))
                break
            else:
                # if 'via Instagram' in info['photo']['description']['_content']:
                if 'instagram' in str(info).lower() or \
                   'iPhone' in [x['raw'] for x in info['photo']['tags']['tag']]:
                    remote_photo = urllib2.urlopen(url)
                    local_photo = open(join(FLICKR_IMAGES_DIR, '{}.jpg'.format(photo['id'])), 'wb')
                    local_photo.write(remote_photo.read())
                    print('{}. Processed photo {} - {}'.format(i, photo['id'], href))
                else:
                    print('{}. Photo {} - {} doesn\'t seem to be from Instagram'.format(i, photo['id'], href))

    def replace_photos(self):
        try:
            file_matched = open('matched.txt', 'r')
            self.matched = [tuple(x.split('\t')) for x in file_matched.read().splitlines()]
            file_matched.close()
        except IOError:
            pass
        map(self.replace_photo, [(x[0], x[1]) for x in self.matched if x[2] == 'new'])
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
        self.iphone_imgs = []
        self.flickr_imgs = []
        try:
            file_matched = open('matched.txt', 'r')
            self.matched = [tuple(x.split('\t')) for x in file_matched.read().splitlines()]
            file_matched.close()
        except IOError:
            self.matched = []

        try:
            file_squared = open('squared.txt', 'r')
            self.squared = [x for x in file_squared.read().splitlines()]
            file_squared.close()
        except IOError:
            self.squared = []

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

    def compare_photos(self, iphone_img, flickr_img, mode='image'):
        if mode == 'image':
            return self._img_diff(iphone_img, flickr_img) == 100
        elif mode == 'path':
            resize_mode = Image.ANTIALIAS
            im1 = Image.open(join(IPHONE_IMAGES_DIR, iphone_img))
            im1 = im1.resize(COMPARER_IMAGE_SIZE, resize_mode)
            im2 = Image.open(join(FLICKR_IMAGES_DIR, flickr_img))
            im2 = im2.resize(COMPARER_IMAGE_SIZE, resize_mode)
            return self._img_diff(im1, im2) == 100
        else:
            return False

    def calibrate(self):
        """Function compares identical images - for calibration"""

        for photo in self.matched:
            iphone_img = photo[0]
            flickr_img = photo[1]

            cmp = self.compare_photos(iphone_img=iphone_img, flickr_img=flickr_img, mode='path')
            print(iphone_img, flickr_img, cmp)
            if cmp:
                print('MATCHED')
            else:
                print('NOT MATCHED')

    def load_images(self):

        def open(image):
            resize_mode = Image.ANTIALIAS
            print('Loading {}'.format(image))
            return Image.open(image).resize(COMPARER_IMAGE_SIZE, resize_mode)

        self.iphone_imgs = [(x, open(join(IPHONE_IMAGES_DIR, x)))
                            for x in sorted(os.listdir(IPHONE_IMAGES_DIR), reverse=True)
                            if '.jpg' in x.lower() and
                               x in self.squared and
                               x not in [y[0] for y in self.matched]]

        self.flickr_imgs = [(x, open(join(FLICKR_IMAGES_DIR, x)))
                            for x in sorted(os.listdir(FLICKR_IMAGES_DIR), reverse=True)
                            if '.jpg' in x.lower() and
                               x not in [y[1] for y in self.matched]]

    def compare_dirs(self, attempts=40):
        """Compares dirs file by file"""

        file_matched = open('matched.txt', 'a', 0)

        if self.iphone_imgs == [] and self.flickr_imgs == []:
            self.load_images()

        print('Comparing {} iPhone images with {} Flickr images'.format(len(self.iphone_imgs), len(self.flickr_imgs)))

        for flickr_img in self.flickr_imgs:
            i = 0
            for iphone_img in self.iphone_imgs:
                i += 1
                if self.compare_photos(iphone_img=iphone_img[1], flickr_img=flickr_img[1]):
                    file_matched.write('{}\t{}\tnew\n'.format(iphone_img[0], flickr_img[0]))
                    print('{} matched to {} in {} attempts'.format(flickr_img[0], iphone_img[0], i))
                    self.iphone_imgs.remove(iphone_img)
                    break
                if i > attempts:
                    # file_matched.write('---\t{}\tnot matched\n'.format(flickr_img[0]))
                    print('{} not matched in {} attempts'.format(flickr_img[0], i))
                    break

        file_matched.close()

    def squared_list(self):
        def squared_img(img):
            img = Image.open(img)
            return img.size[0] == img.size[1]
        squared_imgs = [x+'\n' for x in sorted(os.listdir(IPHONE_IMAGES_DIR))
                        if '.jpg' in x.lower() and squared_img(join(IPHONE_IMAGES_DIR, x))]
        try:
            file_squared = open('squared.txt', 'w')
            file_squared.writelines(squared_imgs)
            file_squared.close()
        except IOError:
            pass

    def create_html(self, mode='new'):
        html_file = open('matched.html', 'w')
        size = 160, 160
        html_file.write('<html><body>')
        html_file.writelines(['<p>{} <img src="file://{}" height={} width={}>'
                              ' <img src="file://{}" height={} width={}></p>\n'.format(
                              x[0],
                              join(IPHONE_IMAGES_DIR, x[0]), size[0], size[1],
                              join(FLICKR_IMAGES_DIR, x[1]), size[0], size[1])
                              for x in self.matched if x[2] == mode or mode == 'all'][0:15])
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
    parser.add_argument('--attempts', help='Number of attempts to compare')
    args = vars(parser.parse_args())

    if args['mode'] == 'download':
        flickr = Flickr()
        flickr.download_photos(args['page'])
    elif args['mode'] == 'compare':
        comparer = Comparer()
        comparer.compare_dirs(args['attempts'])
        comparer.create_html(mode='new')
    elif args['mode'] == 'html':
        comparer = Comparer()
        comparer.create_html(mode='new')
    elif args['mode'] == 'replace':
        flickr = Flickr()
        flickr.replace_photos()
    elif args['mode'] == 'unmatched':
        comparer = Comparer()
        comparer.create_html(mode='not matched')
        comparer.compare_dirs(args['attempts'])


def photo_test():
    comparer = Comparer()
    dir = comparer.iphone_images_dir
    images = [x for x in os.listdir(dir) if '.jpg' in x.lower()]
    print images[0]
    photo1 = Photo(join(dir, images[0]))
    print photo1.exif


def compare_test():
    comparer = Comparer()
    iphone_img = 'IMG_0179.JPG'
    flickr_img = '6641846395.jpg'
    cmp = comparer.compare_photos(iphone_img=join(IPHONE_IMAGES_DIR, iphone_img),
                                  flickr_img=join(FLICKR_IMAGES_DIR, flickr_img),
                                  mode='path')
    print('Result of comparing {} and {} - {}'.format(iphone_img,
                                                      flickr_img,
                                                      'MATCHED' if cmp else 'NOT MATCHED'))


def write_squared():
    comparer = Comparer()
    comparer.squared_list()

if __name__ == '__main__':
    main()
    # photo_test()
    # write_squared()
    # compare_test()
