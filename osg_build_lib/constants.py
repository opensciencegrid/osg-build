#!/usr/bin/python
"""Global constants for osg-build"""
import os
import sys

WD_RESULTS = '_build_results'
WD_PREBUILD = '_final_srpm_contents'
WD_UNPACKED = '_upstream_srpm_contents'
WD_UNPACKED_TARBALL = '_upstream_tarball_contents'
AFS_CACHE_PATH = '/p/vdt/public/html/upstream'
AFS_CACHE_PREFIX = 'file://' + AFS_CACHE_PATH
WEB_CACHE_PREFIX = 'http://vdt.cs.wisc.edu/upstream'
DEFAULT_CONFIG_FILE = os.path.expanduser("~/.osg-build.ini")
ALT_DEFAULT_CONFIG_FILE = os.path.expanduser("~/.vdt-build.ini")
DEFAULT_KOJI_TAG = "el5-osg"
DEFAULT_KOJI_TARGET = "el5-osg"

KOJI_USER_CONFIG_DIR = os.path.expanduser("~/.koji")
OSG_KOJI_USER_CONFIG_DIR = os.path.expanduser("~/.osg-koji")
KOJI_CLIENT_CERT = os.path.join(KOJI_USER_CONFIG_DIR, "client.crt") # TODO needs to be synced with osg-koji-site.conf

KOJI_CONF = "osg-koji-site.conf"
OLD_KOJI_CONF = "osg-koji.conf"
DATA_DIR = "/usr/share/osg-build"

KOJI_HUB = "http://koji-hub.batlab.org"

DATA_FILE_SEARCH_PATH = [sys.path[0], DATA_DIR]

SVN_ROOT = "https://vdt.cs.wisc.edu/svn"
SVN_AFS_ROOT = "file:///p/vdt/workspace/svn"

