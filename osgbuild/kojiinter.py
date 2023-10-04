"""koji interface classes for osg-build"""
# pylint: disable=W0614,C0103


import configparser
import json
import logging
import random
import re
import os
import string
import sys
import time
import urllib
import urllib.request, urllib.error
from typing import Optional

from .constants import *
from . import clientcert
from . import utils
from .error import KojiError, type_of_error

log = logging.getLogger(__name__)

HAVE_KOJILIB = None
try:
    import koji as kojilib
    from koji_cli import lib as kojicli
    HAVE_KOJILIB = True
except (ImportError, AttributeError):
    HAVE_KOJILIB = False

# TODO: replace with @functools.lru_cache() once we drop Python 2

__koji_config_file = None
__koji_config = None


def get_koji_config_file():
    # type: () -> str
    """Return the path to the koji config file; raise KojiError if no such file exists."""
    global __koji_config_file

    if not __koji_config_file:
        config_file = (utils.find_file("config", [OSG_KOJI_USER_CONFIG_DIR,
                                                  KOJI_USER_CONFIG_DIR]) or
                       utils.find_file(KOJI_CONF, DATA_FILE_SEARCH_PATH))
        if not config_file:
            raise KojiError("Can't find Koji config file")
        __koji_config_file = config_file

    return __koji_config_file


def get_koji_config(config_file=None):
    # type: (Optional[str]) -> configparser.ConfigParser
    """Parse and return a koji config file, validating that it has some of the
    necessary properties (e.g., a 'koji' section).

    config_file: a path to the koji config file or None (in which case the default path will be used)

    """
    global __koji_config

    if not __koji_config:
        config = configparser.ConfigParser()
        if not config_file:
            config_file = get_koji_config_file()
        config.read(config_file)
        if not config.has_section("koji"):
            raise KojiError("Koji config file %s is missing a 'koji' section" % config_file)
        for opt in "server", "weburl", "topurl":  # TODO: "authtype" should also be required once we move to kerberos
            if not config.has_option("koji", opt):
                raise KojiError("Koji config file %s is missing the '%s' option" % (config_file, opt))
        __koji_config = config

    return __koji_config


def get_koji_cmd():
    """Get the command used to call koji."""
    which_osg_koji = utils.which("osg-koji")
    if which_osg_koji:
        return [which_osg_koji]
    else:
        raise KojiError("'osg-koji' not found")


def download_koji_file(task_id, filename, destdir):
    """Download a the file 'filename' for task number 'task_id' and place it
    in destdir/task_id/filename

    """
    weburl = KOJI_WEB + "/koji"
    try:
        weburl = get_koji_config().get("koji", "weburl")
    except KojiError:
        pass
    url = weburl + "/getfile?taskID=%d&name=%s" % (task_id, filename)
    log.debug('Retrieving ' + url)
    try:
        handle = urllib.request.urlopen(url)
    except urllib.error.HTTPError as err:
        log.error('Error retrieving ' + url)
        log.error(str(err))
        raise
    utils.safe_makedirs(destdir)
    full_filename = os.path.join(destdir, filename)
    with open(full_filename, 'w') as desthandle:
        desthandle.write(handle.read())


def chop_package_el_suffix(package):
    # type: (str) -> str
    """If the package directory has the el version(s) at the end, e.g.
    condor.el9, buildsys-macros.el8, foobar.el7.el8
    chop them off. This gives us the "base" package name for adding to the
    Koji tag.
    """
    el_pattern = re.compile(r"([.]el\d+)+$")
    real_package = el_pattern.sub("", package)
    return real_package


class KojiInter(object):
    """An interface around the koji cli"""
    backend = None

    def __init__(self, opts):
        self.no_wait = opts['no_wait']
        self.regen_repos = opts['regen_repos']
        self.scratch = opts['scratch']
        self.arch_override = opts.get('target_arch', None)
        if self.arch_override and not self.scratch:
            log.warning("target-arch ignored on non-scratch builds")
            self.arch_override = None

        if KojiInter.backend is None:
            if not HAVE_KOJILIB and opts['koji_backend'] == 'kojilib':
                raise KojiError("KojiLib backend requested, but can't import it!")
            elif HAVE_KOJILIB and opts.get('koji_backend') != 'shell':
                log.debug("KojiInter Using KojiLib backend")
                KojiInter.backend = KojiLibInter(opts['dry_run'])
            else:
                log.debug("KojiInter Using shell backend")
                KojiInter.backend = KojiShellInter(opts['dry_run'])
            KojiInter.backend.read_config_file()
            KojiInter.backend.init_koji_session()

        self.target = opts['koji_target']
        self.build_tag, self.dest_tag = KojiInter.backend.get_build_and_dest_tags(self.target)
        if opts['koji_tag'] == 'TARGET':
            self.tag = self.dest_tag
        else:
            self.tag = opts['koji_tag']

        self.background = opts['background']



    def add_pkg(self, package_name):
        """Part of koji task. If the package needs to be added to koji_tag,
        do so.

        """
        return KojiInter.backend.add_pkg(self.tag, package_name)


    def build_srpm(self, srpm):
        """Submit an SRPM build"""
        return KojiInter.backend.build_srpm(srpm,
                                            self.target,
                                            self.scratch,
                                            regen_repos=self.regen_repos,
                                            no_wait=self.no_wait,
                                            background=self.background,
                                            arch_override=self.arch_override)


    def build_svn(self, url, rev):
        """Submit an SVN build"""
        return KojiInter.backend.build("svn+" + url + "#" + rev,
                                       self.target,
                                       self.scratch,
                                       regen_repos=self.regen_repos,
                                       no_wait=self.no_wait,
                                       background=self.background,
                                       arch_override=self.arch_override)

    def build_git(self, remote, rev, path):
        """Submit a GIT build"""
        print(remote)
        return KojiInter.backend.build("git+" + remote + "?" + path + "#" + rev,
                                       self.target,
                                       self.scratch,
                                       regen_repos=self.regen_repos,
                                       no_wait=self.no_wait,
                                       background=self.background,
                                       arch_override=self.arch_override)

    def mock_config(self, arch, tag, dist, outpath, name):
        """Request a mock config from koji-hub"""
        return KojiInter.backend.mock_config(arch, tag, dist, outpath, name)
# end of class KojiInter


class KojiShellInter(object):
    """An interface to doing koji tasks via invoking the koji cli through
    the shell.

    """
    def __init__(self, dry_run=False):
        self.koji_cmd = get_koji_cmd()
        self.user = None
        self.authtype = DEFAULT_AUTHTYPE
        self.topurl = os.path.join(KOJI_HUB, "kojifiles")
        self.dry_run = dry_run

    def read_config_file(self, config_file=None):
        # TODO duplication between here and KojiLibInter
        try:
            cfg = get_koji_config(config_file)
            items = dict(cfg.items('koji'))
        except configparser.Error as err:
            raise KojiError("Can't read config file from %s: %s" % (config_file, err))
        for var in ['topurl', 'authtype']:
            if items.get(var):
                setattr(self, var, os.path.expanduser(items[var]))

    def init_koji_session(self, login=True):
        if login and not self.dry_run:
            self.login_to_koji()

    def login_to_koji(self):
        log.info("Logging in to koji using %s auth", self.authtype)
        try:
            output = utils.checked_backtick(self.koji_cmd + ["call", "--json", "getLoggedInUser"])
            output_js = json.loads(output)
            self.user = output_js["name"]
        except (KeyError, AttributeError, json.JSONDecodeError, utils.CalledProcessError) as err:
            raise KojiError("Couldn't log in to Koji: %s" % err) from err

    def add_pkg(self, tag, package, owner=None):
        if owner is None:
            owner = self.user
        if not self.dry_run and not owner:
            raise KojiError("Cannot add package without an owner")
        real_package = chop_package_el_suffix(package)
        found = False
        list_pkgs = utils.backtick(self.koji_cmd + ["list-pkgs", "--package", real_package])
        for line in list_pkgs.split("\n"):
            fields = re.split(r"\s*", line, 2)
            try:
                if fields[1] == tag:
                    found = True
            except IndexError:
                pass

        if not found:
            cmd = (self.koji_cmd + ["add-pkg", tag, real_package, "--owner", owner])
            log.info("Calling koji to add the package to tag %s", tag)
            if not self.dry_run:
                utils.checked_call(cmd)
            else:
                print(" ".join(cmd))

    def get_build_and_dest_tags(self, target):
        """Return the build and destination tags for the current target."""
        line = utils.checked_backtick(self.koji_cmd + ["-q", "list-targets", "--name", target])
        if not line:
            raise KojiError("Unable to find koji target with the name " + target)
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
        kwargs recognized: no_wait, regen_repos, background, arch_override

        """
        log.debug("building " + url)
        no_wait = kwargs.get('no_wait', False)
        regen_repos = kwargs.get('regen_repos', False)
        background = kwargs.get('background', False)
        arch_override = kwargs.get('arch_override', None)
        build_subcmd = ["build", target, url]
        if scratch:
            build_subcmd += ["--scratch"]
        if no_wait:
            build_subcmd += ["--nowait"]
        if background:
            build_subcmd += ["--background"]
        if arch_override:
            build_subcmd += ["--arch-override=" + arch_override]
        log.info("Calling koji to build the package for target %s", target)

        if not self.dry_run:
            err = utils.unchecked_call(self.koji_cmd + build_subcmd)
        else:
            print(" ".join(self.koji_cmd + build_subcmd))
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
                print(" ".join(self.koji_cmd + regen_repo_subcmd))
                err2 = 0
            if err2:
                raise KojiError("koji regen-repo failed with exit code " + str(err2))


    def build_srpm(self, srpm, target, scratch=False, **kwargs):
        """Submit an SRPM build"""
        return self.build(srpm, target, scratch, **kwargs)

    def get_targets(self):
        """Get a list of the names of targets (as strings) from koji"""
        out, err = utils.sbacktick(self.koji_cmd + ["list-targets", "--quiet"])
        if err:
            raise KojiError("koji list-targets failed with exit code " + str(err))
        lines = out.split("\n")
        target_names = [re.split(r"\s+", x)[0] for x in lines]
        return target_names


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
            raise KojiError("koji mock-config failed with exit code " + str(err))


    def search_names(self, terms, stype, match):
        search_subcmd = ["search", stype]
        if match == 'regex':
            search_subcmd.append("--regex")
        elif match == 'exact':
            search_subcmd.append("--exact")
        search_subcmd.append(terms)

        out, err = utils.sbacktick(self.koji_cmd + search_subcmd)
        if err:
            raise KojiError("koji search failed with exit code " + str(err))
        return out.split("\n")



    def tag_build(self, tag, build, force=False):
        tag_pkg_subcmd = ["tag-pkg", tag, build]
        if force:
            tag_pkg_subcmd.append("--force")
        err = utils.unchecked_call(self.koji_cmd + tag_pkg_subcmd)
        if err:
            raise KojiError("koji tag-pkg failed with exit code " + str(err))


    def watch_tasks(self, *args):
        log.debug('Watching tasks not implemented in Shell backend')


    def watch_tasks_with_retry(self, *args):
        log.debug('Watching tasks not implemented in Shell backend')



if HAVE_KOJILIB:
    # HACK
    # Create an object that has an instance variable named poll_interval.
    # kojicli.watch_tasks() expects a global variable named options with
    # an attribute poll_interval to determine how often to poll the server
    # for a status update.
    # TODO This doesn't seem to be true by Koji 1.33 so this hack can be removed;
    #      poll_interval is now an argument to watch_tasks()
    class _KojiCliOptions(object): # pylint: disable=C0111,R0903
        def __init__(self, poll_interval):
            self.poll_interval = poll_interval
    kojicli.options = _KojiCliOptions(5)


def koji_error_wrap(description):
    """Decorator to wrap the body of a function in a try/except clause which
    catches kojilib.GenericError and raises a KojiError with a more
    user-friendly error message including a description of what we were doing.
    Also catches kojilib.ServerOffline and raises a more specific error.

    Example usage:
        @koji_error_wrap('adding package')
        def add_pkg(self, ...):
            ...

    """
    # Due to the way decorators work in python, it is necessary to have three levels of functions here.
    # This:
    #   @koji_error_wrap(description)
    #   def foo()...
    # gets translated into:
    #   def foo()...
    #   foo = koji_error_wrap(description)(foo)
    # The second line then becomes:
    #   foo = koji_error_wrap_helper(foo)
    # (where the definition of koji_error_wrap_helper depends on 'description'),
    # which must then return a function that has the same calling conventions as 'foo'.
    def koji_error_wrap_helper(function_to_wrap):
        def wrapped_function(*args, **kwargs):
            try:
                return function_to_wrap(*args, **kwargs)
            except kojilib.ServerOffline as err:
                raise KojiError("Server outage detected while %s: %s" % (description, err))
            except kojilib.GenericError as err:
                raise KojiError("Error of type %s while %s: %s" % (type_of_error(err), description, err))
        return wrapped_function
    return koji_error_wrap_helper


class KojiLibInter(object):
    # Aliasing for convenience
    if HAVE_KOJILIB:
        BR_STATES = kojilib.BR_STATES
        BUILD_STATES = kojilib.BUILD_STATES
        REPO_STATES = kojilib.REPO_STATES
        TASK_STATES = kojilib.TASK_STATES

    def __init__(self, dry_run=False):
        if not HAVE_KOJILIB:
            raise KojiError("Cannot use KojiLibInter without kojilib!")

        self.ca = None
        self.cert = KOJI_CLIENT_CERT
        self.kojisession = None
        self.server = os.path.join(KOJI_HUB, "kojihub")
        self.serverca = None
        self.user = None
        self.authtype = DEFAULT_AUTHTYPE
        self.weburl = os.path.join(KOJI_WEB, "koji")
        self.topurl = os.path.join(KOJI_WEB, "kojifiles")
        self.dry_run = dry_run

        # "Fix" for SOFTWARE-3112:
        # python-requests, via urllib3, requests keep-alives by default, which are apparently disabled on koji-hub.
        # This leads to "resetting dropped connection" messages.  I can't find a way to turn off keep-alives so I
        # turn off those messages.
        logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
        logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(logging.WARNING)

    def read_config_file(self, config_file=None):
        try:
            cfg = get_koji_config(config_file)
            items = dict(cfg.items('koji'))

            try:
                use_old_ssl = cfg.getboolean('koji', 'use_old_ssl')
                if use_old_ssl:
                    log.warning("Ignoring use_old_ssl: only supported on Python 2")
            except configparser.NoOptionError:
                pass
        except configparser.Error as err:
            raise KojiError("Can't read config file from %s: %s" % (config_file, err))
        for var in ['ca', 'cert', 'server', 'serverca', 'weburl', 'topurl', 'authtype']:
            if items.get(var):
                setattr(self, var, os.path.expanduser(items[var]))


    def init_koji_session(self, login=True):
        log.info("Initializing koji session to %s", self.server)
        self.kojisession = kojilib.ClientSession(self.server, {})
        if login and not self.dry_run:
            self.login_to_koji()


    def login_to_koji(self):
        log.info("Logging in to koji using %s auth", self.authtype)
        # TODO validate parameters
        if self.authtype == "ssl":
            try:
                self.kojisession.ssl_login(self.cert, self.ca, self.serverca)
            except Exception as err:
                raise KojiError("Couldn't do ssl_login: " + str(err))
        elif self.authtype == "kerberos":
            try:
                self.kojisession.gssapi_login()
            except Exception as err:
                raise KojiError("Couldn't do gssapi_login: " + str(err))
        else:
            raise KojiError("authtype %s not supported; must be either 'kerberos' or 'ssl'" % self.authtype)
        try:
            self.user = self.kojisession.getLoggedInUser()["name"]
        except (KeyError, AttributeError):
            raise KojiError("Couldn't log in to koji for unknown reason")


    @koji_error_wrap('adding package')
    def add_pkg(self, tag, package, owner=None):
        if owner is None:
            owner = self.user
        if not self.dry_run and not owner:
            raise KojiError("Cannot add package without an owner")
        tag_obj = self.kojisession.getTag(tag)
        if not tag_obj:
            raise KojiError("Invalid tag %s" % tag)
        real_package = chop_package_el_suffix(package)
        try:
            package_list = self.kojisession.listPackages(tagID=tag_obj['id'], pkgID=real_package)
        except kojilib.GenericError: # koji raises this if the package doesn't exist
            package_list = None
        if not package_list:
            if not self.dry_run:
                return self.kojisession.packageListAdd(tag, real_package, owner)
            else:
                log.info("kojisession.packageListAdd(%r, %r, %r)", tag, real_package, owner)


    @koji_error_wrap('building')
    def build(self, url, target, scratch=False, **kwargs):
        """build package at url for target.

        Using **kwargs so signature is same as KojiShellInter.build.
        kwargs recognized: priority, background, arch_override

        """
        opts = { 'scratch': scratch }
        arch_override = kwargs.get('arch_override', None)
        if arch_override:
            opts['arch_override'] = arch_override
        priority = kwargs.get('priority', None)
        if kwargs.get('background', False):
            priority = priority or 5 # Copied from koji cli
        if not self.dry_run:
            return self.kojisession.build(url, target, opts, priority)
        else:
            log.info("kojisession.build(%r, %r, %r, %r)", url, target, opts, priority)


    def build_srpm(self, srpm, target, scratch=False, **kwargs):
        return self.build(self.upload(srpm),
                          target,
                          scratch=scratch,
                          **kwargs)

    @koji_error_wrap('getting targets')
    def get_targets(self):
        """Get a list of the names of targets (as strings) from koji"""
        targets = self.kojisession.getBuildTargets(None)
        target_names = sorted([x['name'] for x in targets])
        return target_names

    @koji_error_wrap('generating mock config')
    def mock_config(self, arch, tag, dist, outpath, name):
        tag_obj = self.kojisession.getTag(tag)
        if not tag_obj:
            raise KojiError("Invalid tag %s" % tag)
        config = self.kojisession.getBuildConfig(tag_obj['id'])
        if not config:
            raise KojiError("Couldn't get config for tag %s" % tag)
        repo = self.kojisession.getRepo(config['id'])
        if not repo:
            raise KojiError("Couldn't get repo for tag %s" % tag)
        opts = {'tag_name': tag_obj['name'],
                'repoid': repo['id'],
                'distribution': dist,
                'topurl': self.topurl}
        output = kojilib.genMockConfig(name, arch, **opts)
        utils.unslurp(outpath, output)


    @koji_error_wrap('searching')
    def search(self, terms, stype, match):
        return self.kojisession.search(terms, stype, match)


    def search_names(self, terms, stype, match):
        data = self.search(terms, stype, match)
        return [x['name'] for x in data]


    @koji_error_wrap('tagging')
    def tag_build(self, tag, build, force=False):
        return self.kojisession.tagBuild(tag, build, force)


    @koji_error_wrap('uploading')
    def upload(self, source):
        "Upload a file to koji. Return the relative remote path."
        serverdir = self._unique_path()
        if not self.dry_run:
            self.kojisession.uploadWrapper(source, serverdir, callback=None)
        return os.path.join(serverdir, os.path.basename(source))


    # taken from cli/koji from Koji version 1.11
    # Copyright (c) 2005-2014 Red Hat, Inc.
    def _unique_path(self, prefix="cli-build"):
        """Create a unique path fragment by appending a path component
        to prefix.  The path component will consist of a string of letter and numbers
        that is unlikely to be a duplicate, but is not guaranteed to be unique."""
        # Use time() in the dirname to provide a little more information when
        # browsing the filesystem.
        # For some reason repr(time.time()) includes 4 or 5
        # more digits of precision than str(time.time())
        return '%s/%r.%s' % (prefix, time.time(),
                          ''.join([random.choice(string.ascii_letters) for i in range(8)]))


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
            log.info("self.kojisession.newRepo(%r)", tag)


    @koji_error_wrap('watching tasks')
    def watch_tasks(self, tasks):
        return kojicli.watch_tasks(self.kojisession, tasks)


    @koji_error_wrap('watching tasks')
    def watch_tasks_with_retry(self, tasks, max_retries=20, retry_interval=20):
        tries = 0
        while True:
            try:
                return kojicli.watch_tasks(self.kojisession, tasks)
            except kojilib.ServerOffline as err:
                # these have a large chance of being bogus
                log.info("Got error from server: %s", err)
                tries += 1
                if tries < max_retries:
                    log.info("Retrying in %d seconds", retry_interval)
                    time.sleep(retry_interval)
                else:
                    raise


    @koji_error_wrap('downloading results')
    def download_results(self, task_ids, destdir):
        """Download the resulting files of a set of tasks into destdir.
        Each task gets its own separate subdir in destdir.

        """
        session = self.kojisession

        # Loop through all task ids, and also get their children if they have not
        # been specified; get all output files for each task and download them.
        all_task_ids = [int(x) for x in task_ids]
        for task_id in all_task_ids:
            children = session.getTaskChildren(task_id)
            for child in children:
                child_id = int(child['id'])
                if child_id not in all_task_ids:
                    all_task_ids.append(child_id)

            # buildArch tasks have files in them that we want. Get tag and arch
            # from task info and download files into a subdir under destdir.
            # Subdir name determined by build tag and arch. If the build tag is
            # el5-osg-build and the arch is noarch, files will be in 'el5-osg-noarch'.
            task_info = session.getTaskInfo(task_id, request=True)
            if task_info.get('method', "") == 'buildArch':
                if 'request' in task_info:
                    tag_id, arch = task_info['request'][1:3]
                    tag_info = session.getTag(tag_id)
                    try:
                        tag_name = tag_info.get('name', 'unknown')
                        filenames = session.listTaskOutput(task_id)
                        for filename in filenames:
                            if not filename.endswith('src.rpm'):
                                destsubdir = re.sub(r'-build', '', tag_name) + "-" + arch
                                download_koji_file(task_id, filename, os.path.join(destdir, destsubdir))
                    except (TypeError, AttributeError, urllib.error.HTTPError):
                        # TODO More useful error message
                        log.warning("Unable to download files for task %d", task_id)
                        return False
        return True


# end of class KojiLibInter
