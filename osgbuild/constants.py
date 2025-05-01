"""Global constants for osg-build"""
import os as _os

WD_RESULTS = '_build_results'
WD_PREBUILD = '_final_srpm_contents'
WD_UNPACKED = '_upstream_srpm_contents'
WD_UNPACKED_TARBALL = '_upstream_tarball_contents'
WD_QUILT = '_quilt'
BACKUP_WEB_CACHE_PREFIX = 'https://vdt.cs.wisc.edu/upstream'
WEB_CACHE_PREFIX = 'https://sw-upstream.svc.osg-htc.org/upstream'

KOJI_USER_CONFIG_DIR = _os.path.expanduser("~/.koji")
OSG_KOJI_USER_CONFIG_DIR = _os.path.expanduser("~/.osg-koji")
KOJI_CLIENT_CERT = _os.path.join(OSG_KOJI_USER_CONFIG_DIR, "client.crt")

DATA_DIR = "/usr/share/osg-build"
PROMOTER_INI = 'promoter.ini'
SIGNING_KEYS_INI = 'signing_keys.ini'
DEFAULT_AUTHTYPE = "kerberos"

KOJI_HUB = "https://koji.osg-htc.org"
KOJI_WEB = "https://koji.osg-htc.org"

DATA_FILE_SEARCH_PATH = [_os.path.abspath(_os.path.dirname(__file__) + "/../data")]
if "OSG_LOCATION" in _os.environ:
    DATA_FILE_SEARCH_PATH.append(_os.environ["OSG_LOCATION"] + DATA_DIR)
DATA_FILE_SEARCH_PATH.append(DATA_DIR)
try:
    try:
        # noinspection PyPackageRequirements
        import importlib_resources as _importlib_resources
    except ImportError:
        import importlib.resources as _importlib_resources
    DATA_FILE_SEARCH_PATH.append(str(_importlib_resources.files("osgbuild.data")))
except (ImportError, AttributeError):
    pass


DEFAULT_BUILDOPTS_COMMON = {
    'background': False,
    'cache_prefix': None,
    'dry_run': False,
    'full_extract': False,
    'getfiles': False,
    'koji_backend': None,
    'mock_clean': True,
    'mock_config': None,
    'mock_config_from_koji': None,
    'no_wait': False,
    'regen_repos': False,
    'repo': None,
    'scratch': False,
    'target_arch': None,
    'working_directory': '.',
}

DVERS = ['el7', 'el8', 'el9']

DEFAULT_BUILDOPTS_BY_DVER = {}
for _dver in DVERS:
    DEFAULT_BUILDOPTS_BY_DVER[_dver] = dict(
        distro_tag='osg.'+_dver,
        koji_tag=None,
        koji_target=None,
        redhat_release=_dver[2:]
    )
DEFAULT_BUILDOPTS_BY_DVER['el7']['_binary_payload'] = 'w2.xzdio'

# If the dver on the current machine can't be detected for some reason, or
# isn't EL, use this.
FALLBACK_DVER = 'el9'
DEFAULT_DVERS = ['el8', 'el9']
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
    '24-main': ['el8', 'el9'],
    '24-upcoming': ['el8', 'el9'],
    '24-internal': ['el8', 'el9'],
    'devops': ['el7', 'el8', 'el9'],
    'chtc': ['el9'],
}
assert FALLBACK_DVER in DVERS
for _d in DEFAULT_DVERS:
    assert _d in DVERS
for _ds in DEFAULT_DVERS_BY_REPO.values():
    for _d in _ds:
        assert _d in DVERS

BUGREPORT_EMAIL = "help@osg-htc.org"

BACKGROUND_THRESHOLD = 5
