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
WEB_CACHE_PREFIX = 'https://vdt.cs.wisc.edu/upstream'

KOJI_USER_CONFIG_DIR = os.path.expanduser("~/.koji")
OSG_KOJI_USER_CONFIG_DIR = os.path.expanduser("~/.osg-koji")
KOJI_CLIENT_CERT = os.path.join(OSG_KOJI_USER_CONFIG_DIR, "client.crt")

KOJI_CONF = "osg-koji-site.conf"
OLD_KOJI_CONF = "osg-koji.conf"
DATA_DIR = "/usr/share/osg-build"

KOJI_HUB = "https://koji.opensciencegrid.org"
KOJI_WEB = "https://koji.opensciencegrid.org"

DATA_FILE_SEARCH_PATH = [os.path.abspath(os.path.dirname(__file__) + "/../data")]
if "OSG_LOCATION" in os.environ:
    DATA_FILE_SEARCH_PATH.append(os.environ["OSG_LOCATION"] + DATA_DIR)
DATA_FILE_SEARCH_PATH.append(DATA_DIR)

SVN_ROOT = "https://vdt.cs.wisc.edu/svn"
SVN_REDHAT_PATH = "/native/redhat"

SVN_RESTRICTED_BRANCHES = {
    r'^branches/(?P<osgver>[0-9.]+)-upcoming$': 'upcoming',
    r'^branches/osg-internal$'             : 'oldinternal',
    r'^branches/devops$'                   : 'devops',
    r'^branches/osg-(?P<osgver>\d+\.\d+)$' : 'versioned',
    r'^branches/(?P<osgver>[0-9.]+)-main$' : 'versioned',
    r'^branches/(?P<osgver>[0-9.]+)-internal$' : 'internal',
}
KOJI_RESTRICTED_TARGETS = {
    r'^osg-(el\d+)$'                       : 'main',
    r'^osg-(?P<osgver>[0-9.]+)-upcoming-(el\d+)$': 'upcoming',
    r'^devops-(el\d+)$'                    : 'devops',
    r'^osg-(el\d+)-internal$'              : 'oldinternal',
    r'^osg-(?P<osgver>\d+\.\d+)-(el\d+)$'  : 'versioned',
    r'^(?P<osgver>[0-9.]+)-main-(el\d+)$'  : 'versioned',
    r'^(?P<osgver>[0-9.]+)-internal-(el\d+)$' : 'internal',
}
GIT_RESTRICTED_BRANCHES = {
    r'^(\w*/)?(?P<osgver>[0-9.]+)-upcoming$': 'upcoming',
    r'^(\w*/)?internal$'                   : 'oldinternal',
    r'^(\w*/)?devops$'                     : 'devops',
    r'^(\w*/)?osg-(?P<osgver>\d+\.\d+)$'   : 'versioned',
    r'^(\w*/)?(?P<osgver>[0-9.]+)-main$'   : 'versioned',
    r'^(\w*/)?(?P<osgver>[0-9.]+)-internal$' : 'internal',
}

CSL_KOJI_DIR = "/p/vdt/workspace/koji-1.15.3"

OSG_REMOTE = 'https://github.com/opensciencegrid/Software-Redhat.git'
OSG_AUTH_REMOTE = 'git@github.com:opensciencegrid/Software-Redhat.git'
HCC_REMOTE = 'https://github.com/unlhcc/hcc-packaging.git'
HCC_AUTH_REMOTE = 'git@github.com:unlhcc/hcc-packaging.git'

KNOWN_GIT_REMOTES = [HCC_REMOTE,
                     HCC_AUTH_REMOTE,
                     OSG_REMOTE,
                     OSG_AUTH_REMOTE]
# Map the authenticated URL to an anonymous checkout URL.
GIT_REMOTE_MAPS = {HCC_AUTH_REMOTE: HCC_REMOTE,
                   OSG_AUTH_REMOTE: OSG_REMOTE}

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

DVERS = ['el7', 'el8', 'el9']

DEFAULT_BUILDOPTS_BY_DVER = {}
for dver in DVERS:
    DEFAULT_BUILDOPTS_BY_DVER[dver] = dict(
        distro_tag='osg.'+dver,
        koji_tag=None,
        koji_target=None,
        redhat_release=dver[2:]
    )
DEFAULT_BUILDOPTS_BY_DVER['el7']['_binary_payload'] = 'w2.xzdio'

# If the dver on the current machine can't be detected for some reason, or
# isn't EL, use this.
FALLBACK_DVER = 'el7'
DEFAULT_DVERS = ['el7', 'el8', 'el9']
DEFAULT_DVERS_BY_REPO = {
    '3.5': ['el7', 'el8'],
    'osg-3.5': ['el7', 'el8'],
    '3.5-upcoming': ['el7', 'el8'],
    '3.6': ['el7', 'el8', 'el9'],
    'osg-3.6': ['el7', 'el8', 'el9'],
    '3.6-upcoming': ['el7', 'el8', 'el9'],
    '23-main': ['el8', 'el9'],
    '23-upcoming': ['el8', 'el9'],
    '23-internal': ['el8', 'el9'],
    'internal': ['el7'],
    'devops': ['el7', 'el8'],
}
assert FALLBACK_DVER in DVERS
for d in DEFAULT_DVERS:
    assert d in DVERS
for ds in DEFAULT_DVERS_BY_REPO.values():
    for d in ds:
        assert d in DVERS

REPO_HINTS_STATIC = {
    'osg': {'target': 'osg-%(dver)s', 'tag': 'osg-%(dver)s'},
    'internal': {'target': 'osg-%(dver)s-internal', 'tag': 'osg-%(dver)s'},
    'devops': {'target': 'devops-%(dver)s', 'tag': 'osg-%(dver)s'},
    'hcc': {'target': 'hcc-%(dver)s', 'tag': 'hcc-%(dver)s'},
}

BUGREPORT_EMAIL = "help@osg-htc.org"

BACKGROUND_THRESHOLD = 5

