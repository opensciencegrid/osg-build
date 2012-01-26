#!/usr/bin/python
"""koji wrapper class for osg-build"""
import logging
import re
import os

from osg_build_lib.constants import (
    DATA_FILE_SEARCH_PATH,
    KOJI_CLIENT_CERT,
    KOJI_CONF,
    KOJI_HUB,
    OLD_KOJI_CONF)
from osg_build_lib.utils import (
    backtick,
    checked_backtick,
    checked_call,
    find_file,
    unchecked_call,
    which)
from osg_build_lib.error import KojiError

def get_koji_cmd(koji_wrapper):
    # Use osg-koji wrapper if available and configured.
    if which("osg-koji") and koji_wrapper:
        return ["osg-koji"]
    elif which("koji"):
        # Not using osg-koji, so we need to find the conf file and do some
        # checks ourselves.
        conf_file = (find_file(KOJI_CONF, DATA_FILE_SEARCH_PATH) or
                     find_file(OLD_KOJI_CONF, DATA_FILE_SEARCH_PATH))
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
    subject = checked_backtick("openssl x509 -in '%s' -noout -subject"
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

    def __init__(self, koji_wrapper=True, kojilogin=None, no_wait=False, regen_repos=False, scratch=False):
        self.no_wait = no_wait
        self.regen_repos = regen_repos
        self.scratch = scratch

        self.koji_cmd = get_koji_cmd(koji_wrapper)

        self.cn = kojilogin or get_cn()
        if not self.cn:
            raise KojiError(
"""Unable to determine your Koji login. Either pass --kojilogin or verify that
'openssl x509 -in %s -noout -subject'
gives you a subject with a CN""" % KOJI_CLIENT_CERT)


    def add_pkg(self, koji_tag, package_name):
        """Part of koji task. If the package needs to be added to koji_tag,
        do so.

        """
        # See if the package needs to be added
        found = False
        list_pkgs = backtick(self.koji_cmd + ["list-pkgs", "--package", package_name])
        for line in list_pkgs.split("\n"):
            fields = re.split(r"\s*", line, 2)
            try:
                if fields[1] == koji_tag:
                    found = True
            except IndexError:
                pass

        if not found:
            logging.info("Calling koji to add the package")
            checked_call(
                self.koji_cmd +
                ["add-pkg", koji_tag, package_name, "--owner", self.cn])


    def get_build_and_dest_tags(self, koji_target):
        line = checked_backtick(self.koji_cmd + ["-q", "list-targets", "--name", koji_target])
        if not line:
            raise KojiError("Unable to find koji target with the name " + koji_target)
        else:
            try:
                fields = re.split(r"\s*", line, 2)
                target_build_tag = fields[1]
                target_dest_tag = fields[2]
            except IndexError:
                raise KojiError("Unable to determine koji tags from koji target")
        return (target_build_tag, target_dest_tag)


    def build_common(self, koji_target, url):
        logging.debug("building " + url)
        build_subcmd = ["build", koji_target, url]
        if self.scratch:
            build_subcmd += ["--scratch"]
        if self.no_wait:
            build_subcmd += ["--nowait"]
        logging.info("Calling koji to build the package")
        err = unchecked_call(self.koji_cmd + build_subcmd)
        if err:
            raise KojiError("koji build failed with exit code " + str(err))
        if self.regen_repos and not self.scratch:
            target_build_tag, _ = (
                self.get_build_and_dest_tags(koji_target))
            regen_repo_subcmd = ["regen-repo", target_build_tag]
            if self.no_wait:
                regen_repo_subcmd += ["--nowait"]
            logging.info("Calling koji to regen " + target_build_tag)
            err2 = unchecked_call(self.koji_cmd + regen_repo_subcmd)
            if err2:
                raise KojiError("koji regen-repo failed with exit code "
                                + str(err2))


    def build_srpm(self, koji_target, srpm):
        return self.build_common(koji_target, srpm)

    
    def build_svn(self, koji_target, url, rev):
        return self.build_common(koji_target, "svn+" + url + "#" + rev)
    

    def mock_config(self, arch, tag, dist, outpath, name):
        mock_config_subcmd = ["mock-config",
                              "--arch=" + arch,
                              "--tag=" + tag,
                              "--distribution=" + dist,
                              "--topurl=" + KOJI_HUB + "/mnt/koji",
                              "-o",
                              outpath,
                              name]
        
        err = unchecked_call(self.koji_cmd + mock_config_subcmd)
        if err:
            raise KojiError("koji mock-config failed with exit code " +
                            str(err))

