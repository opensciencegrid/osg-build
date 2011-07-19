#!/usr/bin/env python
from glob import glob
from fnmatch import fnmatch
import os
import re
import shutil
import subprocess
import sys

have_mock = not os.system("which mock &>/dev/null")

class RemoteTaskError(Exception):
    pass

def checked_call(*args):
    err = subprocess.call(*args)
    if err:
        raise RemoteTaskError("subprocess.call(" + str(args) + ") returned " +
                              str(err) + "!")

def init_nmi():
    taskname = os.environ.get('_NMI_TASKNAME')
    if taskname is None:
        raise RemoteTaskError("_NMI_TASKNAME not in environment!")
    if not os.environ.get('NMI_PLATFORM'):
        raise RemoteTaskError("NMI_PLATFORM not in environment!")
    if taskname == '':
        print("No task specified, returning SUCCESS")
        sys.exit(0)
    if os.environ.get('_NMI_STEP_FAILED'):
        raise RemoteTaskError("Previous step failed, can't continue with " +
                              taskname)

    return taskname

def rebuild_i386():
    global have_mock
    if re.search('x86_64', os.environ['NMI_PLATFORM']) and not have_mock:
        print("Not building a 32-bit package on a 64-bit platform without mock")
        return 0
    else:
        return rebuild('i386')

def rebuild_x86_64():
    global have_mock
    if not re.search('x86_64', os.environ['NMI_PLATFORM']):
        print("Not building a 64-bit package on a 32-bit platform.")
        return 0
    else:
        return rebuild('x86_64')

def rebuild(arch=None):
    global have_mock
    if arch is None:
        arch = re.search('x86(_64)?', os.environ['NMI_PLATFORM'])
    if not have_mock:
        print("Mock doesn't exist on this machine. Using rpmbuild.")
        os.makedirs("tmp")
        cwd = os.getcwd()
        cmd = ["rpmbuild", "--rebuild"]
        for d in ["_topdir", "_srcrpmdir", "_specdir", "_sourcedir",
                  "_builddir", "_rpmdir"]:
            cmd += ["--define=" + d + " " + cwd]
        cmd += ["--define=_tmppath " + cwd + "/tmp"]
        cmd += ["--define=_build_name_fmt %%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm"]
        cmd += ["--define=dist .vdt"]
        cmd += [glob("*.src.rpm")[0]]

        checked_call(cmd)
    else:
        cwd = os.getcwd()
        try:
            mock_cfg = re.sub(r'\.cfg$', '',
                              glob("glue/mock-auto-" + arch + "*")[0])
        except IndexError:
            raise RemoteTaskError("No mock config for this platform!")
        if os.path.exists("/etc/mock/site-defaults.cfg"):
            shutil.copy("/etc/mock/site-defaults.cfg", cwd)
        if os.path.exists("/etc/mock/logging.ini"):
            shutil.copy("/etc/mock/logging.ini", cwd)
        cmd = ["mock", "--configdir", cwd, "-r", mock_cfg,
               "--resultdir", cwd, "--rebuild", glob("*.src.rpm")[0]]
        checked_call(cmd)

def package():
    os.makedirs("results")
    for f in glob("*.rpm"):
        if not fnmatch(f, "*.src.rpm"):
            shutil.copy(f, "results")
    
    cmd = "tar czvf results.tar.gz results".split(' ')
    checked_call(cmd)
    
# Turn off buffering for stdout/stderr
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 0)

taskname = init_nmi()

print("===== Environment =====")
for k in sorted(os.environ.keys()):
    print "%-20s = %s" % (k,os.environ[k])
print("===== Files =====")
os.system("ls -lR")

eval("sys.exit(" + os.environ['_NMI_TASKNAME'] + "())")


