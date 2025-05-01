import dataclasses
import enum
import re
import typing as t


class RestrictedTarget:
    name: str
    remotes: t.List[str]
    koji_target_re: re.Pattern
    svn_branch_re: t.Optional[re.Pattern] = None
    git_branch_re: re.Pattern = None

    def __init__(
            self,
            name: str,
            remotes: t.Union[str, t.List[str]],
            koji_target_re: t.Union[str, re.Pattern],
            svn_branch_re: t.Union[str, re.Pattern] = None,
            git_branch_re: t.Union[str, re.Pattern] = None,
    ):
        self.name = name
        if isinstance(koji_target_re, str):
            self.koji_target_re = re.compile(koji_target_re)
        elif isinstance(koji_target_re, re.Pattern):
            self.koji_target_re = koji_target_re
        else:
            raise TypeError("koji_target_re has the wrong type: %s" % type(koji_target_re))

        if not svn_branch_re:
            self.svn_branch_re = None
        elif isinstance(svn_branch_re, str):
            self.svn_branch_re = re.compile(svn_branch_re)
        elif isinstance(svn_branch_re, re.Pattern):
            self.svn_branch_re = svn_branch_re
        else:
            raise TypeError("svn_branch_re has the wrong type: %s" % type(svn_branch_re))

        if isinstance(git_branch_re, str):
            self.git_branch_re = re.compile(git_branch_re)
        elif isinstance(git_branch_re, re.Pattern):
            self.git_branch_re = git_branch_re
        else:
            raise TypeError("git_branch_re has the wrong type: %s" % type(git_branch_re))

        if not remotes:
            raise ValueError("remotes must contain at least one remote")
        if isinstance(remotes, str):
            self.remotes = [remotes]
        else:
            self.remotes = remotes



# Changes from original pattern: these aren't anchored; use re.fullmatch() or re.match() if you want to anchor them
# SVN branches implicitly start with 'branches/'

# fmt: off
# KOJI_RESTRICTED_TARGETS = {
#     r'^osg-(el\d+)$'                                : 'main',
#     r'^osg-(?P<osgver>[0-9.]+)-upcoming-(el\d+)$'   : 'upcoming',
#     r'^devops-(el\d+)$'                             : 'devops',
#     r'^osg-(el\d+)-internal$'                       : 'oldinternal',
#     r'^osg-(?P<osgver>\d+\.\d+)-(el\d+)$'           : 'versioned',
#     r'^osg-(?P<osgver>[0-9.]+)-main-(el\d+)$'       : 'versioned',
#     r'^osg-(?P<osgver>[0-9.]+)-internal-(el\d+)$'   : 'internal',
#     r'^chtc-(el\d+)$'                               : 'chtc',
# }
# GIT_RESTRICTED_BRANCHES = {
#     r'^(\w*/)?(?P<osgver>[0-9.]+)-upcoming$'    : 'upcoming',
#     r'^(\w*/)?internal$'                        : 'oldinternal',
#     r'^(\w*/)?devops$'                          : 'devops',
#     r'^(\w*/)?osg-(?P<osgver>\d+\.\d+)$'        : 'versioned',
#     r'^(\w*/)?(?P<osgver>[0-9.]+)-main$'        : 'versioned',
#     r'^(\w*/)?(?P<osgver>[0-9.]+)-internal$'    : 'internal',
# }

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

class RemoteLayout(enum.Enum):
    LEGACY = "legacy"
    SUBTREE = "subtree"


@dataclasses.dataclass
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
    def remote_map(self) -> t.Dict[str, str]:
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
REPO_HINTS_STATIC = {
    'devops': {'target': 'devops-%(dver)s', 'tag': 'osg-%(dver)s'},
    'hcc': {'target': 'hcc-%(dver)s', 'tag': 'hcc-%(dver)s'},
    'chtc': {'target': 'chtc-%(dver)s', 'tag': 'chtc-%(dver)s'},
}
