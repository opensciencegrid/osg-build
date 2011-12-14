#!/usr/bin/python
"""mock wrapper class and functions for osg-build"""
from fnmatch import fnmatch
from glob import glob
import grp
import os
import re
import shutil
import string
import subprocess
import sys

from osg_build_lib.error import MockError
from osg_build_lib.utils import checked_call, sbacktick, unchecked_call, unslurp


def get_mock_version():
    """Return mock version as a 2-element tuple (major, minor)"""
    query, ret = sbacktick("rpm -q mock")
    match = re.match(r'''mock-((?:\d+\.?)+)-''', query)
    if ret != 0 or not match:
        print >> sys.stderr,"Unable to determine the mock version"
        print >> sys.stderr,"Make sure mock is installed (yum install mock)"
        raise MockError(query)
    version = [int(x) for x in match.group(1).split(".")]
    return tuple(version)


def make_mock_config(arch, cfg_path, dist):
    """Autogenerate a mock config for arch 'arch'."""
    if re.match(r'i[3-6]86', arch):
        basearch = 'i386'
    else:
        basearch = arch
    
    cfg_abspath = os.path.abspath(cfg_path)
    cfg_name = re.sub(r'\.cfg$', '', os.path.basename(cfg_abspath))
    #cfg_dir = os.path.dirname(cfg_abspath)

    mockver = get_mock_version()
    if mockver < (0, 8):
        template = OLD_MOCK_CFG_TEMPLATE
    else:
        template = NEW_MOCK_CFG_TEMPLATE

    unslurp(cfg_abspath,
            template.safe_substitute(
                NAME=cfg_name,
                ARCH=arch,
                BASEARCH=basearch,
                DIST=dist))
    
    #if mockver >= (0, 8):
    #    link_mock_extra_config_files(cfg_dir)

    return cfg_abspath


def make_mock_config_from_koji(koji_obj, arch, cfg_path, tag, dist):
    mockver = get_mock_version()
    if mockver < (0, 8):
        raise MockError("Mock version too old to use a mock config from a koji buildroot. Needs to be at least 0.8")

    cfg_abspath = os.path.abspath(cfg_path)
    cfg_name = re.sub(r'\.cfg$', '', os.path.basename(cfg_abspath))
    #cfg_dir = os.path.dirname(cfg_abspath)

    koji_obj.mock_config(arch, tag, dist, cfg_abspath, cfg_name)

    #link_mock_extra_config_files(cfg_dir)

    return cfg_abspath


def link_mock_extra_config_files(cfg_dir):
    for filename in ['site-defaults.cfg', 'logging.ini']:
        system_filepath = os.path.join("/etc/mock", filename)
        local_filepath = os.path.join(cfg_dir, filename)
        if os.path.exists(system_filepath) and not os.path.exists(local_filepath):
            os.symlink(system_filepath, local_filepath)


class Mock(object):

    def __init__(self, cfg_path=None, target_arch=None):
        self.mock_cmd = ['mock']
        if cfg_path:
            cfg_abspath = os.path.abspath(cfg_path)
            cfg_abspath_no_ext = re.sub(r'\.cfg$', '', cfg_abspath)
            #self.cfg_dir = os.path.dirname(cfg_abspath_no_ext)
            self.cfg_name = os.path.basename(cfg_abspath_no_ext)

            if not os.path.isfile(cfg_abspath):
                raise MockError("Couldn't find mock config file at " + cfg_abspath)

            #self.mock_cmd += ['--configdir', self.cfg_dir, '-r', self.cfg_name]
            # The cfg file passed to mock is always relative to /etc/mock
            self.mock_cmd += ['-r', "../../"+cfg_abspath_no_ext]
        else:
            #self.cfg_dir = None
            self.cfg_name = None

        self.target_arch = target_arch

        try:
            mock_gid = grp.getgrnam('mock').gr_gid
        except KeyError:
            raise MockError("The mock group does not exist on this system!")
        if mock_gid not in os.getgroups():
            raise MockError(
"""You are not able to do a mock build on this machine because you are not in the mock group.
/etc/group must be edited and your username must be added to the mock group.
You might need to log out and log in for the changes to take effect""")


    def rebuild(self, resultdir, srpm, extra_opts=None):
        rebuild_cmd = self.mock_cmd + ['--resultdir',
                                       resultdir,
                                       '--no-cleanup-after',
                                       'rebuild',
                                       srpm]
        if self.target_arch:
            rebuild_cmd += ['--arch', self.target_arch]

        ret = unchecked_call(rebuild_cmd)
        if ret:
            raise MockError('Mock build failed (command was: ' +
                                ' '.join(rebuild_cmd) + ')')
        
        # TODO: Parse the mock logs/output instead of using glob.
        rpms = [x for x in glob(os.path.join(resultdir, "*.rpm"))
                if not fnmatch(x, "*.src.rpm")]

        return rpms


    def clean(self):
        checked_call(self.mock_cmd + ["clean"])

        
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

%dist           .$DIST
%centos_ver     5
%rhel           5

#%_smp_mflags   -j1
"""
'''

NEW_MOCK_MACROS = '''
config_opts['macros'] = {
    '%_topdir': "/builddir/build",
    '%_rpmfilename': "%%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm",
    '%dist': ".$DIST",
    '%centos_ver': "5",
    '%rhel': '5',}
'''

OLD_MOCK_CFG_TEMPLATE = string.Template(MOCK_CFG_HEADER + MOCK_YUM_CONF +
                                        OLD_MOCK_MACROS)

NEW_MOCK_CFG_TEMPLATE = string.Template(MOCK_CFG_HEADER + MOCK_YUM_CONF +
                                        NEW_MOCK_MACROS)


