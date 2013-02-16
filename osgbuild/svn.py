"""Helper functions for an SVN build."""
import re
import os

from osgbuild.constants import SVN_ROOT, SVN_TRUNK_PATH, SVN_UPCOMING_PATH
from osgbuild.error import Error, SVNError, UsageError
from osgbuild import utils

def is_uncommitted(package_dir):
    """Return True if there are uncommitted changes in the SVN working dir."""
    out, err = utils.sbacktick("svn status -q " + package_dir)
    if err:
        raise SVNError("Exit code %d getting SVN status. Output:\n%s" % (err, out))
    if out:
        print "The following uncommitted changes exist:"
        print out
        return True
    else:
        return False


def is_outdated(package_dir):
    """Return True if the package has been changed since the revision in the
    SVN working dir.

    """
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
        print "The following outdated files exist:"
        print "\n".join(outdated_files)
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
    out, err = utils.sbacktick(command, clocale=True, err2out=True)
    if err:
        raise SVNError("Exit code %d getting SVN listing of %s (rev %s). Output:\n%s" % (err, url, rev, out))
    for line in out.split("\n"):
        if line.startswith('osg/') or line.startswith('upstream/'):
            return True
    return False

        
def verify_correct_branch(package_dir, buildopts):
    """Check that the user is not trying to build from trunk into upcoming, or
    vice versa.

    """
    package_info = get_package_info(package_dir)
    url = package_info['canon_url']
    for dver in buildopts['enabled_dvers']:
        if buildopts['targetopts_by_dver'][dver]['koji_target'].endswith('osg-upcoming'):
            if re.search(SVN_TRUNK_PATH, url):
                raise Error("""\
Error: Incorrect branch for koji build
Not allowed to build into the upcoming targets from
trunk (SVN/%s)!  Either move the package dir into the
upcoming area (SVN/%s) or a separate branch, or do not build
it for the upcoming targets (i.e. do not pass the --upcoming,
or the --koji-target el5-osg-upcoming or el6-osg-upcoming flags).""" % (SVN_TRUNK_PATH, SVN_UPCOMING_PATH))
        else:
            if re.search(SVN_UPCOMING_PATH, url):
                raise Error("""\
Error: Incorrect branch for koji build
Only allowed to build packages from the upcoming area (SVN/%s)
into the upcoming targets.  Either move the package dir
into trunk (SVN/%s) or a separate branch, or pass the
--upcoming flag.""" % (SVN_UPCOMING_PATH, SVN_TRUNK_PATH))



def get_package_info(package_dir, rev=None):
    """Return the svn info for a package dir."""
    command = ["svn", "info", package_dir]
    if rev:
        command += ["-r", rev]
    else:
        command += ["-r", "HEAD"]

    out, err = utils.sbacktick(command, clocale=True, err2out=True)
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
    if not re.match("\w+", package_name): # sanity check
        raise Error("Package directory '%s' gives invalid package name '%s'" % (package_dir, package_name))
    if not verify_package_info(package_info):
        raise UsageError("%s isn't a package directory "
                         "(must have either osg/ or upstream/ dirs or both)" % (package_dir))

    if not buildopts.get('scratch'):
        koji_obj.add_pkg(package_name)
    return koji_obj.build_svn(package_info['canon_url'],
                              package_info['revision'])


