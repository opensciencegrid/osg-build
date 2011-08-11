#!/usr/bin/env python
from glob import glob
import re
from optparse import OptionParser
import os
import subprocess
import sys
import time

from VDTBuildUtils import *


RUNAUTH = "/s/std/bin/runauth"


# Turn off buffering for stdout/stderr
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 0)

parser = OptionParser()
parser.add_option("--host")
parser.add_option("--results-dir")
parser.add_option("--yum-base")
parser.add_option("--script")
options, args = parser.parse_args(sys.argv[1:])

checked_call(["tar", "xvzf", "results.tar.gz"])

try:
    tempdir = "/tmp/results-%d.%d.%s" % \
        (os.getuid(), os.getpid(), time.strftime("%H%M", time.localtime()))
    checked_call(["scp", "-r", "results", options.host + ":" + tempdir])
except CalledProcessError, e:
    print >>sys.stderr, "Unable to scp files to " + options.host
    print >>sys.stderr, "If this is an authentication error, check to make"
    print >>sys.stderr, "sure your ssh keys are set up."
    print >>sys.stderr, \
        "See https://twiki.grid.iu.edu/bin/view/Documentation/VDTRPMBatlabBuild"
    
    sys.exit(1)

if re.search(
        RUNAUTH,
        subprocess.Popen(["ssh", options.host, "which", RUNAUTH],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[0]):
    ssh_cmd = ["ssh", "-x", options.host, RUNAUTH]
else:
    ssh_cmd = ["ssh", "-x", options.host]

checked_call(ssh_cmd + ["/bin/mv", os.path.join(tempdir, "*"),
                        options.results_dir])
unchecked_call(ssh_cmd + ["/bin/rmdir", tempdir])

if options.yum_base:
    print "Pushing to yum repos under ", options.yum_base
    checked_call(ssh_cmd + [options.script,
                            "push", os.path.join(options.results_dir, "*.rpm"),
                            "--yum-base", options.yum_base])
else:
    print "Not pushing to yum repos"

