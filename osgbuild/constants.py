"""Global constants for osg-build"""
import dataclasses as _dataclasses
import enum as _enum
import os as _os
import re as _re
import typing as _t

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


class RestrictedTarget:
    name: str
    remotes: _t.List[str]
    koji_target_re: _re.Pattern
    svn_branch_re: _re.Pattern = None
    git_branch_re: _re.Pattern = None

    def __init__(
            self,
            name: str,
            remotes: _t.Union[str, _t.List[str]],
            koji_target_re: _t.Union[str, _re.Pattern],
            svn_branch_re: _t.Union[str, _re.Pattern] = None,
            git_branch_re: _t.Union[str, _re.Pattern] = None,
    ):
        self.name = name
        if isinstance(koji_target_re, str):
            self.koji_target_re = _re.compile(koji_target_re)
        elif isinstance(koji_target_re, _re.Pattern):
            self.koji_target_re = koji_target_re
        else:
            raise TypeError("koji_target_re has the wrong type: %s" % type(koji_target_re))

        if not svn_branch_re:
            self.svn_branch_re = None
        elif isinstance(svn_branch_re, str):
            self.svn_branch_re = _re.compile(svn_branch_re)
        elif isinstance(svn_branch_re, _re.Pattern):
            self.svn_branch_re = svn_branch_re
        else:
            raise TypeError("svn_branch_re has the wrong type: %s" % type(svn_branch_re))

        if isinstance(git_branch_re, str):
            self.git_branch_re = _re.compile(git_branch_re)
        elif isinstance(git_branch_re, _re.Pattern):
            self.git_branch_re = git_branch_re
        else:
            raise TypeError("git_branch_re has the wrong type: %s" % type(git_branch_re))

        if not remotes:
            raise ValueError("remotes must contain at least one remote")
        if isinstance(remotes, str):
            self.remotes = [remotes]
        else:
            self.remotes = remotes


# fmt: off

# Changes from original pattern: these aren't anchored; use re.fullmatch() or re.match() if you want to anchor them
# SVN branches implicitly start with 'branches/'
RESTRICTED_TARGETS = {
    "upcoming": RestrictedTarget(
        name="upcoming",
        remotes=["osg", "osg2"],
        koji_target_re  =        r'osg-(?P<osgver>[0-9.]+)-upcoming-(el\d+)',
        svn_branch_re   =            r'(?P<osgver>[0-9.]+)-upcoming',
        git_branch_re   =     r'(\w*/)?(?P<osgver>[0-9.]+)-upcoming',
    ),
    "oldinternal": RestrictedTarget(
        name="oldinternal",
        remotes=["osg", "osg2"],
        koji_target_re  =  r'osg-(el\d+)-internal',
        svn_branch_re   =          r'osg-internal',
        git_branch_re   =       r'(\w*/)?internal',
    ),
    "devops": RestrictedTarget(
        name="devops",
        remotes=["osg", "osg2"],
        koji_target_re  =          r'devops-(el\d+)',
        svn_branch_re   =          r'devops',
        git_branch_re   =   r'(\w*/)?devops',
    ),
    "versioned": RestrictedTarget(
        name="versioned",
        remotes=["osg", "osg2"],
        koji_target_re =          r'osg-(?P<osgver>\d+\.\d+)-(el\d+)',
        svn_branch_re  =          r'osg-(?P<osgver>\d+\.\d+)',
        git_branch_re  =   r'(\w*/)?osg-(?P<osgver>\d+\.\d+)',
    ),
    "newmain": RestrictedTarget(  # XXX rename to 'main' after I've gotten rid of the osg-elX targets
        name="newmain",
        remotes=["osg", "osg2"],
        koji_target_re  =        r'osg-(?P<osgver>[0-9.]+)-main-(el\d+)',
        svn_branch_re   =            r'(?P<osgver>[0-9.]+)-main',
        git_branch_re   =     r'(\w*/)?(?P<osgver>[0-9.]+)-main',
    ),
    "internal": RestrictedTarget(
        name="internal",
        remotes=["osg", "osg2"],
        koji_target_re  =        r'osg-(?P<osgver>[0-9.]+)-internal-(el\d+)',
        svn_branch_re   =            r'(?P<osgver>[0-9.]+)-internal',
        git_branch_re   =     r'(\w*/)?(?P<osgver>[0-9.]+)-internal',
    ),
    "chtc": RestrictedTarget(
        name="chtc",
        remotes=["chtc"],
        koji_target_re = r'chtc-(el\d+)',
        git_branch_re  = r'.*',
    ),
    "hcc": RestrictedTarget(
        name="hcc",
        remotes=["hcc"],
        koji_target_re = r'hcc-(el\d+)',
        git_branch_re  = r'.*',
    )
}
# fmt: on



# fmt: off
KOJI_RESTRICTED_TARGETS = {
    r'^osg-(el\d+)$'                                : 'main',
    r'^osg-(?P<osgver>[0-9.]+)-upcoming-(el\d+)$'   : 'upcoming',
    r'^devops-(el\d+)$'                             : 'devops',
    r'^osg-(el\d+)-internal$'                       : 'oldinternal',
    r'^osg-(?P<osgver>\d+\.\d+)-(el\d+)$'           : 'versioned',
    r'^osg-(?P<osgver>[0-9.]+)-main-(el\d+)$'       : 'versioned',
    r'^osg-(?P<osgver>[0-9.]+)-internal-(el\d+)$'   : 'internal',
    r'^chtc-(el\d+)$'                               : 'chtc',
}
GIT_RESTRICTED_BRANCHES = {
    r'^(\w*/)?(?P<osgver>[0-9.]+)-upcoming$'    : 'upcoming',
    r'^(\w*/)?internal$'                        : 'oldinternal',
    r'^(\w*/)?devops$'                          : 'devops',
    r'^(\w*/)?osg-(?P<osgver>\d+\.\d+)$'        : 'versioned',
    r'^(\w*/)?(?P<osgver>[0-9.]+)-main$'        : 'versioned',
    r'^(\w*/)?(?P<osgver>[0-9.]+)-internal$'    : 'internal',
}
# fmt: on


class RemoteLayout(_enum.Enum):
    LEGACY = "legacy"
    SUBTREE = "subtree"


@_dataclasses.dataclass
class GitHubRemoteType:
    name: str  # TODO This feels hacky
    repo: str
    layout: RemoteLayout

    @property
    def unauth(self):
        return f"https://github.com/{self.repo}"

    @property
    def auth(self):
        return f"git@github.com:{self.repo}"

    @property
    def urls(self):
        return [self.auth, self.unauth]

    @property
    def remote_map(self) -> _t.Dict[str, str]:
        """
        Map the authenticated URL to an anonymous checkout URL.
        """
        return {self.auth: self.unauth}


REMOTES = {
    "osg": GitHubRemoteType(
        name="osg",
        repo="opensciencegrid/Software-Redhat.git",
        layout=RemoteLayout.LEGACY,
    ),
    "hcc": GitHubRemoteType(
        name="hcc",
        repo="unlhcc/hcc-packaging.git",
        layout=RemoteLayout.LEGACY,
    ),
    "chtc": GitHubRemoteType(
        name="chtc",
        repo="CHTC/packaging.git",
        layout=RemoteLayout.LEGACY,
    ),
    "osg2": GitHubRemoteType(
        name="osg2",
        repo="osg-htc/software-packaging.git",
        layout=RemoteLayout.SUBTREE,
    ),
}


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

REPO_HINTS_STATIC = {
    'devops': {'target': 'devops-%(dver)s', 'tag': 'osg-%(dver)s'},
    'hcc': {'target': 'hcc-%(dver)s', 'tag': 'hcc-%(dver)s'},
    'chtc': {'target': 'chtc-%(dver)s', 'tag': 'chtc-%(dver)s'},
}

BUGREPORT_EMAIL = "help@osg-htc.org"

BACKGROUND_THRESHOLD = 5
