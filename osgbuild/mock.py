"""mock wrapper class and functions for osg-build"""
# pylint: disable=W0614
from __future__ import absolute_import
from fnmatch import fnmatch
from glob import glob
import atexit
import grp
import os
import re
import shutil
import string
import tempfile

from .constants import *
from .error import MockError, OSGBuildError
from . import utils




def make_mock_config_from_koji(koji_obj, arch, cfg_path, tag, dist):
    """Request a mock config from the koji hub"""
    cfg_abspath = os.path.abspath(cfg_path)
    cfg_name = re.sub(r'\.cfg$', '', os.path.basename(cfg_abspath))

    koji_obj.mock_config(arch, tag, dist, cfg_abspath, cfg_name)

    return cfg_abspath


class Mock(object):
    """A wrapper class around mock"""

    def __init__(self, buildopts, koji_obj):
        self.buildopts = buildopts
        self.koji_obj = koji_obj

        cfg_path = self._init_get_cfg_path()
        self.mock_cmd = ['mock']
        mock_version_str = utils.backtick(self.mock_cmd + ["--version"]).strip()
        mm = re.match(r"\d+(?:\.\d+)*", mock_version_str)
        if mm:
            try:
                self.mock_version = tuple(int(it) for it in mm.group(0).split("."))
            except TypeError:
                # this shouldn't happen
                raise MockError("mock --version returned unexpected output: %s" % mock_version_str)
        else:
            raise MockError("mock --version returned unexpected output: %s" % mock_version_str)

        if cfg_path:
            cfg_abspath = os.path.abspath(cfg_path)
            cfg_abspath_no_ext = re.sub(r'\.cfg$', '', cfg_abspath)

            if not os.path.isfile(cfg_abspath):
                raise MockError("Couldn't find mock config file at " + cfg_abspath)

            # The cfg file passed to mock is always relative to /etc/mock
            self.mock_cmd += ['-r', "../../" + cfg_abspath_no_ext]

        self.target_arch = buildopts['target_arch']

        try:
            mock_gid = grp.getgrnam('mock').gr_gid
        except KeyError:
            raise MockError("The mock group does not exist on this system!")
        if mock_gid not in os.getgroups():
            raise MockError(
"""You are not able to do a mock build on this machine because you are not in the mock group.
/etc/group must be edited and your username must be added to the mock group.
You might need to log out and log in for the changes to take effect""")
    # end of __init__()


    def _init_get_cfg_path(self):
        """Find the appropriate configuration to use for mock based on 
        options and make a Mock object with it.

        """
        distro_tag = self.buildopts['distro_tag']
        mock_config = self.buildopts['mock_config']
        mock_config_from_koji = self.buildopts['mock_config_from_koji']
        target_arch = self.buildopts['target_arch']

        machine_arch = os.uname()[4]
        # the "or ''" part is in case target_arch is None
        if re.search("i[3-6]86", target_arch or ''):
            arch = 'i386'
        elif (re.search("x86_64", target_arch or '') and
              not re.search("x86_64", machine_arch)):
            raise OSGBuildError("Can't do 64-bit build on 32-bit machine")
        else:
            arch = machine_arch

        if mock_config:
            # mock is very particular with its config file
            # names. The path we pass it is interpreted to be
            # relative to '/etc/mock', and mock will append '.cfg'
            # to the end of the config file name.  So the argument
            # to --mock-config can be interpreted in the usual way
            # (as a file name with either an absolute path or path
            # relative to the cwd), or it can be interpreted in
            # the way mock does it. Figure out which the user
            # meant (by seeing which interpretation exists) and
            # translate it to what mock wants.
            if not mock_config.endswith(".cfg"):
                given_cfg_path = mock_config + ".cfg"
            else:
                given_cfg_path = mock_config

            if given_cfg_path.startswith('/'):
                # Absolute path
                cfg_path = given_cfg_path
            else:
                # Relative path. Can be relative to cwd or
                # /etc/mock. Prefer cwd.
                given_cfg_dir, given_cfg_file = os.path.split(given_cfg_path)
                cfg_dir1 = os.path.abspath(given_cfg_dir)
                cfg_dir2 = os.path.abspath(os.path.join('/etc/mock', given_cfg_dir))
                cfg_path = utils.find_file(given_cfg_file, [cfg_dir1, cfg_dir2])

        elif mock_config_from_koji:
            cfg_dir = tempfile.mkdtemp(prefix="osg-build-mock-")
            atexit.register(shutil.rmtree, cfg_dir)
            cfg_path = make_mock_config_from_koji(
                self.koji_obj,
                arch,
                os.path.join(cfg_dir,"mock-koji-%s-%s.%d.cfg" % (mock_config_from_koji, arch, os.getuid())),
                mock_config_from_koji,
                distro_tag)
        else:
            cfg_path = None
        # end if

        return cfg_path
    # end of _init_get_cfg_path()

    def rebuild(self, resultdir, srpm):
        """Use mock to build RPMs from an SRPM"""
        rebuild_cmd = self.mock_cmd + ['--resultdir',
                                       resultdir,
                                       '--no-cleanup-after',
                                       'rebuild',
                                       srpm]
        if self.target_arch:
            rebuild_cmd += ['--arch', self.target_arch]
        if self.mock_version >= (1,4,0):
            # systemd-nspawn is often broken; don't use it. network is required for maven builds :(
            rebuild_cmd += ['--enable-network', '--config-opts=use_nspawn=False']
        else:
            # ccache on old versions tries to install the el5 package for ccache and dies
            rebuild_cmd += ['--disable-plugin=ccache']
        ret = utils.unchecked_call(rebuild_cmd)
        if ret:
            raise MockError('Mock build failed (command was: ' + ' '.join(rebuild_cmd) + ')')

        rpms = [x for x in glob(os.path.join(resultdir, "*.rpm")) if not fnmatch(x, "*.src.rpm")]

        return rpms


    def clean(self):
        """Clean the mock chroot"""
        utils.checked_call(self.mock_cmd + ["clean"])
# end of Mock
