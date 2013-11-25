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



