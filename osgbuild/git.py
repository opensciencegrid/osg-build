"""Helper functions for a git build."""
from __future__ import absolute_import
from __future__ import print_function
import re
import os
import errno
try:
    # noinspection PyCompatibility
    from urlparse import urlsplit  # Python 2
except ImportError:
    # noinspection PyCompatibility
    from urllib.parse import urlsplit  # Python 3


from .constants import GIT_RESTRICTED_BRANCHES, KOJI_RESTRICTED_TARGETS
from .error import Error, GitError
from . import utils
from . import constants

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
        if not path.endswith(".git"):
            path = path + ".git"
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

def is_restricted_branch(branch):
    """branch is a git branch such as 'osg-3.6' or 'devops'.
    Allows for an optional word as an extra path component on the left.

    """
    for pattern in GIT_RESTRICTED_BRANCHES:
        if re.search(pattern, branch):
            return True
    return False


def is_restricted_target(target):
    """target is a koji target such as 'osg-el6' or 'osg-3.6-el8'.
    Assumes no extra characters on either side.

    """
    for pattern in KOJI_RESTRICTED_TARGETS:
        if re.search(pattern, target):
            return True
    return False


def restricted_branch_matches_target(branch, target):
    """Return True if the pattern that matches `branch` is associated with the
    same name (e.g. 'devops', 'main', 'upcoming', 'versioned') as the pattern that
    matches `target`; False otherwise.
    Special cases:
    - if the name is 'versioned' (e.g. we're building from 'branches/osg-3.1') then the versions also have to match.
    - treat 'main' (i.e. 'trunk') as 'versioned' with a version of '3.5'
    - if the name is 'upcoming' (e.g. building from 'branches/3.6-upcoming') then the versions also have to match.
      treat a missing version ('branches/upcoming') as '3.5'

    Precondition: is_restricted_branch(branch) and is_restricted_target(target)
    are True.

    """
    branch_match = branch_name = target_match = target_name = None
    for (branch_pattern, branch_name) in GIT_RESTRICTED_BRANCHES.items():
        branch_match = re.search(branch_pattern, branch)
        if branch_match:
            break
    assert branch_match, \
            "No GIT_RESTRICTED_BRANCHES pattern matching %s -- is_restricted_branch() should have caught this" % branch

    for (target_pattern, target_name) in KOJI_RESTRICTED_TARGETS.items():
        target_match = re.search(target_pattern, target)
        if target_match:
            break
    assert target_match, \
            "No KOJI_RESTRICTED_TARGETS pattern matching %s -- is_restricted_target() should have caught this" % target

    # At this point branch_name should be one of the values (right-hand side) of
    # GIT_RESTRICTED_BRANCHES, and target_name should be one of the values of
    # KOJI_RESTRICTED_TARGETS.

    # These might have OSG version numbers ("3.5") in them; make sure they match
    branch_osgver = branch_match.groupdict().get("osgver", None)
    target_osgver = target_match.groupdict().get("osgver", None)

    # Deal with "main" (i.e. the "trunk" branch or the "osg-elX" targets), which are aliases for "3.5"
    if target_name == "main":
        target_name = "versioned"
        target_osgver = "3.6"

    # branch_osgver and target_osgver might be None, e.g. for devops but that's OK
    return (branch_name == target_name) and (branch_osgver == target_osgver)


def get_branch(package_dir):
    """Return the current git branch for a given directory."""
    top_dir = os.path.split(os.path.abspath(package_dir))[0]
    command = ["git", "--work-tree", top_dir, "--git-dir", os.path.join(top_dir, ".git"), "branch"]
    out, err = utils.sbacktick(command, err2out=True)
    if err:
        raise GitError("Exit code %d getting git branch for directory %s.  Output:\n%s" % (err, package_dir, out))
    out = out.strip()
    if not out:
        raise GitError("'git branch' returned no output.")

    branch = [ line[2:] for line in out.splitlines() if line.startswith('* ') ]
    if len(branch) != 1 or not branch[0] or ' ' in branch[0]:
        raise GitError("'git branch' indicates no branch is checked out")
    return branch[0]


def get_known_remote(package_dir):
    """Return the first remote in the current directory's list of remotes which
       is on osg-build's configured whitelist of remotes."""
    top_dir = os.path.split(os.path.abspath(package_dir))[0]
    command = ["git", "--work-tree", top_dir, "--git-dir", os.path.join(top_dir, ".git"), "remote", "-v"]
    out, err = utils.sbacktick(command, err2out=True)
    if err:
        raise GitError("Exit code %d getting git status for directory %s. Output:\n%s" % (err, package_dir, out))
    for line in out.splitlines():
        info = line.strip().split()
        if len(info) != 3:
            continue
        if info[2] != '(fetch)':
            continue
        if info[1] in constants.KNOWN_GIT_REMOTES:
            return info[0], info[1]
    raise GitError("OSG remote not found for directory %s; are remotes configurated correctly?" % package_dir)


def get_fetch_url(package_dir, remote):
    """Return a fetch url
       is on osg-build's configured whitelist of remotes."""
    top_dir = os.path.split(os.path.abspath(package_dir))[0]
    command = ["git", "--work-tree", top_dir, "--git-dir", os.path.join(top_dir, ".git"), "remote", "-v"]
    out, err = utils.sbacktick(command, err2out=True)
    if err:
        raise GitError("Exit code %d getting git status for directory %s. Output:\n%s" % (err, package_dir, out))
    for line in out.splitlines():
        info = line.strip().split()
        if len(info) != 3:
            continue
        if info[2] != '(fetch)':
            continue
        if info[0] == remote:
            return constants.GIT_REMOTE_MAPS.setdefault(info[1], info[1])

    raise GitError("Remote URL not found for remote %s in directory %s; are remotes " \
        "configured correctly?" % (remote, package_dir))

def get_current_branch_remote(package_dir):
    """Return the configured remote for the current branch."""
    branch = get_branch(package_dir)

    top_dir = os.path.split(os.path.abspath(package_dir))[0]
    command = ["git", "--work-tree", top_dir, "--git-dir", os.path.join(top_dir, ".git"),
               "config", "branch.%s.remote" % branch]
    out, err = utils.sbacktick(command, err2out=True)
    if err:
        raise GitError("Exit code %d getting git branch %s remote for directory '%s'. Output:\n%s" % \
                       (err, branch, package_dir, out))

    return out.strip()


def is_uncommitted(package_dir):
    """Return True if there are uncommitted changes or files in the git working dir."""
    top_dir = os.path.split(os.path.abspath(package_dir))[0]
    command = ["git", "--work-tree", top_dir, "--git-dir", os.path.join(top_dir, ".git"), "status", "--porcelain"]
    out, err = utils.sbacktick(command, err2out=True)
    if err:
        raise GitError("Exit code %d getting git status for directory %s. Output:\n%s" % (err, package_dir, out))
    if out:
        print("The following uncommitted changes exist:")
        print(out)
        print("Please commit these first.")
        return True

    remote = get_current_branch_remote(package_dir)

    branch = get_branch(package_dir)
    branch_ref = "refs/heads/%s" % branch
    origin_ref = "refs/remotes/%s/%s" % (remote, branch)

    command = ["git", "--work-tree", top_dir, "--git-dir", os.path.join(top_dir, ".git"), "show-ref"]
    out, err = utils.sbacktick(command, err2out=True)
    if err:
        raise GitError("Exit code %d getting git references for directory %s.  Output:\n%s" % (err, package_dir, out))
    branch_hash = ''
    origin_hash = ''
    for line in out.splitlines():
        info = line.split()
        if len(info) != 2:
            continue
        if info[1] == branch_ref:
            branch_hash = info[0]
        if info[1] == origin_ref:
            origin_hash = info[0]

    if not branch_hash and not origin_hash:
        raise GitError("Could not find either local or remote hash for directory %s." % package_dir)
    if branch_hash != origin_hash:
        raise GitError("Local hash (%s) does not match remote hash "
            "(%s) for directory %s.  Perhaps you need to perform 'git push'?" % \
            (branch_hash, origin_hash, package_dir))

    return False


def is_outdated(package_dir):
    """Return True if the package has been changed since the revision in the
    local git repo.

    """
    remote = get_current_branch_remote(package_dir)
    branch = get_branch(package_dir)
    branch_ref = "refs/heads/%s" % branch
    branch_hash = ''

    top_dir = os.path.split(os.path.abspath(package_dir))[0]
    command = ["git", "--work-tree", top_dir, "--git-dir", os.path.join(top_dir, ".git"), "show-ref"]
    out, err = utils.sbacktick(command, err2out=True)
    if err:
        raise GitError("Exit code %d getting git references for directory %s.  Output:\n%s" % (err, package_dir, out))
    for line in out.splitlines():
        info = line.strip().split()
        if len(info) != 2:
            continue
        if info[1] == branch_ref:
            branch_hash = info[0]
            break
    if not branch_hash:
        raise GitError("Unable to determine local branch's hash.")

    out, err = utils.sbacktick(["git", "--work-tree", top_dir, "--git-dir", os.path.join(top_dir, ".git"),
                                "ls-remote", "--heads", remote])
    if err:
        raise GitError("Exit code %d getting remote git status for directory %s. Output:\n%s" % (err, package_dir, out))

    remote_hash = ''
    for line in out.splitlines():
        info = line.strip().split()
        if len(info) != 2:
            continue
        if info[1] == branch_ref:
            remote_hash = info[0]
            break
    if not remote_hash:
        raise GitError("Unable to determine remote branch's hash.")

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
    top_dir = os.path.split(os.path.abspath(package_dir))[0]
    command = ["git", "--work-tree", top_dir, "--git-dir", os.path.join(top_dir, ".git"),
               "rev-parse", "--show-toplevel"]
    out, err = utils.sbacktick(command, err2out=True)
    if err:
        raise GitError("Exit code %d getting git top-level directory of %s. Output:\n%s" % (err, package_dir, out))
    if top_dir != out.strip():
        raise GitError("Specified package directory (%s) is not a top-level directory in the git repo (%s)." % \
                       (package_dir, top_dir))
    command = ["git", "--work-tree", top_dir, "--git-dir", os.path.join(top_dir, ".git"), "ls-files", "osg", "upstream"]
    out, err = utils.sbacktick(command, err2out=True)
    if err:
        raise GitError("Exit code %d getting git subdirectories of %s. Output:\n%s" % (err, package_dir, out))
    for line in out.split("\n"):
        if line.startswith('osg/') or line.startswith('upstream/'):
            return True
    return False


def verify_git_svn_commit(package_dir):
    """Verify the last commit in the git repo actually came from git-svn."""
    top_dir = os.path.split(os.path.abspath(package_dir))[0]
    command = ["git", "--work-tree", top_dir, "--git-dir", os.path.join(top_dir, ".git"), "log", "-n", "1"]
    out, err = utils.sbacktick(command, err2out=True)
    if err:
        raise GitError("Exit code %d getting git log for directory %s. Output:\n%s" % (err, package_dir, out))

    for line in out.splitlines():
        if line.find("git-svn-id:") >= 0:
            return

    raise GitError("Last git commit not from SVN - possible inconsistency between git and SVN!")


def verify_correct_remote(package_dir):
    """Verify the current branch remote is one of the known remotes."""
    remote = get_current_branch_remote(package_dir)
    known_remote = get_known_remote(package_dir)[0]
    if remote != known_remote:
        raise GitError("Remote %s for directory %s is not an officially known remote." % (remote, package_dir))


def verify_correct_branch(package_dir, buildopts):
    """Check that the user is not trying to build from trunk into upcoming, or
    vice versa.
    """
    if utils.is_url(package_dir):
        # a git url -- we can only do some of our checks
        remote, _, branch = parse_git_url(package_dir)
        if not remote:
            raise GitError("URL %s failed to parse as a git URL" % package_dir)
    else:
        branch = get_branch(package_dir)
        remote = get_known_remote(package_dir)[1]

        verify_correct_remote(package_dir)

        if remote in [constants.OSG_REMOTE, constants.OSG_AUTH_REMOTE]:
            verify_git_svn_commit(package_dir)

    # We only have branching rules for OSG and HCC repos
    if remote not in constants.KNOWN_GIT_REMOTES:
        return

    if not is_restricted_branch(branch):
        # Developer branch -- any target ok
        return
    for dver in buildopts['enabled_dvers']:
        target = buildopts['targetopts_by_dver'][dver]['koji_target']
        _do_target_remote_checks(target, remote, branch)
        if not is_restricted_target(target):
            # Some custom target -- any branch ok
            continue
        if not restricted_branch_matches_target(branch, target):
            raise GitError("Forbidden to build from %s branch into %s target" % (branch, target))


def _do_target_remote_checks(target, remote, branch):
        if target.startswith("hcc-"):
            if "master" not in branch:
                raise Error("""\
Error: Incorrect branch for koji build
Only allowed to build into the HCC repo from the
master branch!  You must switch branches.""")
            if remote not in [constants.HCC_REMOTE, constants.HCC_AUTH_REMOTE]:
                raise Error("""\
Error: You must build into the HCC repo when building from
a HCC git checkout.  You must switch git repos or build targets.""")
        elif re.search(r"osg(?:-\d+\.\d+)?-upcoming-el\d+$", target):
            if remote not in [constants.OSG_REMOTE, constants.OSG_AUTH_REMOTE]:
                raise Error("""\
Error: You may not build into the OSG repo when building from
a non-OSG target.  You must switch git repos or build targets.
Try adding "--repo=hcc" to the command line.""")
            if "master" in branch:
                raise Error("""\
Error: Incorrect branch for koji build
Not allowed to build into the upcoming targets from
master branch!  You must switch branches or build targets.""")
        elif "osg" in target:
            if remote not in [constants.OSG_REMOTE, constants.OSG_AUTH_REMOTE]:
                raise Error("""\
Error: You may not build into the OSG repo when building from
a non-OSG target.  You must switch git repos or build targets.
Try adding "--repo=hcc" to the command line.""")
            if "upcoming" in branch:
                raise Error("""\
Error: Incorrect branch for koji build
Only allowed to build packages from one of the upcoming branches
into the upcoming targets.  Either switch the branch to master,
 or pass the appropriate --upcoming or --3.X-upcoming flag.""")


def koji(package_dir, koji_obj, buildopts):
    """koji task with a git build."""
    if utils.is_url(package_dir):
        remote, package_name, branch = parse_git_url(package_dir)
        if not remote:
            raise Error("Package '%s' does not parse as a Git URL" % package_dir)
        rev = branch
    else:
        package_dir = os.path.abspath(package_dir)
        verify_package_dir(package_dir)
        package_name = os.path.basename(package_dir)
        remote = get_fetch_url(package_dir, get_known_remote(package_dir)[0])

        top_dir = os.path.split(os.path.abspath(package_dir))[0]
        command = ["git", "--work-tree", top_dir, "--git-dir", os.path.join(top_dir, ".git"),
                   "log", "-1", "--pretty=format:%H"]
        out, err = utils.sbacktick(command, err2out=True)
        if err:
            raise GitError("Exit code %d getting git hash for directory %s. Output:\n%s" % (err, package_dir, out))
        rev = out.strip()

    if not re.match(r"\w+", package_name): # sanity check
        raise Error("Package '%s' gives invalid package name '%s'" % (package_dir, package_name))
    if not buildopts.get('scratch'):
        koji_obj.add_pkg(package_name)

    return koji_obj.build_git(remote,
                              rev,
                              package_name)
