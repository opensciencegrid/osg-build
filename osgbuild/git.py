"""Helper functions for a git build."""
import logging
import pathlib
import re
import os
import errno
from urllib.parse import urlsplit

from .error import Error, UsageError, VCSError
from .target_protection import RESTRICTED_TARGETS, RemoteLayout, REMOTES
from . import utils
from . import kojiinter


_log = logging.getLogger(__name__)

REMOTES_BY_URL = {}
for k, v in REMOTES.items():
    for url in v.urls:
        REMOTES_BY_URL[url] = v

# Map the authenticated URL to an anonymous checkout URL.
GIT_REMOTE_MAPS = {
    # flatten list of dicts
    k: v for r in REMOTES.values() for k, v in r.remote_map.items()
}


def git_cmd(run_dir, *args):
    # type: (str, *str) -> list
    """A list of params for doing a git command in a specific repo directory"""
    return ["git", "-C", run_dir] + list(args)


def run_git_cmd(run_dir, *args):
    # type: (str, *str) -> tuple[str, int]
    """Run a git command and return its stdout+stderr, and exit code"""
    command = git_cmd(run_dir, *args)
    return utils.sbacktick(command, err2out=True)


def is_git_new_enough():
    """Returns True if the version of git is at least the minimum required (2.0), False otherwise"""
    command = ["git", "--version"]
    try:
        out = utils.backtick(command)
    except OSError as ose:
        _log.warning("Error getting git version; git unavailable: %s" % ose)
        return False
    mm = re.search(r"git version (\d+)\.(\d+)", out)
    if not mm:
        _log.warning("Error getting git version; could not parse version string")
        return False
    if int(mm.group(1)) >= 2:
        return True
    _log.warning("Git version 2 is required, but only %s.%s is installed" % (mm.group(1), mm.group(2)))
    return False


def is_git(package_dir):
    """Determine whether a given directory is part of a git repo."""
    # If package_dir is a URL, not a directory, then we can't cd into it to
    # check. Assume False unless it's a git or git+https URL or similar
    if utils.is_url(package_dir):
        scheme, _ = package_dir.split(":", 1)
        if "git" in scheme:
            return True
        return False
    pwd = os.getcwd()
    try:
        try:
            os.chdir(package_dir)
        except OSError as ose:
            if ose.errno == errno.ENOENT:
                raise Error("%s is not a valid package directory\n(%s)" % (package_dir, ose))
        command = ["git", "status", "--porcelain"]
        try:
            err = utils.sbacktick(command, err2out=True)[1]
        except OSError as ose:
            if ose.errno != errno.ENOENT:
                raise
            err = 1
        if err:
            return False
    finally:
        os.chdir(pwd)
    return True


def _normalize_remote(remote_url):
    """Normalize the URL of the given Git repo which means:

    - add the ".git" at the end if necessary
    - correct the capitalization of Software-Redhat
    """
    if not remote_url.endswith(".git"):
        remote_url = remote_url + ".git"
    remote_url = re.sub(r"software-redhat", "Software-Redhat", remote_url, flags=re.IGNORECASE)
    return remote_url


def parse_git_url(git_url):
    """Parse a git URL of the type recognized by Koji, which looks like
    `git+REPO?DIRECTORY#BRANCH`
    where REPO is a remote URL like "https://github.com/opensciencegrid/Software-Redhat.git"
    DIRECTORY is a directory like "osg-xrootd"
    BRANCH is a git branch like "osg-3.6"

    Return (REMOTE, DIRECTORY, BRANCH) or (None, None, None) if parsing failed.
    """
    scheme, netloc, path, query, fragment = urlsplit(git_url)
    try:
        if not (scheme and netloc and path and query):
            return None, None, None
        scheme = scheme.rsplit("+")[-1]  # git+https -> https
        path = _normalize_remote(path)
        repo = "{scheme}://{netloc}{path}".format(**locals())
        directory = query
        branch = fragment or "HEAD"
        return repo, directory, branch
    except TypeError:
        return None, None, None


#
# Branch checking
#
# We need to forbid building from certain git branches into certain Koji
# targets. This is implemented by having two dicts mapping regexp patterns to
# names, one containing the restricted git branches and one containing the
# restricted Koji targets.
#
# We're permissive by default: if neither the branch nor the target match any
# of the regexps in their respective dicts, the build is allowed. On the other
# hand, if both are restricted then the branch name has to match the target
# name.
#


def get_git_branch(package_dir):
    # type: (str) -> str
    """Return the current git branch for a given directory."""
    out, err = run_git_cmd(package_dir, "branch")
    if err:
        raise VCSError("Exit code %d getting git branch for directory %s.  Output:\n%s" % (err, package_dir, out))
    out = out.strip()
    if not out:
        raise VCSError("'git branch' returned no output.")

    branch = [ line[2:] for line in out.splitlines() if line.startswith('* ') ]
    if len(branch) != 1 or not branch[0] or ' ' in branch[0]:
        raise VCSError("'git branch' indicates no branch is checked out")
    return branch[0]


def get_subtree_branch(package_dir):
    """
    Return the branch for the given package directory in a remote using the
    'subtree' layout.

    Args:
        package_dir: the package directory to get the branch for

    Returns: the branch name
    """
    # The "subtree" layout requires that the package directory be a subdirectory
    # of the branch.
    try:
        return pathlib.Path(package_dir).absolute().parts[-2]
    except IndexError:
        raise VCSError("Unable to determine the branch for the package directory %s" % package_dir)


def get_known_remote(package_dir):
    """Return the first remote in the current directory's list of urls which
       is on osg-build's configured whitelist of urls,
       as a (name, normalized url) tuple.
       """
    out, err = run_git_cmd(package_dir, "remote", "-v")
    if err:
        raise VCSError("Exit code %d getting git status for directory %s. Output:\n%s" % (err, package_dir, out))
    for line in out.splitlines():
        info = line.strip().split()
        if len(info) != 3:
            continue
        if info[2] != '(fetch)':
            continue
        remote_name = info[0]
        remote_url = _normalize_remote(info[1])
        if remote_url in REMOTES_BY_URL:
            return remote_name, remote_url
    raise VCSError("Known remote not found for directory %s; are URLs configurated correctly?" % package_dir)


def get_fetch_url(package_dir, remote):
    """Return a fetch url
       is on osg-build's configured whitelist of urls."""
    out, err = run_git_cmd(package_dir, "remote", "-v")
    if err:
        raise VCSError("Exit code %d getting git status for directory %s. Output:\n%s" % (err, package_dir, out))
    for line in out.splitlines():
        info = line.strip().split()
        if len(info) != 3:
            continue
        if info[2] != '(fetch)':
            continue
        dir_remote_name = info[0]
        dir_remote_url = _normalize_remote(info[1])
        if dir_remote_name == remote:
            return GIT_REMOTE_MAPS.setdefault(dir_remote_url, dir_remote_url)
            # ^^ mutates a constant, sigh

    raise VCSError("Remote URL not found for remote %s in directory %s; are urls " \
        "configured correctly?" % (remote, package_dir))

def get_current_branch_remote(package_dir):
    """Return the configured remote name for the current branch."""
    branch = get_git_branch(package_dir)

    out, err = run_git_cmd(package_dir, "config", f"branch.{branch}.remote")
    if err:
        raise VCSError("Exit code %d getting git branch %s remote for directory '%s'. Output:\n%s" % \
                       (err, branch, package_dir, out))

    return out.strip()


def is_uncommitted(package_dir):
    """Return True if there are uncommitted changes or files in the git working dir."""
    out, err = run_git_cmd(package_dir, "status", "--porcelain")
    if err:
        raise VCSError("Exit code %d getting git status for directory %s. Output:\n%s" % (err, package_dir, out))
    if out:
        print("The following uncommitted changes exist:")
        print(out)
        print("Please commit these first.")
        return True

    remote = get_current_branch_remote(package_dir)

    branch = get_git_branch(package_dir)
    branch_ref = "refs/heads/%s" % branch
    origin_ref_pat = re.compile(r"refs/(urls|remotes)/%s/%s" % (re.escape(remote), re.escape(branch)))

    out, err = run_git_cmd(package_dir, "show-ref")
    if err:
        raise VCSError("Exit code %d getting git references for directory %s.  Output:\n%s" % (err, package_dir, out))
    branch_hash = ''
    origin_hash = ''
    for line in out.splitlines():
        info = line.split()
        if len(info) != 2:
            continue
        if info[1] == branch_ref:
            branch_hash = info[0]
        if origin_ref_pat.fullmatch(info[1]):
            origin_hash = info[0]

    if not branch_hash and not origin_hash:
        raise VCSError("Could not find either local or remote hash for directory %s." % package_dir)
    if branch_hash != origin_hash:
        raise VCSError("Local hash (%s) does not match remote hash "
            "(%s) for directory %s.  Perhaps you need to perform 'git push'?" % \
                       (branch_hash, origin_hash, package_dir))

    return False


def is_outdated(package_dir):
    """Return True if the package has been changed since the revision in the
    local git repo.

    """
    remote = get_current_branch_remote(package_dir)
    branch = get_git_branch(package_dir)
    branch_ref = "refs/heads/%s" % branch
    branch_hash = ''

    out, err = run_git_cmd(package_dir, "show-ref")
    if err:
        raise VCSError("Exit code %d getting git references for directory %s.  Output:\n%s" % (err, package_dir, out))
    for line in out.splitlines():
        info = line.strip().split()
        if len(info) != 2:
            continue
        if info[1] == branch_ref:
            branch_hash = info[0]
            break
    if not branch_hash:
        raise VCSError("Unable to determine local branch's hash.")

    command = git_cmd(package_dir, "ls-remote", "--heads", remote)
    out, err = utils.sbacktick(command)
    if err:
        raise VCSError("Exit code %d getting remote git status for directory %s. Output:\n%s" % (err, package_dir, out))

    remote_hash = ''
    for line in out.splitlines():
        info = line.strip().split()
        if len(info) != 2:
            continue
        if info[1] == branch_ref:
            remote_hash = info[0]
            break
    if not remote_hash:
        raise VCSError("Unable to determine remote branch's hash.")

    if remote_hash == branch_hash:
        return False

    print("Remote hash (%s) does not match local hash (%s) for branch %s." % (remote_hash, branch_hash, branch))
    return True


def verify_working_dir(pkg):
    """Verify if a package working directory has uncommitted changes or is
    outdated and ask the user what to do. Return True if it's ok to continue.

    """
    if is_uncommitted(pkg):
        if not utils.ask_yn("""\
Package working directory %s has uncommitted changes that will not be included
in the git build.
Continue (yes/no)?""" % pkg):
            return False
    if is_outdated(pkg):
        if not utils.ask_yn("""\
Package working directory %s is out of date and its contents may not reflect
what will be built.
Continue (yes/no)?""" % pkg):
            return False
    return True


def verify_package_dir(package_dir):
    """Check if package_dir points to a valid package dir (i.e. contains
    at least an osg/ dir or an upstream/ dir) and is in a git repo.
    """
    out, err = run_git_cmd(package_dir, "ls-files", "osg", "upstream")
    if err:
        raise VCSError("Exit code %d getting git subdirectories of %s. Output:\n%s" % (err, package_dir, out))
    for line in out.split("\n"):
        if line.startswith('osg/') or line.startswith('upstream/'):
            return True
    return False


def verify_git_svn_commit(package_dir):
    """Verify the last commit in the git repo actually came from git-svn."""
    out, err = run_git_cmd(package_dir, "log", "-n", "1")
    if err:
        raise VCSError("Exit code %d getting git log for directory %s. Output:\n%s" % (err, package_dir, out))

    for line in out.splitlines():
        if line.find("git-svn-id:") >= 0:
            return

    raise VCSError("Last git commit not from SVN - possible inconsistency between git and SVN!")


def verify_correct_remote(package_dir):
    """Verify the current branch remote is one of the known urls."""
    remote = get_current_branch_remote(package_dir)
    known_remote = get_known_remote(package_dir)[0]
    if remote != known_remote:
        raise VCSError("Remote %s for directory %s is not an officially known remote." % (remote, package_dir))


def verify_correct_branch(package_dir, buildopts):
    """Check that the user is not trying to build from trunk into upcoming, or
    vice versa.
    """
    if utils.is_url(package_dir):
        # a git url -- we can only do some of our checks
        remote, _, git_branch = parse_git_url(package_dir)
        if not remote:
            raise VCSError("URL %s failed to parse as a git URL" % package_dir)
    else:
        git_branch = get_git_branch(package_dir)
        remote = get_known_remote(package_dir)[1]

        verify_correct_remote(package_dir)

        if remote in REMOTES["osg"].urls:
            verify_git_svn_commit(package_dir)

    assert buildopts['enabled_dvers'], "No enabled dvers -- catch this sooner"
    enabled_dvers = sorted(buildopts['enabled_dvers'])
    _log.debug("found remote %s", remote)
    for dver in enabled_dvers:
        koji_target = buildopts['targetopts_by_dver'][dver]['koji_target']
        if not koji_target:
            _log.debug(f"No koji target for {dver} -- skipping VCS check")
            continue
        for rt in RESTRICTED_TARGETS.values():
            target_match = rt.koji_target_re.fullmatch(koji_target)
            if not target_match:
                continue
            if not rt.git_branch_re:
                raise VCSError(f"cannot build into {koji_target} from Git")
            if remote not in REMOTES_BY_URL:
                raise VCSError(f"cannot build into {koji_target} from unrecognized remote {remote}")
            remote_info = REMOTES_BY_URL[remote]
            if remote_info.name not in rt.remotes:
                raise VCSError(f"cannot build into {koji_target} from the {remote_info.repo} remote")
            _log.debug("remote %s has layout %s", remote_info.name, remote_info.layout)
            if remote_info.layout == RemoteLayout.LEGACY:
                branch = git_branch
                branch_re = rt.git_branch_re
            elif remote_info.layout == RemoteLayout.SUBTREE:
                branch = get_subtree_branch(package_dir)
                branch_re = rt.svn_branch_re  # XXX Rename svn_branch_re to subtree_branch_re
            else:
                assert False, "Unknown remote layout %s" % remote_info.layout
            if not branch_re:
                _log.debug(f"{branch} is not in a repo with restricted branches")
                continue
            branch_match = branch_re.fullmatch(branch)
            if not branch_match or target_match.groupdict() != branch_match.groupdict():
                raise VCSError(f"branch/target mismatch: branch {branch} does not match target {koji_target}")
            break
        else:
            _log.debug(f"{koji_target} is not a restricted target")


def koji(package_dir, koji_obj, buildopts):
    # type: (str, kojiinter.KojiInter, dict) -> int
    """koji task with a git build."""
    if utils.is_url(package_dir):
        remote, package_path, branch = parse_git_url(package_dir)
        if not remote:
            raise Error("Package '%s' does not parse as a Git URL" % package_dir)
        rev = branch
    else:
        package_dir = os.path.abspath(package_dir)
        if not verify_package_dir(package_dir):
            raise UsageError("%s isn't a package directory "
                             "(must have either osg/ or upstream/ dirs or both)" % (package_dir))
        remote = get_fetch_url(package_dir, get_known_remote(package_dir)[0])
        remote_info = REMOTES_BY_URL[remote]
        if remote_info.layout == RemoteLayout.SUBTREE:
            package_path = os.path.join(*(pathlib.Path(package_dir).parts[-2:]))
        else:
            package_path = os.path.basename(package_dir)
        out, err = run_git_cmd(package_dir, "log", "-1", "--pretty=format:%H")
        if err:
            raise VCSError("Exit code %d getting git hash for directory %s. Output:\n%s" % (err, package_dir, out))
        rev = out.strip()

    package_name = os.path.basename(package_path)
    if not re.match(r"\w+", package_name): # sanity check
        raise Error("Package '%s' gives invalid package name '%s'" % (package_dir, package_name))
    if not buildopts.get('scratch'):
        koji_obj.add_pkg(package_name)

    return koji_obj.build_git(remote=_normalize_remote(remote),
                              rev=rev,
                              path=package_path)
