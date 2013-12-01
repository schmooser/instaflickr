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

    IMAGE_SIZE = 10, 10
    RESIZE_MODE = Image.ANTIALIAS

    def __init__(self, session, db):
        logger.debug('processing session %s', session['username'])
        self.session = session
        self.db = db

        userdir, flickrdir, btsyncdir = downloader.get_dirs(self.session)

        self.matches = [x for x in db.matches.find({'owner': self.session['username']})]

        self.flickr_imgs = os.listdir(flickrdir)

        self.btsync_imgs = [x for x in db.btsync.find({'owner': self.session['username'], 'download': 1})]
        self.btsync_imgs = filter(lambda x: x['name'] in os.listdir(btsyncdir), self.btsync_imgs)

        #logger.debug('flickr_imgs: %s', self.flickr_imgs)
        #logger.debug('btsync_imgs: %s', [x['name'] for x in self.btsync_imgs])
        logger.info('have %d flickr_imgs', len(self.flickr_imgs))
        logger.info('have %d btsync_imgs', len(self.btsync_imgs))

        self.flickr_imgs = filter(lambda x: x[1] is not False,
                                  [(x, self.open(os.path.join(flickrdir, x)))
                                   for x in sorted(self.flickr_imgs, reverse=True)
                                   if x not in [y['flickr'] for y in self.matches]])

        self.btsync_imgs = filter(lambda x: x[1] is not False,
                                  [(x, self.open(os.path.join(btsyncdir, x['name'])))
                                   for x in sorted(self.btsync_imgs, reverse=True)
                                   if x not in [y['btsync'] for y in self.matches]])

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

    @staticmethod
    def compare_photos(im1, im2, mode='image'):
        if mode == 'image':
            return Comparer._img_diff(im1, im2) == 100
        elif mode == 'path':
            im1 = Image.open(im1)
            im1 = im1.resize(Comparer.IMAGE_SIZE, Comparer.RESIZE_MODE)
            im2 = Image.open(im2)
            im2 = im2.resize(Comparer.IMAGE_SIZE, Comparer.RESIZE_MODE)
            return Comparer._img_diff(im1, im2) == 100
        else:
            return False

    @staticmethod
    def open(image):
        logger.debug('Loading %s', image)
        img = Image.open(image)
        if img.size[0] == img.size[1]:
            return img.resize(Comparer.IMAGE_SIZE, Comparer.RESIZE_MODE)
        else:
            return False

    def compare(self, attempts=250):
        """Compares dirs file by file"""
        logger.debug('start')

        logger.info('comparing %d btsync images with %d flickr images', len(self.btsync_imgs), len(self.flickr_imgs))

        matches = []
        not_matched = []
        for btsync_img in self.btsync_imgs:
            i = 0
            matched = False
            for flickr_img in self.flickr_imgs:
                i += 1
                if self.compare_photos(btsync_img[1], flickr_img[1], 'image'):
                    logger.info('%s matched to %s in %d attempts', flickr_img[0], btsync_img[0]['name'], i)
                    matches.append(dict(btsync=btsync_img[0]['name'], flickr=flickr_img[0],
                                        owner=self.session['username']))
                    self.flickr_imgs.remove(flickr_img)
                    matched = True
                    break
                if i >= attempts:
                    logger.info('%s not matched in %d attempts', btsync_img[0]['name'], i)
                    break
            if not matched:
                logger.info('%s not matched in %d attempts', btsync_img[0]['name'], i)
                not_matched.append(btsync_img[0])

        logger.info('found %d matches', len(matches))

        for btsync_img in not_matched:
            self.db.btsync.save(dict(btsync_img, download=5))

        if matches:
            self.matches += matches
            self.db.insert(matches)


def main():
    downloader.logger_setup(logger)
    db = downloader.db
    sessions = db.sessions.find()
    for session in sessions:
        if 'status' in session and session['status'] & 1 << 3 == 1 << 3:
            c = Comparer(session, db)
            c.compare()


if __name__ == '__main__':
    main()


