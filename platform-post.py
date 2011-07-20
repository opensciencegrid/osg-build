#!/usr/bin/env python
from glob import glob
import re
from optparse import OptionParser
import os
import subprocess
import sys

class PlatformPostError(Exception):
    pass

def checked_call(*args):
    err = subprocess.call(*args)
    if err:
        raise PlatformPostError("subprocess.call(" + str(args) +
                                ") returned " + str(err) + "!")


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

files = glob("results/*")

for f in files:
    checked_call(["scp", f, options.host + ":" + options.results_dir])

if options.yum_base:
    print("Pushing to yum repos under", options.yum_base)
    if options.host.endswith('.cs.wisc.edu'): # TODO: HACK
        checked_call(["ssh", "-x", options.host,
                    "/s/std/bin/runauth", options.script,
                    "push", os.path.join(options.results_dir, "*.rpm"),
                    "--yum-base", options.yum_base])
    else:
        checked_call(["ssh", "-x", options.host,
                    options.script,
                    "push", os.path.join(options.results_dir, "*.rpm"),
                    "--yum-base", options.yum_base])
else:
    print("Not pushing to yum repos")

