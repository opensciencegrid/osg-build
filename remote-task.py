#!/usr/bin/env python
from glob import glob
from fnmatch import fnmatch
from optparse import OptionParser
import os
import re
import shutil
import subprocess
import sys

from VDTBuildUtils import *
from VDTBuildMockConfig import *


have_mock = not os.system("which mock &>/dev/null")

class RemoteTaskError(Exception):
    pass


def init_nmi():
    taskname = os.environ.get('_NMI_TASKNAME')
    if taskname is None:
        raise RemoteTaskError("_NMI_TASKNAME not in environment!")
    if not os.environ.get('NMI_PLATFORM'):
        raise RemoteTaskError("NMI_PLATFORM not in environment!")
    if taskname == '':
        print "No task specified, returning SUCCESS"
        sys.exit(0)
    if os.environ.get('_NMI_STEP_FAILED'):
        raise RemoteTaskError("Previous step failed, can't continue with " +
                              taskname)

    return taskname




def rebuild_i386():
    global have_mock
    if re.search('x86_64', os.environ['NMI_PLATFORM']) and not have_mock:
        print "Not building a 32-bit package on a 64-bit platform without mock"
        return 0
    else:
        return rebuild('i386')


def rebuild_x86_64():
    if not re.search('x86_64', os.environ['NMI_PLATFORM']):
        print "Not building a 64-bit package on a 32-bit platform."
        return 0
    else:
        return rebuild('x86_64')


def rebuild_rpmbuild():
    print "Mock doesn't exist on this machine. Using rpmbuild."
    os.makedirs("tmp")
    cwd = os.getcwd()
    cmd = ["rpmbuild", "--rebuild"]
    for d in ["_topdir", "_srcrpmdir", "_specdir", "_sourcedir",
                "_builddir", "_rpmdir"]:
        cmd += ["--define=" + d + " " + cwd]
    cmd += ["--define=_tmppath " + cwd + "/tmp"]
    cmd += ["--define=_build_name_fmt %%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm"]
    cmd += ["--define=dist .osg"]
    cmd += [glob("*.src.rpm")[0]]

    checked_call(cmd)


def rebuild(arch=None):
    global have_mock
    if not have_mock:
        return rebuild_rpmbuild()
    global options

    # Make a mock config
    if arch is None:
        arch = re.search('x86(_64)?', os.environ['NMI_PLATFORM'])
    mockver = get_mock_version()

    cwd = os.getcwd()
    mock_cfg = make_mock_config(arch, cwd, mockver, options.dist,
                                os.environ.get("_CONDOR_SLOT", "0"))
    copy_mock_extra_config_files(cwd, mockver)
    print "Using mock config " + mock_cfg + ":"

    print slurp(mock_cfg+".cfg")

    print "Starting up mock"
    cmd = ["mock", "--configdir", cwd, "-r", mock_cfg,
            "--resultdir", cwd,
            "--arch", arch+",noarch",
            "--rebuild", glob("*.src.rpm")[0]]
    try:
        checked_call(cmd)
    except CalledProcessError, e:
        print "Error executing mock\n" + str(e)
        print "Mock logs follow:"
        for logfile in glob("*.log"):
            print "\n----- %s -----" % logfile
            print slurp(logfile)
        sys.exit(1)
            

def package():
    """Put the binary rpms into a tarball. Not putting the srpm in because
    there is already a copy on the submit machine.

    """
    os.makedirs("results")
    for f in glob("*.rpm"):
        if not fnmatch(f, "*.src.rpm"):
            shutil.copy(f, "results")
    
    cmd = "tar czvf results.tar.gz results".split(' ')
    checked_call(cmd)


# Turn off buffering for stdout/stderr
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 0)

print "  ===== Arguments ====="
print " ".join(sys.argv)

print "  ===== Environment ====="
for k in sorted(os.environ.keys()):
    print "%-20s = %s" % (k,os.environ[k])
print "  ===== Files ====="
os.system("ls -lR")

parser = OptionParser()
parser.set_defaults(dist="osg")
parser.add_option("--dist")
options, args = parser.parse_args(sys.argv[1:])

taskname = init_nmi()

print "======= Task Output ======="
eval("sys.exit(" + os.environ['_NMI_TASKNAME'] + "())")


