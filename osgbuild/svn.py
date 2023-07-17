"""Helper functions for an SVN build."""
from __future__ import absolute_import
from __future__ import print_function
import re
import os
import errno

from .constants import SVN_ROOT, SVN_REDHAT_PATH, SVN_RESTRICTED_BRANCHES, KOJI_RESTRICTED_TARGETS
from .error import Error, SVNError, UsageError
from . import utils


def is_svn(package_dir):
    """Determine whether a given directory is part of an SVN repo."""
    # If package_dir is a URL, not a directory, then we can't cd into it to
    # check. Assume True unless it's a git or git+https URL or similar
    if utils.is_url(package_dir):
        scheme, _ = package_dir.split(":", 1)
        if "git" in scheme:
            return False
        return True
    pwd = os.getcwd()
    try:
        try:
            os.chdir(package_dir)
        except OSError as ose:
            if ose.errno == errno.ENOENT:
                raise Error("%s is not a valid package directory\n(%s)" % (package_dir, ose))
        command = ["svn", "info"]
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


def is_uncommitted(package_dir):
    """Return True if there are uncommitted changes in the SVN working dir."""
    if utils.is_url(package_dir):
        return False
    out, err = utils.sbacktick("svn status -q " + package_dir, err2out=True)
    if err:
        raise SVNError("Exit code %d getting SVN status. Output:\n%s" % (err, out))
    if out:
        print("The following uncommitted changes exist:")
        print(out)
        return True
    else:
        return False


def is_outdated(package_dir):
    """Return True if the package has been changed since the revision in the
    SVN working dir.

    """
    if utils.is_url(package_dir):
        return False
    out, err = utils.sbacktick("svn status -u -q " + package_dir)
    if err:
        raise SVNError("Exit code %d getting SVN status. Output:\n%s" % (err, out))
    outdated_files = []
    for line in out.split("\n"):
        try:
            outdated_flag = line[8]
        except IndexError:
            continue
        if outdated_flag == "*":
            outdated_files.append(line)
    if outdated_files:
        print("The following outdated files exist:")
        print("\n".join(outdated_files))
        return True
    else:
        return False


def verify_working_dir(pkg):
    """Verify if a package working directory has uncommitted changes or is
    outdated and ask the user what to do. Return True if it's ok to continue.

    """
    if is_uncommitted(pkg):
        if not utils.ask_yn("""\
Package working directory %s has uncommitted changes that will not be included
in the SVN build.
Continue (yes/no)?""" % pkg):
            return False
    if is_outdated(pkg):
        if not utils.ask_yn("""\
Package working directory %s is out of date and its contents may not reflect
what will be built.
Continue (yes/no)?""" % pkg):
            return False
    return True


def verify_package_info(package_info):
    """Check if package_info points to a valid package dir (i.e. contains
    at least an osg/ dir or an upstream/ dir).

    """
    url = package_info['canon_url']
    rev = package_info['revision']
    command = ["svn", "ls", url, "-r", rev]
    out, err = utils.sbacktick(command, err2out=True)
    if err:
        raise SVNError("Exit code %d getting SVN listing of %s (rev %s). Output:\n%s" % (err, url, rev, out))
    for line in out.split("\n"):
        if line.startswith('osg/') or line.startswith('upstream/'):
            return True
    return False


#
# Branch checking
#
# We need to forbid building from certain SVN branches into certain Koji
# targets. This is implemented by having two dicts mapping regexp patterns to
# names, one containing the restricted SVN branches and one containing the
# restricted Koji targets.
#
# We're permissive by default: if neither the branch nor the target match any
# of the regexps in their respective dicts, the build is allowed. On the other
# hand, if both are restricted then the branch name has to match the target
# name.
#

def is_restricted_branch(branch):
    """branch is an SVN branch such as 'trunk' or 'branches/osg-3.1'.
    Assumes no extra characters on either side (no 'native/redhat/trunk' or
    'trunk/gums')

    """
    for pattern in SVN_RESTRICTED_BRANCHES:
        if re.search(pattern, branch):
            return True
    return False

def is_restricted_target(target):
    """target is a koji target such as 'el5-osg' or 'osg-3.1-el5'.
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
    for (branch_pattern, branch_name) in SVN_RESTRICTED_BRANCHES.items():
        branch_match = re.search(branch_pattern, branch)
        if branch_match:
            break
    assert branch_match, \
            "No SVN_RESTRICTED_BRANCHES pattern matching %s -- is_restricted_branch() should have caught this" % branch

    for (target_pattern, target_name) in KOJI_RESTRICTED_TARGETS.items():
        target_match = re.search(target_pattern, target)
        if target_match:
            break
    assert target_match, \
            "No KOJI_RESTRICTED_TARGETS pattern matching %s -- is_restricted_target() should have caught this" % target

    # At this point branch_name should be one of the values (right-hand side) of
    # SVN_RESTRICTED_BRANCHES, and target_name should be one of the values of
    # KOJI_RESTRICTED_TARGETS.

    # These might have OSG version numbers ("3.5") in them; make sure they match
    branch_osgver = branch_match.groupdict().get("osgver", None)
    target_osgver = target_match.groupdict().get("osgver", None)

    if target_name == "main":
        target_name = "versioned"
        target_osgver = "3.6"

    # branch_osgver and target_osgver might be None, e.g. for devops but that's OK
    return (branch_name == target_name) and (branch_osgver == target_osgver)

def verify_correct_branch(package_dir, buildopts):
    """Check that the user is not trying to build with bad branch/target
    combinations. For example, building from osg-3.6 into 3.6-upcoming, or building
    from osg-3.6 into 23-main.

    """
    package_info = get_package_info(package_dir)
    url = package_info['canon_url']
    # Check for old, deprecated branches
    if SVN_REDHAT_PATH + '/trunk/' in url:
        raise SVNError("trunk has been removed; use branches/osg-3.5 instead")
    elif SVN_REDHAT_PATH + '/branches/upcoming/' in url:
        raise SVNError("unversioned upcoming has been removed; use branches/3.5-upcoming instead")
    branch_match = re.search(SVN_REDHAT_PATH + r'/(branches/[^/]+)/', url)
    if not branch_match:
        # Building from a weird path (such as a tag). Be permissive -- koji
        # itself will catch building from outside SVN so we don't have to
        return
    branch = branch_match.group(1)
    if not is_restricted_branch(branch):
        # Developer branch -- any target ok
        return
    for dver in buildopts['enabled_dvers']:
        target = buildopts['targetopts_by_dver'][dver]['koji_target']
        if not is_restricted_target(target):
            # Some custom target -- any branch ok
            continue
        if not restricted_branch_matches_target(branch, target):
            raise SVNError("Forbidden to build from %s branch into %s target" % (branch, target))


def get_package_info(package_dir):
    """Return the svn info for a package dir."""
    command = ["svn", "info", package_dir]
    # If we don't specify the revision in the argument (e.g. no foo@19999)
    # then explicitly specify HEAD to make sure we're not getting an older
    # version.
    if not re.search(r'@\d+$', package_dir):
        command += ['-r', 'HEAD']

    out, err = utils.sbacktick(command, err2out=True)
    if err:
        raise SVNError("Exit code %d getting SVN info. Output:\n%s" % (err, out))
    info = dict()
    for line in out.split("\n"):
        label, value = line.strip().split(": ", 1)
        label = label.strip().lower().replace(' ', '_')
        info[label] = value
    info['canon_url'] = re.sub("^" + re.escape(info['repository_root']), SVN_ROOT, info['url'])
    return info


def koji(package_dir, koji_obj, buildopts):
    """koji task with an svn build."""
    package_info = get_package_info(package_dir)
    package_name = os.path.basename(package_info['canon_url'])
    if not re.match(r"\w+", package_name): # sanity check
        raise Error("Package directory '%s' gives invalid package name '%s'" % (package_dir, package_name))
    if not verify_package_info(package_info):
        raise UsageError("%s isn't a package directory "
                         "(must have either osg/ or upstream/ dirs or both)" % (package_dir))

    if not buildopts.get('scratch'):
        koji_obj.add_pkg(package_name)
    return koji_obj.build_svn(package_info['canon_url'],
                              package_info['revision'])


