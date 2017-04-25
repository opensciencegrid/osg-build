"""Global constants for osg-build"""
import os
import sys

WD_RESULTS = '_build_results'
WD_PREBUILD = '_final_srpm_contents'
WD_UNPACKED = '_upstream_srpm_contents'
WD_UNPACKED_TARBALL = '_upstream_tarball_contents'
WD_QUILT = '_quilt'
AFS_CACHE_PATH = '/p/vdt/public/html/upstream'
AFS_CACHE_PREFIX = 'file://' + AFS_CACHE_PATH
WEB_CACHE_PREFIX = 'http://vdt.cs.wisc.edu/upstream'
DEFAULT_CONFIG_FILE = os.path.expanduser("~/.osg-build.ini")
ALT_DEFAULT_CONFIG_FILE = os.path.expanduser("~/.vdt-build.ini")

KOJI_USER_CONFIG_DIR = os.path.expanduser("~/.koji")
OSG_KOJI_USER_CONFIG_DIR = os.path.expanduser("~/.osg-koji")
KOJI_CLIENT_CERT = os.path.join(KOJI_USER_CONFIG_DIR, "client.crt")

KOJI_CONF = "osg-koji-site.conf"
OLD_KOJI_CONF = "osg-koji.conf"
DATA_DIR = "/usr/share/osg-build"

KOJI_HUB = "http://koji.chtc.wisc.edu"
KOJI_WEB = "https://koji.chtc.wisc.edu"

DATA_FILE_SEARCH_PATH = [sys.path[0],
                         os.path.join(sys.path[0], "data"),
                         DATA_DIR]

SVN_ROOT = "https://vdt.cs.wisc.edu/svn"
SVN_REDHAT_PATH = "/native/redhat"

SVN_RESTRICTED_BRANCHES = {
    r'^trunk$'                             : 'main',
    r'^branches/upcoming$'                 : 'upcoming',
    r'^branches/osg-internal$'             : 'internal',
    r'^branches/osg-(?P<osgver>\d+\.\d+)$' : 'versioned'}
KOJI_RESTRICTED_TARGETS = {
    r'^osg-(el\d+)$'                       : 'main',
    r'^osg-upcoming-(el\d+)$'              : 'upcoming',
    r'^osg-(el\d+)-internal$'              : 'internal',
    r'^osg-(?P<osgver>\d+\.\d+)-(el\d+)$'  : 'versioned'}
GIT_RESTRICTED_BRANCHES = {
    r'^(\w*/)?master$'                     : 'main',
    r'^(\w*/)?upcoming$'                   : 'upcoming',
    r'^(\w*/)?internal$'                   : 'internal',
    r'^(\w*/)?osg-(?P<osgver>\d+\.\d+)$'   : 'versioned'}

CSL_KOJI_DIR = "/p/vdt/workspace/koji-1.11.0"

OSG_REMOTE = 'https://github.com/opensciencegrid/Software-Redhat.git'
HCC_REMOTE = 'https://github.com/unlhcc/hcc-packaging.git'
HCC_AUTH_REMOTE = 'git@github.com:unlhcc/hcc-packaging.git'

KNOWN_GIT_REMOTES = [HCC_REMOTE,
                     HCC_AUTH_REMOTE,
                     OSG_REMOTE]
# Map the authenticated URL to an anonymous checkout URL.
GIT_REMOTE_MAPS = {HCC_AUTH_REMOTE: HCC_REMOTE}

DEFAULT_BUILDOPTS_COMMON = {
    'autoclean': True,
    'background': False,
    'cache_prefix': 'AUTO',
    'dry_run': False,
    'full_extract': False,
    'getfiles': False,
    'koji_backend': None,
    'kojilogin': None,
    'koji_wrapper': True,
    'mock_clean': True,
    'mock_config': None,
    'mock_config_from_koji': None,
    'no_wait': False,
    'regen_repos': False,
    'repo': 'osg',
    'scratch': False,
    'vcs': None,
    'target_arch': None,
    'working_directory': '.',
}

DEFAULT_BUILDOPTS_BY_DVER = {
    'el5': {
        'distro_tag': 'osg.el5',
        'koji_tag': None,
        'koji_target': None,
        'redhat_release': '5',
    },
    'el6': {
        'distro_tag': 'osg.el6',
        'koji_tag': None,
        'koji_target': None,
        'redhat_release': '6',
    },
    'el7': {
        'distro_tag': 'osg.el7',
        'koji_tag': None,
        'koji_target': None,
        'redhat_release': '7',
    }
}
# If the dver on the current machine can't be detected for some reason, or
# isn't EL, use this.
FALLBACK_DVER = 'el7'

REPO_HINTS_STATIC = {
    'osg': {'target': 'osg-%(dver)s', 'tag': 'osg-%(dver)s'},
    'upcoming': {'target': 'osg-upcoming-%(dver)s', 'tag': 'osg-%(dver)s'},
    'internal': {'target': 'osg-%(dver)s-internal', 'tag': 'osg-%(dver)s'},
    'hcc': {'target': 'hcc-%(dver)s', 'tag': 'hcc-%(dver)s'},
    'uscms': {'target': 'uscms-%(dver)s', 'tag': 'uscms-%(dver)s'},
    'condor': {'target': 'condor-%(dver)s', 'tag': 'condor-%(dver)s'},
    'perfsonar': {'target': 'perfsonar-%(dver)s', 'tag': 'perfsonar-%(dver)s'},
}

DEFAULT_DVERS = ['el6', 'el7']
DEFAULT_DVERS_BY_REPO = {
    '3.2': ['el5', 'el6'],
    'osg-3.2': ['el5', 'el6'],
    '3.3': ['el6', 'el7'],
    'osg-3.3': ['el6', 'el7'],
    'internal': ['el5', 'el6', 'el7'],
}
DVERS = DEFAULT_BUILDOPTS_BY_DVER.keys()

BUGREPORT_EMAIL = "osg-software@opensciencegrid.org"

BACKGROUND_THRESHOLD = 5

