#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Purpose: analyze photos to match

Steps:
  1. Get photos from Flickr
  2. Get photos from BTSync
  3. Upload matched photos to Flickr

Photo statuses:
    { "code" : 0, "name" : "Not analyzed" }
    { "code" : 1, "name" : "Matched" }                 1 << 0
    { "code" : 2, "name" : "Matched and replaced" }    1 << 1

"""

import os
import math
import operator
import logging
from PIL import Image
from PIL import ImageChops

import downloader

LOGLEVEL = logging.DEBUG
logger = logging.getLogger(__name__)
logger.setLevel(LOGLEVEL)


class Comparer:
    """Compare photos"""

    COMPARER_IMAGE_SIZE = 10, 10

    def __init__(self, session, db):
        self.session = session
        self.db = db

        userdir, flickrdir, btsyncdir = downloader.get_dirs(self.session)

        self.matches = []
        cursor = db.matches.find({'owner': self.session['username']})
        for img in cursor:
            self.matches.append(img)

        self.flickr_imgs = os.listdir(self.dirs[1])

        self.btsync_imgs = []
        cursor = db.btsync.find({'owner': self.session['username'], 'download': 1})
        for img in cursor:
            self.btsync_imgs.append(img['name'])

        self.flickr_imgs = [(x, self.open(os.join(flickrdir, x), self.COMPARER_IMAGE_SIZE))
                            for x in sorted(self.flickr_imgs, key=lambda x: x['name'], reverse=True)
                            if x['name'] not in [y['flickr'] for y in self.matches]]

        self.btsync_imgs = [(x['name'], self.open(os.join(btsyncdir, x['name']), self.COMPARER_IMAGE_SIZE))
                            for x in sorted(self.btsync_imgs, key=lambda x: x['name'], reverse=True)
                            if x['name'] not in [y['btsync'] for y in self.matches]]

    @staticmethod
    def _img_diff(im1, im2):
        diff = ImageChops.difference(im1, im2).convert('1')
        h1 = diff.histogram()
        return h1[0]

    @staticmethod
    def _rms(im1, im2):
        h1 = im1.histogram()
        h2 = im2.histogram()
        rms = math.sqrt(reduce(operator.add, map(lambda a, b: (a-b)**2, h1, h2))/len(h1))
        # print im1, im2, rms
        return rms

    def compare_photos(self, im1, im2, mode='image'):
        if mode == 'image':
            return self._img_diff(im1, im2) == 100
        elif mode == 'path':
            resize_mode = Image.ANTIALIAS
            im1 = Image.open(im1)
            im1 = im1.resize(self.COMPARER_IMAGE_SIZE, resize_mode)
            im2 = Image.open(im2)
            im2 = im2.resize(self.COMPARER_IMAGE_SIZE, resize_mode)
            return self._img_diff(im1, im2) == 100
        else:
            return False

    @staticmethod
    def open(image, size):
        resize_mode = Image.ANTIALIAS
        logger.debug('Loading {}'.format(image))
        return Image.open(image).resize(size, resize_mode)

    def compare(self, attempts=50):
        """Compares dirs file by file"""
        logger.debug('start')

        logger.info('Comparing {} iPhone images with {} Flickr images'.format(len(self.iphone_imgs), len(self.flickr_imgs)))

        matches = []
        for flickr_img in self.flickr_imgs:
            i = 0
            for btsync_img in self.btsync_imgs:
                i += 1
                if self.compare_photos(btsync_img[1], flickr_img[1], 'image'):
                    logger.info('{i1} matched to {i2} in {n} attempts'.format(i1=flickr_img[0], i2=btsync_img[0], n=i))
                    matches.append(dict(btsync=btsync_img[0], flickr=flickr_img[0], owner=self.session['username']))
                    self.btsync_imgs.remove(btsync_img)
                    break
                if i > attempts:
                    # file_matched.write('---\t{}\tnot matched\n'.format(flickr_img[0]))
                    logger.info('{} not matched in {} attempts'.format(flickr_img[0], i))
                    break

        if matches:
            self.matches += matches
            self.db.insert(matches)


def main():
    downloader.logger_setup()
    db = downloader.db
    sessions = db.sessions.find()
    #sessions = db.sessions.find({'username': 'schmooser'})
    for session in sessions:
        if 'status' in session and session['status'] & 1 << 3 == 1 << 3:
            c = Comparer(session, db)
            c.compare()


if __name__ == '__main__':
    main()


