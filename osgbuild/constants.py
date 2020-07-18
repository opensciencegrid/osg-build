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

KOJI_USER_CONFIG_DIR = os.path.expanduser("~/.koji")
OSG_KOJI_USER_CONFIG_DIR = os.path.expanduser("~/.osg-koji")
KOJI_CLIENT_CERT = os.path.join(OSG_KOJI_USER_CONFIG_DIR, "client.crt")

KOJI_CONF = "osg-koji-site.conf"
OLD_KOJI_CONF = "osg-koji.conf"
DATA_DIR = "/usr/share/osg-build"

KOJI_HUB = "http://koji.opensciencegrid.org"
KOJI_WEB = "https://koji.opensciencegrid.org"

DATA_FILE_SEARCH_PATH = [os.path.abspath(os.path.dirname(__file__) + "/../data")]
if "OSG_LOCATION" in os.environ:
    DATA_FILE_SEARCH_PATH.append(os.environ["OSG_LOCATION"] + DATA_DIR)
DATA_FILE_SEARCH_PATH.append(DATA_DIR)

SVN_ROOT = "https://vdt.cs.wisc.edu/svn"
SVN_REDHAT_PATH = "/native/redhat"

SVN_RESTRICTED_BRANCHES = {
    r'^trunk$'                             : 'main',
    r'^branches/upcoming$'                 : 'upcoming',
    r'^branches/osg-internal$'             : 'internal',
    r'^branches/devops$'                   : 'devops',
    r'^branches/osg-(?P<osgver>\d+\.\d+)$' : 'versioned',
    r'^branches/condor'                    : 'condor'}
KOJI_RESTRICTED_TARGETS = {
    r'^osg-(el\d+)$'                       : 'main',
    r'^osg-upcoming-(el\d+)$'              : 'upcoming',
    r'^devops-(el\d+)$'                    : 'devops',
    r'^osg-(el\d+)-internal$'              : 'internal',
    r'^osg-(?P<osgver>\d+\.\d+)-(el\d+)$'  : 'versioned',
    r'^condor-(el\d+)$'                    : 'condor'}
GIT_RESTRICTED_BRANCHES = {
    r'^(\w*/)?master$'                     : 'main',
    r'^(\w*/)?upcoming$'                   : 'upcoming',
    r'^(\w*/)?internal$'                   : 'internal',
    r'^(\w*/)?devops$'                     : 'devops',
    r'^(\w*/)?osg-(?P<osgver>\d+\.\d+)$'   : 'versioned',
    r'^(\w*/)?condor-(el\d+)'              : 'condor'}

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

DVERS = ['el6', 'el7', 'el8', 'fc32']

DEFAULT_BUILDOPTS_BY_DVER = {}
for dver in DVERS:
    DEFAULT_BUILDOPTS_BY_DVER[dver] = dict(
        distro_tag='osg.'+dver,
        koji_tag=None,
        koji_target=None,
        redhat_release=dver[2:]
    )

# If the dver on the current machine can't be detected for some reason, or
# isn't EL, use this.
FALLBACK_DVER = 'el7'
DEFAULT_DVERS = ['el7']
DEFAULT_DVERS_BY_REPO = {
    '3.3': ['el6', 'el7'],
    'osg-3.3': ['el6', 'el7'],
    '3.4': ['el6', 'el7'],
    'osg-3.4': ['el6', 'el7'],
    '3.5': ['el7'],
    'osg-3.5': ['el7'],
    'internal': ['el6', 'el7'],
    'condor': ['el6', 'el7'],
    'devops': ['el7'],
    'upcoming': ['el7'],
}
assert FALLBACK_DVER in DVERS
for d in DEFAULT_DVERS:
    assert d in DVERS
for ds in DEFAULT_DVERS_BY_REPO.values():
    for d in ds:
        assert d in DVERS

REPO_HINTS_STATIC = {
    'osg': {'target': 'osg-%(dver)s', 'tag': 'osg-%(dver)s'},
    'upcoming': {'target': 'osg-upcoming-%(dver)s', 'tag': 'osg-%(dver)s'},
    'internal': {'target': 'osg-%(dver)s-internal', 'tag': 'osg-%(dver)s'},
    'devops': {'target': 'devops-%(dver)s', 'tag': 'osg-%(dver)s'},
    'hcc': {'target': 'hcc-%(dver)s', 'tag': 'hcc-%(dver)s'},
    'condor': {'target': 'condor-%(dver)s', 'tag': 'condor-%(dver)s'},
}

BUGREPORT_EMAIL = "osg-software@opensciencegrid.org"

BACKGROUND_THRESHOLD = 5

