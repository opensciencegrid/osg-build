#!/usr/bin/env python
from glob import glob
import re
from optparse import OptionParser
import os
import subprocess
import sys
import time

from VDTBuildUtils import *


KOJI_HUB = "http://koji-hub.batlab.org/kojihub"
KOJI_TAG = "dist-el5-vdt"
RUNAUTH = "/s/std/bin/runauth"
have_koji = not os.system("which koji &>/dev/null")


def koji_import():
    """Import all rpms into koji."""
    if not have_koji:
        print "Koji not installed. Skipping koji_import."
        return
    for f in glob("*.rpm") + glob("results/*.rpm"):
        unchecked_call("koji import %s --create-build" % f)


def koji_tag():
    """Tag the rpms we just imported."""
    if not have_koji:
        print "Koji not installed. Skipping koji_tag."
        return
    for f in glob("*.rpm") + glob("results/*.rpm"):
        bn = os.path.basename(f)
        # strip off arch and extension
        nvr = re.sub(r'\.\w+\.rpm$', '', bn)
        unchecked_call("koji tag-pkg %s %s" % \
                       (KOJI_TAG, nvr))


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

koji_tag()
koji_import()

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

