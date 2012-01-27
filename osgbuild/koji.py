"""koji wrapper class for osg-build"""
# pylint: disable=W0614
import logging
import re
import os

from osgbuild.constants import *
from osgbuild import utils
from osgbuild.error import KojiError

def get_koji_cmd(koji_wrapper):
    """Get the command used to call koji."""
    # Use osg-koji wrapper if available and configured.
    if utils.which("osg-koji") and koji_wrapper:
        return ["osg-koji"]
    elif utils.which("koji"):
        # Not using osg-koji, so we need to find the conf file and do some
        # checks ourselves.
        conf_file = (utils.find_file(KOJI_CONF, DATA_FILE_SEARCH_PATH) or
                     utils.find_file(OLD_KOJI_CONF, DATA_FILE_SEARCH_PATH))
        if not conf_file:
            raise KojiError("Can't find " +
                            KOJI_CONF +
                            " or " +
                            OLD_KOJI_CONF +
                            "; search path was:\n" +
                            os.pathsep.join(DATA_FILE_SEARCH_PATH))

        if not os.path.exists(KOJI_CLIENT_CERT):
            raise KojiError("Unable to find your Koji client cert at "
                            + KOJI_CLIENT_CERT)

        return ["koji", "--config", conf_file, "--authtype", "ssl"]
    else:
        raise KojiError("Can't find koji or osg-koji!")


def get_cn():
    """Return the user's koji login (their CN, unless otherwise specified
    on the command line.

    """
    subject = utils.checked_backtick("openssl x509 -in '%s' -noout -subject"
                                     " -nameopt multiline" % KOJI_CLIENT_CERT)
    # Get the last commonName
    cn_match = re.search(r"""(?xms)
        ^ \s* commonName \s* = \s* ([^\n]+) \s* $
        (?!.*commonName)""", subject)

    if cn_match:
        return cn_match.group(1)
    else:
        return None


class Koji(object):
    """A wrapper around the koji cli"""

    def __init__(self, opts):
        self.no_wait = opts['no_wait']
        self.regen_repos = opts['regen_repos']
        self.scratch = opts['scratch']

        self.koji_cmd = get_koji_cmd(opts['koji_wrapper'])

        self.cn = opts['kojilogin'] or get_cn()
        if not self.cn:
            raise KojiError(
"""Unable to determine your Koji login. Either pass --kojilogin or verify that
'openssl x509 -in %s -noout -subject'
gives you a subject with a CN""" % KOJI_CLIENT_CERT)
    
        self.target = opts['koji_target']
        self.build_tag, self.dest_tag = self._get_build_and_dest_tags()
        if opts['koji_tag'] == 'TARGET':
            self.tag = self.dest_tag
        else:
            self.tag = opts['koji_tag']


    def add_pkg(self, package_name):
        """Part of koji task. If the package needs to be added to koji_tag,
        do so.

        """
        # See if the package needs to be added
        found = False
        list_pkgs = utils.backtick(self.koji_cmd +
                                   ["list-pkgs", "--package", package_name])
        for line in list_pkgs.split("\n"):
            fields = re.split(r"\s*", line, 2)
            try:
                if fields[1] == self.tag:
                    found = True
            except IndexError:
                pass

        if not found:
            logging.info("Calling koji to add the package")
            utils.checked_call(
                self.koji_cmd +
                ["add-pkg", self.tag, package_name, "--owner", self.cn])


    def _get_build_and_dest_tags(self):
        """Return the build and destination tags for the current target."""
        line = utils.checked_backtick(
            self.koji_cmd +
            ["-q", "list-targets", "--name", self.target])
        if not line:
            raise KojiError("Unable to find koji target with the name " +
                            self.target)
        else:
            try:
                fields = re.split(r"\s*", line, 2)
                target_build_tag = fields[1]
                target_dest_tag = fields[2]
            except IndexError:
                raise KojiError("Unable to determine koji tags from target")
        return (target_build_tag, target_dest_tag)


    def _build_common(self, url):
        """Submit a build"""
        logging.debug("building " + url)
        build_subcmd = ["build", self.target, url]
        if self.scratch:
            build_subcmd += ["--scratch"]
        if self.no_wait:
            build_subcmd += ["--nowait"]
        logging.info("Calling koji to build the package")
        err = utils.unchecked_call(self.koji_cmd + build_subcmd)
        if err:
            raise KojiError("koji build failed with exit code " + str(err))
        if self.regen_repos and not self.scratch:
            regen_repo_subcmd = ["regen-repo", self.build_tag]
            if self.no_wait:
                regen_repo_subcmd += ["--nowait"]
            logging.info("Calling koji to regen " + self.build_tag)
            err2 = utils.unchecked_call(self.koji_cmd + regen_repo_subcmd)
            if err2:
                raise KojiError("koji regen-repo failed with exit code "
                                + str(err2))


    def build_srpm(self, srpm):
        """Submit an SRPM build"""
        return self._build_common(srpm)

    
    def build_svn(self, url, rev):
        """Submit an SVN build"""
        return self._build_common("svn+" + url + "#" + rev)
    

    def mock_config(self, arch, tag, dist, outpath, name):
        """Request a mock config from koji-hub"""
        mock_config_subcmd = ["mock-config",
                              "--arch=" + arch,
                              "--tag=" + tag,
                              "--distribution=" + dist,
                              "--topurl=" + KOJI_HUB + "/mnt/koji",
                              "-o",
                              outpath,
                              name]
        
        err = utils.unchecked_call(self.koji_cmd + mock_config_subcmd)
        if err:
            raise KojiError("koji mock-config failed with exit code " +
                            str(err))
# end of class Koji

