import string
WD_RESULTS = '_build_results'
WD_PREBUILD = '_final_srpm_contents'
WD_UNPACKED = '_upstream_srpm_contents'
WD_UNPACKED_TARBALL = '_upstream_tarball_contents'
AFS_CACHE_PATH = '/p/vdt/public/html/upstream'
AFS_CACHE_PREFIX = 'file://' + AFS_CACHE_PATH
WEB_CACHE_PREFIX = 'http://vdt.cs.wisc.edu/upstream'
DEFAULT_CONFIG_FILE = '~/.vdt-build.ini'

CMDFILE_TEMPLATE = string.Template("""
component           = $NAME
component_version   = $VERSION-$RELEASE
description         = $NAME $VERSION-$RELEASE RPM build
inputs              = glue.scp, srpm.scp
notify              = $NOTIFY
platform_post       = glue/platform-post.py
platform_post_args  = " $PLATFORM_POST_ARGS "
platforms           = x86_64_rhap_5, x86_rhap_5
project             = VDT
project_release     = 3.0
remote_declare      = glue/remote-declare.py
remote_declare_args = rebuild_i386 rebuild_x86_64 package
remote_task         = glue/remote-task.py
run_type            = build
#append_requirements = (Machine =?= 'mock-1.batlab.org')
#append_requirements = (Machine =?= 'nmi-0104.batlab.cs.wisc.edu')
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

#MOCK_CFG_TEMPLATE = string.Template('''
##!/usr/bin/python -tt
#import os
#config_opts['root'] = '$NAME'
#config_opts['target_arch'] = '$ARCH'
#config_opts['chroot_setup_cmd'] = 'install buildsys-build yum-priorities rpm-build'
#
#config_opts['yum.conf'] = """
#[main]
#cachedir=/var/cache/yum
#debuglevel=1
#logfile=/var/log/yum.log
#reposdir=/dev/null
#retries=20
#obsoletes=1
#gpgcheck=0
#assumeyes=1
#
## repos
#
#[sl-base]
#name=SL 5 Base
#baseurl=http://ftp.scientificlinux.org/linux/scientific/55/$basearch/SL
#        http://ftp1.scientificlinux.org/linux/scientific/55/$basearch/SL
#        http://ftp2.scientificlinux.org/linux/scientific/55/$basearch/SL
#        ftp://ftp.scientificlinux.org/linux/scientific/55/$basearch/SL
#
#[sl-security]
#name=SL 5 security updates
#baseurl=http://ftp.scientificlinux.org/linux/scientific/55/$basearch/updates/security
#        http://ftp1.scientificlinux.org/linux/scientific/55/$basearch/updates/security
#        http://ftp2.scientificlinux.org/linux/scientific/55/$basearch/updates/security
#        ftp://ftp.scientificlinux.org/linux/scientific/55/$basearch/updates/security
#
#[vdt]
#name=vdt
#baseurl=http://vdt.cs.wisc.edu/repos/3.0/el5/development/$basearch/
#priority=98
#
#[epel]
#name=Extra Packages for Enterprise Linux 5 - $basearch
##baseurl=http://download.fedoraproject.org/pub/epel/5/$basearch
#mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=epel-5&arch=$basearch
#"""
#
#config_opts['macros'] = """
#%_topdir /builddir/build
#%_rpmfilename  %%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm
#
## please change this to reflect the Distro Tree and Repo hosting packages!
#%dist    .vdt
#
#"""
#''')

MOCK_CFG_TEMPLATE = string.Template('''
#!/usr/bin/python -tt
import os

config_opts['root'] = '$NAME'
config_opts['target_arch'] = '$ARCH'
config_opts['chroot_setup_cmd'] = 'install buildsys-build yum-priorities'

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
#exclude=[ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefhijklmnopqrstuvwxyz]*.i*86 g[abcdefghijkmnopqrstuvwxyz]*.i?86 glib2.i?86 glib.i?86 *-devel.i?86
# repos

[os]
name=os
mirrorlist=http://mirrorlist.centos.org/?release=5&arch=$basearch&repo=os
#baseurl=http://mirror.centos.org/centos/5/os/$basearch/

[updates]
name=updates
#mirrorlist=http://mirrorlist.centos.org/?release=5&arch=$basearch&repo=updates
#baseurl=http://mirror.centos.org/centos/5/updates/$basearch/
baseurl=http://mirror.unl.edu/centos/5/os/$basearch/

[groups]
name=groups
baseurl=http://dev.centos.org/centos/buildsys/5/

[vdt]
name=vdt
baseurl=http://vdt.cs.wisc.edu/repos/3.0/el5/development/$basearch/
priority=98

[epel]
name=Extra Packages for Enterprise Linux 5 - $basearch
#baseurl=http://download.fedoraproject.org/pub/epel/5/$basearch
mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=epel-5&arch=$basearch

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

"""


config_opts['macros'] = """
%_topdir /builddir/build
%_rpmfilename  %%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm

# Change the next two lines to reflect yourself.

#%packager  YourName <YourEmail@server.com>
#%vendor   
#%distribution 

# please change this to reflect the Distro Tree and Repo hosting packages!
%dist    .vdt
%centos_ver     5

#%_smp_mflags   -j1

"""

''')
