"""koji interface classes for osg-build"""
# pylint: disable=W0614


import ConfigParser
import logging
import random
import re
import os
import time

from osgbuild.constants import *
from osgbuild import utils
from osgbuild.error import KojiError

log = logging.getLogger('osgbuild')
log.propagate = False

HAVE_KOJILIB = None
try:
    # Hack to load koji modules
    # This loads the koji libraries (koji/__init__.py) as kojilib, and the
    # script that is the koji cli (cli/koji or /usr/bin/koji) as kojicli
    import imp
    # UW CSL hack
    if os.path.isdir(CSL_KOJI_DIR):
        # explicitly import koji (as kojilib) from CSL_KOJI_DIR
        kojilib_filehandle, kojilib_filename, kojilib_desc = (
            imp.find_module('koji', [CSL_KOJI_DIR]))
        kojilib = imp.load_module('koji',
                                  kojilib_filehandle,
                                  kojilib_filename,
                                  kojilib_desc)
        # HAAACK
        kojicli_filename = os.path.join(CSL_KOJI_DIR, "cli", "koji")
    else:
        import koji as kojilib
        kojicli_filename = utils.which("koji")
    # load koji cli (as kojicli) from either somewhere in $PATH or CSL_KOJI_DIR/cli/koji
    # I can't use imp.find_module here to get the values I need because
    # /usr/bin/koji doesn't end in .py
    kojicli_filehandle = open(kojicli_filename)
    kojicli_desc = ('', kojicli_filehandle.mode, imp.PY_SOURCE)
    kojicli = imp.load_module('kojicli',
                              kojicli_filehandle,
                              kojicli_filename,
                              kojicli_desc)
    if kojilib.BR_STATES and kojilib.BUILD_STATES and kojilib.REPO_STATES and kojilib.TASK_STATES:
        HAVE_KOJILIB = True
    else:
        HAVE_KOJILIB = False
except ImportError:
    HAVE_KOJILIB = False
except AttributeError:
    HAVE_KOJILIB = False
    

def get_koji_cmd(use_osg_koji):
    """Get the command used to call koji."""
    # Use osg-koji wrapper if available and configured.
    if utils.which("osg-koji") and use_osg_koji:
        return ["osg-koji"]
    elif utils.which("koji"):
        # Not using osg-koji, so we need to find the conf file and do some
        # checks ourselves.
        conf_file = (utils.find_file(KOJI_CONF, DATA_FILE_SEARCH_PATH) or
                     utils.find_file(OLD_KOJI_CONF, DATA_FILE_SEARCH_PATH))
        if not conf_file:
            raise KojiError("Can't find %s or %s; search path was: %s" %
                            (KOJI_CONF,
                             OLD_KOJI_CONF,
                             os.pathsep.join(DATA_FILE_SEARCH_PATH)))

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


class KojiInter(object):
    """An interface around the koji cli"""
    backend = None

    def __init__(self, opts):
        self.no_wait = opts['no_wait']
        self.regen_repos = opts['regen_repos']
        self.scratch = opts['scratch']

        self.cn = opts['kojilogin'] or get_cn()
        if not self.cn:
            raise KojiError("""\
Unable to determine your Koji login. Either pass --kojilogin or verify that
'openssl x509 -in %s -noout -subject'
gives you a subject with a CN""" % KOJI_CLIENT_CERT)
    
        if KojiInter.backend is None:
            if HAVE_KOJILIB and opts.get('koji_backend') != 'shell':
                log.debug("KojiInter Using KojiLib backend")
                KojiInter.backend = KojiLibInter(self.cn, opts['dry_run'])
                KojiInter.backend.read_config_file()
                KojiInter.backend.init_koji_session()
            elif not HAVE_KOJILIB and opts['koji_backend'] == 'kojilib':
                raise KojiError("KojiLib backend requested, but can't import it!")
            else:
                log.debug("KojiInter Using shell backend")
                KojiInter.backend = KojiShellInter(self.cn, opts['dry_run'],
                                                   opts['koji_wrapper'])

        self.target = opts['koji_target']
        self.build_tag, self.dest_tag = KojiInter.backend.get_build_and_dest_tags(self.target)
        if opts['koji_tag'] == 'TARGET':
            self.tag = self.dest_tag
        else:
            self.tag = opts['koji_tag']



    def add_pkg(self, package_name):
        """Part of koji task. If the package needs to be added to koji_tag,
        do so.

        """
        return KojiInter.backend.add_pkg(self.tag, package_name)


    def build_srpm(self, srpm):
        """Submit an SRPM build"""
        return KojiInter.backend.build_srpm(srpm, self.target, self.scratch, regen_repos=self.regen_repos, no_wait=self.no_wait)

    
    def build_svn(self, url, rev):
        """Submit an SVN build"""
        return KojiInter.backend.build("svn+" + url + "#" + rev, self.target, self.scratch, regen_repos=self.regen_repos, no_wait=self.no_wait)
    

    def mock_config(self, arch, tag, dist, outpath, name):
        """Request a mock config from koji-hub"""
        return KojiInter.backend.mock_config(arch, tag, dist, outpath, name)
# end of class KojiInter


class KojiShellInter(object):
    """An interface to doing koji tasks via invoking the koji cli through
    the shell.

    """
    def __init__(self, user=None, dry_run=False, koji_wrapper=False):
        self.user = user or get_cn()
        self.koji_cmd = get_koji_cmd(koji_wrapper)
        self.dry_run = dry_run

    def add_pkg(self, tag, package, owner=None):
        if owner is None:
            owner = self.user

        found = False
        list_pkgs = utils.backtick(self.koji_cmd +
                                   ["list-pkgs", "--package", package])
        for line in list_pkgs.split("\n"):
            fields = re.split(r"\s*", line, 2)
            try:
                if fields[1] == tag:
                    found = True
            except IndexError:
                pass

        if not found:
            cmd = (self.koji_cmd +
                   ["add-pkg", tag, package, "--owner", owner])
            log.info("Calling koji to add the package to tag %s", tag)
            if not self.dry_run:
                utils.checked_call(cmd)
            else:
                print " ".join(cmd)
    
    def get_build_and_dest_tags(self, target):
        """Return the build and destination tags for the current target."""
        line = utils.checked_backtick(
            self.koji_cmd +
            ["-q", "list-targets", "--name", target])
        if not line:
            raise KojiError("Unable to find koji target with the name " +
                            target)
        else:
            try:
                fields = re.split(r"\s*", line, 2)
                target_build_tag = fields[1]
                target_dest_tag = fields[2]
            except IndexError:
                raise KojiError("Unable to determine koji tags from target")
        return (target_build_tag, target_dest_tag)


    def build(self, url, target, scratch=False, **kwargs):
        """build package at url for target.

        Using **kwargs so signature is same as KojiLibInter.build.
        kwargs recognized: no_wait, regen_repos

        """
        log.debug("building " + url)
        no_wait = kwargs.get('no_wait', False)
        regen_repos = kwargs.get('regen_repos', False)
        build_subcmd = ["build", target, url]
        if scratch:
            build_subcmd += ["--scratch"]
        if no_wait:
            build_subcmd += ["--nowait"]
        log.info("Calling koji to build the package for target %s", target)

        if not self.dry_run:
            err = utils.unchecked_call(self.koji_cmd + build_subcmd)
        else:
            print " ".join(self.koji_cmd + build_subcmd)
            err = 0

        if err:
            raise KojiError("koji build failed with exit code " + str(err))
        if regen_repos and not scratch:
            build_tag = self.get_build_and_dest_tags(target)[0]
            regen_repo_subcmd = ["regen-repo", build_tag]
            if no_wait:
                regen_repo_subcmd += ["--nowait"]
            log.info("Calling koji to regen " + build_tag)
            if not self.dry_run:
                err2 = utils.unchecked_call(self.koji_cmd + regen_repo_subcmd)
            else:
                print " ".join(self.koji_cmd + regen_repo_subcmd)
                err2 = 0
            if err2:
                raise KojiError("koji regen-repo failed with exit code "
                                + str(err2))

        
    def build_srpm(self, srpm, target, scratch=False, **kwargs):
        """Submit an SRPM build"""
        return self.build(srpm, target, scratch, **kwargs)

        
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


    def tag_build(self, tag, build, force=False):
        tag_pkg_subcmd = ["tag-pkg",
                          tag,
                          build]
        if force:
            tag_pkg_subcmd.append("--force")
        err = utils.unchecked_call(self.koji_cmd + tag_pkg_subcmd)
        if err:
            raise KojiError("koji tag-pkg failed with exit code " +
                            str(err))

    def watch_tasks(self, *args):
        pass


if HAVE_KOJILIB:
    # HACK
    # Create an object that has an instance variable named poll_interval.
    # kojicli.watch_tasks() expects a global variable named options with
    # an attribute poll_interval to determine how often to poll the server
    # for a status update.
    class _KojiCliOptions(object):
        def __init__(self, poll_interval):
            self.poll_interval = poll_interval
    kojicli.options = _KojiCliOptions(5)

class KojiLibInter(object):
    # Aliasing for convenience
    if HAVE_KOJILIB:
        BR_STATES = kojilib.BR_STATES
        BUILD_STATES = kojilib.BUILD_STATES
        REPO_STATES = kojilib.REPO_STATES
        TASK_STATES = kojilib.TASK_STATES

    def __init__(self, user=None, dry_run=False):
        if not HAVE_KOJILIB:
            raise KojiError("Cannot use KojiLibInter without kojilib!")

        self.ca = None
        self.cert = KOJI_CLIENT_CERT
        self.kojisession = None
        self.server = os.path.join(KOJI_HUB, "kojihub")
        self.serverca = None
        self.user = user or get_cn()
        self.weburl = os.path.join(KOJI_HUB, "koji")
        self.dry_run = dry_run


    def read_config_file(self, config_file=None):
        if not config_file:
            config_file = (
                utils.find_file('config',
                                [OSG_KOJI_USER_CONFIG_DIR,
                                 KOJI_USER_CONFIG_DIR]) or
                utils.find_file(KOJI_CONF, DATA_FILE_SEARCH_PATH) or
                utils.find_file(OLD_KOJI_CONF, DATA_FILE_SEARCH_PATH))
        if not config_file or not os.path.isfile(config_file):
            raise KojiError("Can't find koji config file.")
        try:
            cfg = ConfigParser.ConfigParser()
            cfg.read(config_file)
            items = dict(cfg.items('koji'))
        except ConfigParser.Error, err:
            raise KojiError("Can't read config file from %s: %s" %
                            (config_file, str(err)))
        for var in ['ca', 'cert', 'server', 'serverca', 'weburl']:
            if items.get(var):
                setattr(self, var, os.path.expanduser(items[var]))


    def init_koji_session(self, login=True):
        print "Initializing koji session to", self.server
        self.kojisession = kojilib.ClientSession(self.server,
                                                 {'user': self.user})
        if login and not self.dry_run:
            print "Logging in to koji as", self.user
            try:
                self.kojisession.ssl_login(self.cert, self.ca, self.serverca)
            except Exception, err:
                raise KojiError("Couldn't do ssl_login: " + str(err))
            if not self.kojisession.logged_in:
                raise KojiError("Couldn't log in to koji for unknown reason")


    def add_pkg(self, tag, package, owner=None):
        if owner is None:
            owner = self.user
        tag_obj = self.kojisession.getTag(tag)
        if not tag_obj:
            raise KojiError("Invalid tag %s", tag)
        try:
            package_list = self.kojisession.listPackages(tagID=tag_obj['id'], pkgID=package)
        except kojilib.GenericError, e: # koji raises this if the package doesn't exist
            package_list = None
        if not package_list:
            if not self.dry_run:
                return self.kojisession.packageListAdd(tag, package, owner) # TODO Handle errors.
            else:
                log.info("kojisession.packageListAdd(%r, %r, %r)", tag, package, owner)
                


    def build(self, url, target, scratch=False, **kwargs):
        """build package at url for target.

        Using **kwargs so signature is same as KojiShellInter.build.
        kwargs recognized: priority

        """
        opts = { 'scratch': scratch }
        if not self.dry_run:
            return self.kojisession.build(url, target, opts, kwargs.get('priority'))
        else:
            log.info("kojisession.build(%r, %r, %r, %r)", url, target, opts, kwargs.get('priority'))


    def build_srpm(self, srpm, target, scratch=False, **kwargs):
        return self.build(self.upload(srpm),
                          target,
                          scratch=scratch,
                          **kwargs)


    def mock_config(self, arch, tag, dist, outpath, name):
        tag_obj = self.kojisession.getTag(tag)
        if not tag_obj:
            raise KojiError("Invalid tag %s", tag)
        config = self.kojisession.getBuildConfig(tag_obj['id'])
        if not config:
            raise KojiError("Couldn't get config for tag %s", tag)
        repo = self.kojisession.getRepo(config['id'])
        if not repo:
            raise KojiError("Couldn't get repo for tag %s", tag)
        opts = {'tag_name': tag_obj['name'],
                'repoid': repo['id'],
                'distribution': dist}
        output = kojilib.getMockConfig(name, arch, **opts)
        utils.unslurp(outpath, output)


    def search(self, terms, stype, match):
        return self.kojisession.search(terms, stype, match)


    def tag_build(self, tag, build, force=False):
        return self.kojisession.tagBuild(tag, build, force)


    def upload(self, source):
        "Upload a file to koji. Return the relative remote path."
        serverdir = self._unique_path()
        if not self.dry_run:
            self.kojisession.uploadWrapper(source, serverdir, callback=None)
        return os.path.join(serverdir, os.path.basename(source))


    def _unique_path(self, prefix="cli-build"):
        return kojicli._unique_path(prefix)


    def get_build_and_dest_tags(self, target):
        """Return the build and destination tags for target."""
        info = self.kojisession.getBuildTargets(target) # TESTME
        if not info:
            raise KojiError("Couldn't get info for target %s" % target)
        return (info[0]['build_tag_name'], info[0]['dest_tag_name'])

    
    def regen_repo(self, tag):
        """Regenerate a repo"""
        if not self.dry_run:
            return self.kojisession.newRepo(tag)
        else:
            log.info("self.kojisession.newRepo(%r)" % tag)


    def watch_tasks(self, tasks):
        return kojicli.watch_tasks(self.kojisession, tasks)


# end of class KojiLibInter
