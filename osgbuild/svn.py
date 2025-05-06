"""Helper functions for an SVN build."""
import logging
import re
import os

from .error import Error, VCSError, UsageError
from .target_protection import RESTRICTED_TARGETS
from . import utils

SVN_ROOT = "https://vdt.cs.wisc.edu/svn"
SVN_REDHAT_PATH = "/native/redhat"

_log = logging.getLogger(__name__)


def is_svn(package_dir):
    """Determine whether a given directory is part of an SVN repo."""
    # If package_dir is a URL, not a directory, then we can't cd into it to
    # check. Assume True unless it's a git or git+https URL or similar
    if utils.is_url(package_dir):
        scheme, _ = package_dir.split(":", 1)
        if "git" in scheme:
            return False
        return True
    try:
        with utils.chdir(package_dir):
            command = ["svn", "info"]
            try:
                err = utils.sbacktick(command, err2out=True)[1]
            except FileNotFoundError:
                _log.debug("'svn' command not found, assuming not SVN")
                return False
            if err == 0:
                return True
            else:
                return False
    except (FileNotFoundError, NotADirectoryError) as err:
        raise VCSError("%s is not a valid package directory\n(%s)" % (package_dir, err))


def is_uncommitted(package_dir):
    """Return True if there are uncommitted changes in the SVN working dir."""
    if utils.is_url(package_dir):
        return False
    out, err = utils.sbacktick("svn status -q " + package_dir, err2out=True)
    if err:
        raise VCSError("Exit code %d getting SVN status. Output:\n%s" % (err, out))
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
        raise VCSError("Exit code %d getting SVN status. Output:\n%s" % (err, out))
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
        raise VCSError("Exit code %d getting SVN listing of %s (rev %s). Output:\n%s" % (err, url, rev, out))
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


def verify_correct_branch(package_dir, buildopts):
    package_info = get_package_info(package_dir)
    url = package_info['canon_url']

    if SVN_REDHAT_PATH + '/branches/' not in url:
        raise VCSError("must build from a branch in branches/")

    branch = url.rsplit('/')[-2]  # .../branches/osg-3.6/xrootd -> osg-3.6
    assert buildopts['enabled_dvers'], "No enabled dvers -- catch this sooner"
    enabled_dvers = sorted(buildopts['enabled_dvers'])
    for dver in enabled_dvers:
        koji_target = buildopts['targetopts_by_dver'][dver]['koji_target']
        if not koji_target:
            _log.debug(f"No koji target for {dver} -- skipping VCS check")
            continue
        for rt in RESTRICTED_TARGETS.values():
            target_match = rt.koji_target_re.fullmatch(koji_target)
            if not target_match:
                continue
            if not rt.svn_branch_re:
                raise VCSError(f"cannot build into {koji_target} from SVN")
            branch_match = rt.svn_branch_re.fullmatch(branch)
            if not branch_match:
                raise VCSError(f"branch/target mismatch: {branch} does not match {koji_target}")
            if target_match.groupdict() != branch_match.groupdict():
                raise VCSError(f"branch/target mismatch: {branch} does not match {koji_target}")
            break
        else:
            _log.debug(f"{koji_target} is not a restricted target")


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
        raise VCSError("Exit code %d getting SVN info. Output:\n%s" % (err, out))
    info = dict()
    for line in out.split("\n"):
        label, value = line.strip().split(": ", 1)
        label = label.strip().lower().replace(' ', '_')
        info[label] = value
    # 'canon_url' is the https URL of the package directory (in case the
    # local repository is checked out via a file:/// URL.
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
