import atexit
import os
import re
import shutil
import sys
import tempfile
from os.path import join as opj

from osgbuild import constants as C

try:
    # type checking, if avaliable
    from typing import List, Optional
except ImportError:  # Python 2
    List = Optional = None

from osgbuild.utils import find_file, errprintf, checked_backtick, checked_call, CalledProcessError

OSG_36 = "native/redhat/branches/osg-3.6"
OSG_36_UPCOMING = "native/redhat/branches/3.6-upcoming"
OSG_23_MAIN = "native/redhat/branches/23-main"
OSG_23_UPCOMING = "native/redhat/branches/23-upcoming"


def regex_in_list(pattern, listing):
    return [x for x in listing if re.match(pattern, x)]


def go_to_temp_dir():
    working_dir = tempfile.mkdtemp(prefix="osg-build-test-")
    atexit.register(shutil.rmtree, working_dir, ignore_errors=True, onerror=None)
    os.chdir(working_dir)
    return working_dir


def common_setUp(path, rev):
    """Create a temporary directory, ensure it gets deleted on exit, cd to it,
    and check out a specific revision of a path from our SVN.

    """
    working_dir = go_to_temp_dir()
    svn_export(path, rev, os.path.basename(path))
    return opj(working_dir, os.path.basename(path))


def backtick_osg_build(cmd_args, *args, **kwargs):
    kwargs['clocale'] = True
    kwargs['err2out'] = True
    return checked_backtick([sys.executable, "-m", "osgbuild.main"] + cmd_args, *args, **kwargs)


def checked_osg_build(cmd_args, *args, **kwargs):
    return checked_call([sys.executable, "-m", "osgbuild.main"] + cmd_args, *args, **kwargs)


def svn_export(path, rev, destpath):
    """Run svn export on a revision rev of path into destpath"""
    try:
        checked_backtick(
            ["svn", "export", opj(C.SVN_ROOT, path) + "@" + rev, "-r", rev, destpath],
            err2out=True)
    except CalledProcessError as err:
        errprintf("Error in svn export:\n%s", err.output)
        raise
