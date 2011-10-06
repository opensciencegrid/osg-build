import os
import re
import shutil
import string
import subprocess
import sys

from osg_build_lib.utils import *


def get_mock_version():
    """Return mock version as a 2-element tuple (major, minor)"""
    query = subprocess.Popen(
        ["rpm", "-q", "mock"], stdout=subprocess.PIPE).communicate()[0]
    match = re.match(r'''mock-((?:\d+\.?)+)-''', query)
    if not match:
        print >>sys.stderr,"Unable to determine the mock version"
        print >>sys.stderr,"Make sure mock in installed (yum install mock)"
        raise Exception(query) # TODO do better than this
    version = [int(x) for x in match.group(1).split(".")]
    return tuple(version)


def make_mock_config(arch, cfg_dir, mockver=None, dist='osg', index=''):
    """Autogenerate a mock config for arch 'arch'. 'mockver' is needed because
    mock config file format changed incompatibly somewhere in mock 0.8 or so
    and we need support for both 0.6.x (centos) and 1.x (batlab, epel).

    """
    if re.match(r'i[3-6]86', arch):
        basearch = 'i386'
    else:
        basearch = arch
    if index != '':
        index = '.' + index
    cfg_name = "mock-auto-%s%s" % (arch, index)
    cfg_path = os.path.join(cfg_dir, cfg_name + ".cfg")
    if mockver is None:
        mockver = get_mock_version()

    if mockver < (0, 8):
        template = OLD_MOCK_CFG_TEMPLATE
    else:
        template = NEW_MOCK_CFG_TEMPLATE


    unslurp(cfg_path,
            template.safe_substitute(
                NAME=cfg_name, ARCH=arch, BASEARCH=basearch,
                DIST=dist))

    return cfg_name


def copy_mock_extra_config_files(cfg_dir, mockver=None, force=False):
    if mockver is None:
        mockver = get_mock_version()

    if mockver >= (0, 8):
        for filename in ['site-defaults.cfg', 'logging.ini']:
            system_filepath = os.path.join("/etc/mock", filename)
            local_filepath = os.path.join(cfg_dir, filename)
            if os.path.exists(system_filepath) and \
                    (force or not os.path.exists(local_filepath)):
                shutil.copy(system_filepath, local_filepath)
    else:
        # Not necessary
        pass
        
#
#
# Constants and templates
#
#


MOCK_CFG_HEADER = '''
#!/usr/bin/python -tt
import os

config_opts['root'] = '$NAME'
config_opts['target_arch'] = '$ARCH'
config_opts['chroot_setup_cmd'] = 'install buildsys-build yum-priorities'
'''

MOCK_YUM_CONF = '''
config_opts['yum.conf'] = """
[main]
cachedir=/var/cache/yum
debuglevel=1
reposdir=/dev/null
logfile=/var/log/yum.log
retries=20
obsoletes=1
gpgcheck=0
assumeyes=1
# repos

[os]
name=os
mirrorlist=http://mirrorlist.centos.org/?release=5&arch=$BASEARCH&repo=os
#baseurl=http://mirror.centos.org/centos/5/os/$BASEARCH/

[updates]
name=updates
#mirrorlist=http://mirrorlist.centos.org/?release=5&arch=$BASEARCH&repo=updates
#baseurl=http://mirror.centos.org/centos/5/updates/$BASEARCH/
baseurl=http://mirror.unl.edu/centos/5/os/$BASEARCH/

[groups]
name=groups
baseurl=http://dev.centos.org/centos/buildsys/5/

[osg-development]
name=osg-development
#baseurl=http://vdt.cs.wisc.edu/repos/3.0/el5/development/$BASEARCH/
mirrorlist=http://repo.grid.iu.edu/mirror/osg-development/$BASEARCH
priority=98

[epel]
name=Extra Packages for Enterprise Linux 5 - $BASEARCH
#baseurl=http://download.fedoraproject.org/pub/epel/5/$BASEARCH
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=epel-5&arch=$BASEARCH

[jpackage-generic-5.0]
name=JPackage (free), generic
#baseurl=http://mirrors.dotsrc.org/jpackage/5.0/generic/free
mirrorlist=http://www.jpackage.org/mirrorlist.php?dist=generic&type=free&release=5.0
failovermethod=priority
gpgcheck=0
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-jpackage
enabled=1
priority=10

[jpackage-generic-5.0-updates]
name=JPackage (free), generic updates
#baseurl=http://mirrors.dotsrc.org/jpackage/5.0-updates/generic/free
mirrorlist=http://www.jpackage.org/mirrorlist.php?dist=generic&type=free&release=5.0-updates
failovermethod=priority
gpgcheck=0
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-jpackage
enabled=1
priority=10

[jpackage-generic-5.0-devel]
name=JPackage (free), generic
baseurl=http://mirrors.dotsrc.org/jpackage/5.0/generic/devel
failovermethod=priority
gpgcheck=0
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-jpackage
enabled=0
priority=10

[jpackage-distro]
name=JPackage (free) for distro $releasever
mirrorlist=http://www.jpackage.org/mirrorlist.php?dist=redhat-el-5&type=free&release=5.0
failovermethod=priority
gpgcheck=0
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-jpackage
enabled=1
priority=10

[osg-minefield]
name=OSG Development Repository on koji-hub
baseurl=http://koji-hub.batlab.org/mnt/koji/repos/el5-osg-development/latest/$basearch/
failovermethod=priority
gpgcheck=0
enabled=1
priority=98

"""
'''

OLD_MOCK_MACROS = '''
config_opts['macros'] = """
%_topdir /builddir/build
%_rpmfilename  %%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm

%dist    .$DIST
%centos_ver     5

#%_smp_mflags   -j1
"""
'''

NEW_MOCK_MACROS = '''
config_opts['macros'] = {
    '%_topdir': "/builddir/build",
    '%_rpmfilename': "%%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm",
    '%dist': ".$DIST",
    '%centos_ver': "5"}
'''

OLD_MOCK_CFG_TEMPLATE = string.Template(MOCK_CFG_HEADER + MOCK_YUM_CONF +
                                        OLD_MOCK_MACROS)

NEW_MOCK_CFG_TEMPLATE = string.Template(MOCK_CFG_HEADER + MOCK_YUM_CONF +
                                        NEW_MOCK_MACROS)


