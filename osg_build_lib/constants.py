import string
import os
WD_RESULTS = '_build_results'
WD_PREBUILD = '_final_srpm_contents'
WD_UNPACKED = '_upstream_srpm_contents'
WD_UNPACKED_TARBALL = '_upstream_tarball_contents'
AFS_CACHE_PATH = '/p/vdt/public/html/upstream'
AFS_CACHE_PREFIX = 'file://' + AFS_CACHE_PATH
WEB_CACHE_PREFIX = 'http://vdt.cs.wisc.edu/upstream'
DEFAULT_CONFIG_FILE = os.path.expanduser("~/.osg-build.ini")
ALT_DEFAULT_CONFIG_FILE = os.path.expanduser("~/.vdt-build.ini")
DEFAULT_KOJI_TAG = "el5-osg"
DEFAULT_KOJI_TARGET = "el5-osg"

KOJI_USER_CONFIG_DIR = os.path.expanduser("~/.koji")
KOJI_CLIENT_CERT = os.path.join(KOJI_USER_CONFIG_DIR, "client.crt") # TODO needs to be synced with osg-koji.conf
KOJI_SERVER_CERT = os.path.join(KOJI_USER_CONFIG_DIR, "osg-ca-bundle.crt") # TODO needs to be synced with osg-koji.conf

KOJI_ESNET_CA_HASH = "d1b603c3"
KOJI_ESNET_CA_SUBJECT = "subject= /DC=net/DC=ES/O=ESnet/OU=Certificate Authorities/CN=ESnet Root CA 1"
KOJI_DOEGRIDS_CA_HASH = "1c3f2ca8"
KOJI_DOEGRIDS_CA_SUBJECT = "subject= /DC=org/DC=DOEGrids/OU=Certificate Authorities/CN=DOEGrids CA 1"

DOEGRIDS_TARBALL_URL = "https://pki1.doegrids.org/Other/doegrids.tar"

GRID_CERTS_DIR = "/etc/grid-security/certificates"

KOJI_CONF = "osg-koji.conf"
DATA_DIR = "/usr/share/osg-build"

CMDFILE_TEMPLATE = string.Template("""
component           = $NAME
component_version   = $VERSION-$RELEASE
description         = $NAME $VERSION-$RELEASE RPM build
inputs              = glue.scp, srpm.scp
notify              = $NOTIFY
platform_post       = glue/platform-post.py
platform_post_args  = " $PLATFORM_POST_ARGS "
platforms           = x86_64_sl_5.6
project             = VDT
project_release     = 3.0
remote_declare      = glue/remote-declare.py
remote_declare_args = rebuild_i386 rebuild_x86_64 package
remote_task         = glue/remote-task.py
remote_task_args    = " $REMOTE_TASK_ARGS "
run_type            = build
#append_requirements = (Machine =?= 'mock-1.batlab.org')
""")

GLUE_SCP_TEXT = """
method      = scp
scp_file    = @NMIDIR@/glue
recursive   = true
untar       = false
"""

SRPM_SCP_TEMPLATE = string.Template("""
method      = scp
scp_file    = @NMIDIR@/$SRPM
recursive   = false
untar       = false
""")


