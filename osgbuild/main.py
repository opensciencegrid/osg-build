"""osg build script"""


# TODO Shouldn't need koji access for 'rpmbuild', but currently does since it
# gets the values for the --repo arg -- which is only used for koji builds.
# Make it so.
from __future__ import absolute_import
from __future__ import print_function
import logging
from optparse import OptionGroup, OptionParser, OptionValueError
import re
import tempfile

from .constants import *
from .error import UsageError, KojiError, SVNError, GitError, Error
from . import srpm
from . import svn
from . import git
from . import utils
from .version import __version__

try:
    from . import kojiinter
except ImportError:
    kojiinter = None

try:
    from . import mock
except ImportError:
    mock = None

log = logging.getLogger('')
log.setLevel(logging.INFO)
log_consolehandler = logging.StreamHandler()
log_consolehandler.setLevel(logging.INFO)
log_formatter = logging.Formatter(" >> %(message)s")
log_consolehandler.setFormatter(log_formatter)
log.addHandler(log_consolehandler)

#-------------------------------------------------------------------------------
# Main function
#-------------------------------------------------------------------------------
def main(argv):
    """Main function."""

    buildopts, package_dirs, task = init(argv)
    vcs = None

    if task in ['koji', 'mock']:
        for dver in buildopts['enabled_dvers']:
            targetopts = buildopts['targetopts_by_dver'][dver]
            if kojiinter:
                targetopts['koji_target'] = targetopts['koji_target'] or target_for_repo_hint(buildopts['repo'], dver)
                targetopts['koji_tag'] = targetopts['koji_tag'] or tag_for_repo_hint(buildopts['repo'], dver)
    # checks
    if task == 'koji' and buildopts['vcs']:
        # verify working dirs
        for pkg in package_dirs:
            vcs_ok = False
            # vcs is the module for accessing the repo
            vcs = svn if svn.is_svn(pkg) else git if git.is_git(pkg) else None
            if vcs:
                try:
                    vcs_ok = vcs.verify_working_dir(pkg)
                except (SVNError, GitError) as err:
                    log.info(str(err))
            if not vcs_ok:
                print("VCS build requested but no usable VCS found for " + pkg)
                print("Exiting")
                return 1

            if not buildopts['scratch']:
                vcs.verify_correct_branch(pkg, buildopts)
    else:
        # verify package dirs
        for pkg in package_dirs:
            if not os.path.isdir(pkg):
                raise UsageError(pkg + " isn't a directory!")
            if ((not os.path.isdir(os.path.join(pkg, "osg"))) and
                    (not os.path.isdir(os.path.join(pkg, "upstream")))):
                raise UsageError(pkg +
                    " isn't a package directory "
                    "(must have either osg/ or upstream/ dirs or both)")

    if (task == 'koji' and not buildopts['scratch'] and not buildopts['vcs']):
        raise UsageError("Non-scratch Koji builds must be from SVN!")

    if task == 'koji' and len(package_dirs) >= BACKGROUND_THRESHOLD:
        buildopts['background'] = True

    # main loop
    # HACK
    task_ids = []
    task_ids_by_results_dir = dict()
    for pkg in package_dirs:
        for dver in buildopts['enabled_dvers']:
            dver_buildopts = buildopts.copy()
            dver_buildopts.update(buildopts['targetopts_by_dver'][dver])

            mock_obj = None
            koji_obj = None
            if task == 'koji':
                assert kojiinter  # shouldn't get here without osg-build-koji
                koji_obj = kojiinter.KojiInter(dver_buildopts)
            if task == 'mock':
                assert mock  # shouldn't get here without osg-build-mock
                if dver_buildopts['mock_config_from_koji']:
                    assert kojiinter  # shouldn't get here without osg-build-koji
                    # HACK: We don't want to log in to koji just to get a mock config
                    dver_buildopts_ = dver_buildopts.copy()
                    dver_buildopts_['dry_run'] = True
                    koji_obj = kojiinter.KojiInter(dver_buildopts_)
                mock_obj = mock.Mock(dver_buildopts, koji_obj)

            if buildopts['vcs'] and task == 'koji':
                task_ids.append(vcs.koji(pkg, koji_obj, dver_buildopts))
            else:
                builder = srpm.SRPMBuild(pkg,
                                         dver_buildopts,
                                         mock_obj=mock_obj,
                                         koji_obj=koji_obj)
                builder.maybe_autoclean()
                method = getattr(builder, task)
                if task == 'koji':
                    task_ids_by_results_dir.setdefault(builder.results_dir, [])
                    task_id = method()
                    task_ids.append(task_id)
                    task_ids_by_results_dir[builder.results_dir].append(task_id)
                else:
                    method()
    # end of main loop
    # HACK
    task_ids = [_f for _f in task_ids if _f]
    if kojiinter and kojiinter.KojiInter.backend and task_ids:
        print("Koji task ids are:", task_ids)
        for tid in task_ids:
            print(KOJI_WEB + "/koji/taskinfo?taskID=" + str(tid))
        if not buildopts['no_wait']:
            ret = kojiinter.KojiInter.backend.watch_tasks_with_retry(task_ids)
            # TODO This is not implemented for the KojiShellInter backend
            # Not implemented for SVN builds since results_dir is undefined for those
            if buildopts['getfiles']:
                if buildopts['vcs']:
                    log.warning("--getfiles is only for SRPM builds")
                elif not isinstance(kojiinter.KojiInter.backend, kojiinter.KojiLibInter):
                    log.warning("--getfiles is only implemented on the KojiLib backend")
                else:
                    for destdir, tids in task_ids_by_results_dir.items():
                        if kojiinter.KojiInter.backend.download_results(tids, destdir):
                            log.info("Results and logs downloaded to %s", destdir)
            try:
                return int(ret)
            except (TypeError, ValueError):
                pass
        else:
            if buildopts['getfiles']:
                log.warning("Cannot use both --getfiles and --nowait")

    return 0
# end of main()


def init(argv):
    """Initialization. Get build options and packages.

    """
    options, args = parse_cmdline_args(argv)

    if options.version:
        print_version_and_exit()
    # if loglevel is passed on the command line, make it take into effect
    # immediately so we see debug messages in get_buildopts
    if options.loglevel:
        set_loglevel(options.loglevel)

    task = get_task(args)
    # Check for required modules
    if task == 'mock' and not mock:
        raise Error('Mock plugin not found.\nInstall osg-build-mock to make the mock task available.')
    elif task == 'koji' and not kojiinter:
        raise Error('Koji plugin not found.\nInstall osg-build-koji to make the koji task available.')

    buildopts = get_buildopts(options, task)
    if buildopts['mock_config_from_koji'] and not kojiinter:
        raise Error('Koji plugin not found.\nInstall osg-build-koji to make getting a Mock config from Koji available.')

    set_loglevel(buildopts.get('loglevel', 'INFO'))

    package_dirs = args[1:]
    if not package_dirs:
        guess = guess_pkg_dir(os.getcwd())
        log.info("Package dir not specified, using %s", guess)
        package_dirs.append(guess)

    return (buildopts, package_dirs, task)
# end of init()


__koji_targets_cache = None
def valid_koji_targets():
    """Return a list of valid koji targets (to be used for building up the list
    of values for the --repo argument).
    """
    global __koji_targets_cache # pylint:disable=W0603
    if not __koji_targets_cache:
        # HACK
        try:
            koji_obj = kojiinter.KojiShellInter(dry_run=True, koji_wrapper=True)
            __koji_targets_cache = koji_obj.get_targets()
        except KojiError as err:
            log.warning(str(err))
    return __koji_targets_cache

def valid_dvers(targets):
    """Return a list of valid dvers as derived from a list of koji targets.
    targets: a list of koji targets returned by valid_koji_targets"""
    dvers = set()
    for target in targets:
        dver = get_dver_from_string(target)
        if dver:
            dvers.add(dver)
    return sorted(dvers)

__repo_hints_cache = None
def repo_hints(targets):
    """Return the valid arguments for --repo and the target and tag hints
    associated with them.  Most of the repo_hints are already specified in
    REPO_HINTS_STATIC, but we need to determine which 'versioned' osg targets
    (e.g. osg-3.1-el5) exist.

    'targets' is a list of koji targets and can be obtained from
    valid_koji_targets().

    """
    global __repo_hints_cache # pylint:disable=W0603

    if not __repo_hints_cache:
        __repo_hints_cache = REPO_HINTS_STATIC.copy()
        if targets:
            for target in targets:
                osg_match = re.match(r'osg-([0-9.]+)-el\d+', target)
                osg_main_match = re.match(r'osg-(\d+)-main-el\d+', target)
                osg_upcoming_match = re.match(r'osg-([0-9.]+)-upcoming-el\d+', target)
                osg_internal_match = re.match(r'osg-(\d+)-internal-el\d+', target)
                if osg_match:
                    osgver = osg_match.group(1)
                    __repo_hints_cache[osgver] = __repo_hints_cache['osg-%s' % osgver] = {'target': 'osg-%s-%%(dver)s' % osgver, 'tag': 'osg-%(dver)s'}
                elif osg_main_match:
                    osgver = osg_main_match.group(1)
                    __repo_hints_cache["%s-main" % osgver] = __repo_hints_cache['osg-%s' % osgver] = {'target': 'osg-%s-main-%%(dver)s' % osgver, 'tag': 'osg-%(dver)s'}
                elif osg_upcoming_match:
                    osgver = osg_upcoming_match.group(1)
                    __repo_hints_cache["%s-upcoming" % osgver] = {'target': 'osg-%s-upcoming-%%(dver)s' % osgver, 'tag': 'osg-%(dver)s'}
                elif osg_internal_match:
                    osgver = osg_internal_match.group(1)
                    __repo_hints_cache["%s-internal" % osgver] = {'target': 'osg-%s-internal-%%(dver)s' % osgver, 'tag': 'osg-%(dver)s'}

    return __repo_hints_cache


def set_loglevel(level_str):
    """Sets the log level from a string. level_str should match one of the
    constants defined in logging"""
    global log, log_consolehandler

    try:
        loglevel = int(getattr(logging, level_str.upper()))
    except (TypeError, AttributeError):
        raise UsageError("Invalid log level")

    log.setLevel(loglevel)
    log_consolehandler.setLevel(loglevel)


def parse_cmdline_args(argv):
    """Parse the arguments given on the command line. Return a tuple containing
    options:    the options object, containing the keyword arguments
    args:       a list containing the positional arguments left over

    """
    header = """
   %prog TASK PACKAGE1 <PACKAGE2..n> [options]

Valid tasks are:
lint         Discover potential package problems using rpmlint(1)
prebuild     Preprocess the package, create SRPM to be submitted, and stop
prepare      Use 'rpmbuild -bp' to unpack and patch the package
quilt        Preprocess the package and run 'quilt setup' on the spec file to
             unpack the source files and prepare a quilt(1) series file.
rpmbuild     Build using rpmbuild(8) on the local machine
"""
    header_post = ""
    if kojiinter:
        header += "koji         Build using the Koji build system\n"
    else:
        header_post += "Install osg-build-koji to make the koji task available\n"
    if mock:
        header += "mock         Build using mock(1) on the local machine\n"
    else:
        header_post += "Install osg-build-mock to make the mock task available\n"

    if header_post:
        header += "\n" + header_post

    parser = OptionParser(header)
    parser.add_option(
        "-a", "--autoclean", action="store_true",
        help="Clean out the following directories before each build: "
        "'%s', '%s', '%s', '%s' (default)" % (
            WD_RESULTS, WD_PREBUILD, WD_UNPACKED, WD_UNPACKED_TARBALL))
    parser.add_option(
        "--no-autoclean", action="store_false", dest="autoclean",
        help="Disable autoclean")
    parser.add_option(
        "-c", "--cache-prefix",
        help="The prefix for the software cache to take source files from. "
        "The following special caches exist: "
        "AFS (%s), VDT (%s), and AUTO (AFS if avaliable, VDT if not). "
        "Default: AUTO" % (AFS_CACHE_PREFIX, WEB_CACHE_PREFIX))
    for dver in DVERS:
        rhel = int(dver[2:])
        parser.add_option(
            "--"+dver, action="callback", callback=parser_targetopts_callback,
            type=None,
            dest="redhat_release",
            help="Build for RHEL %d-compatible. Equivalent to --redhat-release=%d" % (rhel,rhel))
    parser.add_option(
        "--loglevel",
        help="The level of logging the script should do. "
        "Valid values are: DEBUG,INFO,WARNING,ERROR,CRITICAL. Default: INFO")
    parser.add_option(
        "-q", "--quiet", action="store_const", const="warning", dest="loglevel",
        help="Display less information. Equivalent to --loglevel=warning")
    parser.add_option(
        "--redhat-release", action="callback",
        callback=parser_targetopts_callback,
        dest="redhat_release",
        type="string",
        help="The version of the distribution to build the package for. "
        "Valid values are: 7 or 8 (for EL 7 or 8 respectively). "
        "Default: build for all releases (koji task) current platform "
        "(other tasks)")
    parser.add_option(
        "-t", "--target-arch",
        help="The target architecture to build for. Ignored in non-scratch "
        "Koji builds. Default: all architectures (koji task) or current "
        "architecture (other tasks)")
    parser.add_option(
        "-v", "--verbose", action="store_const", const="debug", dest="loglevel",
        help="Display more information. Equivalent to --loglevel=debug")
    parser.add_option(
        "--version", action="store_true",
        help="Show version and exit.")
    parser.add_option(
        "-w", "--working-directory",
        help="The base directory to use for temporary files made by the "
        "script. If it is 'TEMP', a randomly-named directory under /tmp "
        "is used. Default: package directory")

    prebuild_group = OptionGroup(parser,
                                 "prebuild task options")
    prebuild_group.add_option(
        "--full-extract", action="store_true",
        help="Fully extract all source files")
    parser.add_option_group(prebuild_group)

    rpmbuild_mock_group = OptionGroup(parser,
                                      "rpmbuild and mock task options")
    rpmbuild_mock_group.add_option(
        "--distro-tag",
        help="The distribution tag to append to the end of the release. "
        "Default: osg.el7, or osg.el8, etc. for EL 7 or 8, etc. respectively")
    parser.add_option_group(rpmbuild_mock_group)

    if mock:
        mock_group = OptionGroup(parser,
                                 "mock task options")
        mock_group.add_option(
            "--mock-clean", action="store_true", dest="mock_clean",
            help="Clean the mock buildroot after building (default)")
        mock_group.add_option(
            "--no-mock-clean", action="store_false", dest="mock_clean",
            help="Do not clean the mock buildroot after building")
        mock_group.add_option(
            "-m", "--mock-config",
            help="The location of a mock config file to build using. "
            "Either this or --mock-config-from-koji must be specified")
        mock_group.add_option(
            "--mock-config-from-koji",
            help="Use a mock config based on a koji buildroot (build tag, "
            "such as osg-3.4-el7-build). Either this or --mock-config must be "
            "specified. This option requires the osg-build-koji plugin")
        parser.add_option_group(mock_group)

    if kojiinter:
        koji_group = OptionGroup(parser,
                                 "koji task options")
        koji_group.add_option(
            "--background", action="store_true",
            help="Run build at a lower priority")
        koji_group.add_option(
            "--dry-run", action="store_true",
            help="Do not invoke koji, only show what would be done")
        koji_group.add_option(
            "--getfiles", "--get-files", action="store_true", dest="getfiles",
            help="Download finished products and logfiles")
        koji_group.add_option(
            "--koji-backend", dest="koji_backend",
            help="The back end to use for invoking koji. Valid values are: "
            "'shell', 'kojilib'. Default: use kojilib if possible")
        koji_group.add_option(
            "-k", "--kojilogin", "--koji-login", dest="kojilogin",
            help="The login you use for koji (most likely your CN, e.g."
            "'Matyas Selmeci 564109'). Default: what's in ~/.osg-koji/client.crt")
        koji_group.add_option(
            "--koji-target",
            action="callback",
            callback=parser_targetopts_callback,
            type="string",
            help="The koji target to use for building. "
            "It is recommended to use the --repo option instead of this when the "
            "desired repo is available. Default: osg-el7 or osg-el8, etc. "
            "for EL 7 or 8, etc. respectively")
        koji_group.add_option(
            "--koji-tag",
            action="callback",
            callback=parser_targetopts_callback,
            type="string",
            help="The koji tag to add packages to. The special value TARGET "
            "uses the destination tag defined in the koji target. "
            "It is recommended to use the --repo option instead of this when the "
            "desired repo is available. Default: osg-el7 or osg-el8, etc. "
            "for EL 7 or 8, etc. respectively")
        koji_group.add_option(
            "--koji-target-and-tag", "--ktt",
            action="callback",
            callback=parser_targetopts_callback,
            type="string",
            dest="ktt",
            metavar='ARG',
            help="Specifies both the koji tag to add packages to and the target "
            "to use for building. '--ktt ARG' is equivalent to '--koji-target ARG "
            " --koji-tag ARG'. "
            "It is recommended to use the --repo option instead of this when the "
            "desired repo is available")
        koji_group.add_option(
            "--koji-wrapper", action="store_true", dest="koji_wrapper",
            help="Use the 'osg-koji' koji wrapper if using the 'shell' backend (default)")
        koji_group.add_option(
            "--no-koji-wrapper", action="store_false", dest="koji_wrapper",
            help="Do not use the 'osg-koji' koji wrapper if using the 'shell' "
            "backend, even if found")
        koji_group.add_option(
            "--no-wait", "--nowait", action="store_true", dest="no_wait",
            help="Do not wait for the build to finish")
        koji_group.add_option(
            "--wait", action="store_false", dest="no_wait",
            help="Wait for the build to finish (default)")
        koji_group.add_option(
            "--regen-repos", action="store_true",
            help="Perform a regen-repo on the build and destination repos after "
            "each koji build. Allows doing builds that depend on each other. "
            "Use sparingly, as this slows down builds and uses more disk space on "
            "the Koji server")
        koji_group.add_option(
            "--scratch", action="store_true",
            help="Perform a scratch build")
        koji_group.add_option(
            "--no-scratch", "--noscratch", action="store_false", dest="scratch",
            help="Do not perform a scratch build (default)")
        koji_group.add_option(
            "--vcs", "--svn", action="store_true", dest="vcs",
            help="Build package directly from SVN/Git "
            "(default for non-scratch builds)")
        koji_group.add_option(
            "--no-vcs", "--novcs", "--no-svn", "--nosvn", action="store_false", dest="vcs",
            help="Do not build package directly from SVN/Git "
            "(default for scratch builds)")
        koji_group.add_option(
            "--3.5-upcoming", action="callback",
            callback=parser_targetopts_callback,
            type=None,
            help="Target build for the 3.5-upcoming osg repos.")
        koji_group.add_option(
            "--3.6-upcoming", action="callback",
            callback=parser_targetopts_callback,
            type=None,
            help="Target build for the 3.6-upcoming osg repos.")
        koji_group.add_option(
            "--repo", action="callback",
            callback=parser_targetopts_callback,
            type="string", dest="repo",
            help="Specify a set of repos to build to (osg-3.6, 3.6-upcoming, "
            + "23-main, 23-upcoming, "
            + ", ".join(REPO_HINTS_STATIC.keys())
            + ")")
        parser.add_option_group(koji_group)

    options, args = parser.parse_args(argv[1:])

    return (options, args)
# end of parse_cmdline_args()


def get_dver_from_string(s):
    """Get the EL major version from a string containing it.
    Return None if not found."""
    if not s:
        return None
    match = re.search(r'\b(el\d+)\b', s)
    if match is not None:
        return match.group(1)
    else:
        return None

def target_for_repo_hint(repo_hint, dver):
    hints = repo_hints(valid_koji_targets())
    if repo_hint in hints:
        return hints[repo_hint]['target'] % {'dver': dver}
    else:
        raise UsageError("'%s' is not a valid repo.\nValid repos are: %s" % (repo_hint, ", ".join(sorted(hints.keys()))))

def tag_for_repo_hint(repo_hint, dver):
    return repo_hints(valid_koji_targets())[repo_hint]['tag'] % {'dver': dver}

def parser_targetopts_callback(option, opt_str, value, parser, *args, **kwargs): # unused-args: pylint:disable=W0613
    """Handle options in the 'targetopts_by_dver' set, such as --koji-tag,
    --redhat-release, etc.

    targetopts_by_dver is a dict keyed by redhat release (aka 'distro
    version' or 'dver' for short) The values of targetopts_by_dver are dicts
    containing the options to use for building with that dver. For example,
    targetopts_by_dver['7']['koji_tag'] is the koji tag to use when building
    for EL 7.

    enabled_dvers is the set of dvers to actually build for, which the
    --el6, --el7 and --redhat-release arguments affect. dvers may also be
    implicitly turned on by other arguments, e.g. specifying
    --koji-tag=el7-foobar will implicitly turn on el7 builds.

    Also handle --ktt (--koji-tag-and-target), which sets both koji_tag
    and koji_target, and --upcoming, and --repo, which sets the target for both dvers.

    """
    # for options that have aliases, option.dest gives us the
    # canonical name of the option (as opposed to opt_str, which gives us
    # what the user typed in)
    opt_name = option.dest

    # We create parser.values.targetopts_by_dver here instead of ahead of time
    # because parser.values is None until we actually run parser.parse_args().
    if not getattr(parser.values, 'targetopts_by_dver', None):
        parser.values.targetopts_by_dver = dict()
        for dver in DVERS:
            parser.values.targetopts_by_dver[dver] = DEFAULT_BUILDOPTS_BY_DVER[dver].copy()
    targetopts_by_dver = parser.values.targetopts_by_dver

    # We also have enabled_dvers for determining which dvers to build for.
    if not getattr(parser.values, 'enabled_dvers', None):
        parser.values.enabled_dvers = set()
    enabled_dvers = parser.values.enabled_dvers

    if value is None:
        value = ''
    if opt_name == 'redhat_release':
        for dver in DVERS:
            if opt_str == '--'+dver:
                enabled_dvers.add(dver)
        if opt_str == '--redhat-release':
            if 'el' + value in DVERS:
                enabled_dvers.add('el' + value)
            else:
                raise OptionValueError("Invalid redhat release value: %r" % value)
    elif opt_name == 'koji_tag' and value == 'TARGET': # HACK
        assert kojiinter  # shouldn't get here without kojiinter
        for dver in targetopts_by_dver:
            targetopts_by_dver[dver]['koji_tag'] = 'TARGET'
    elif opt_str.endswith('upcoming'):
        assert kojiinter  # shouldn't get here without kojiinter
        repo = opt_str[2:]
        parser.values.repo = repo
        for dver in DVERS:
            targetopts_by_dver[dver]['koji_target'] = target_for_repo_hint(repo, dver)
            targetopts_by_dver[dver]['koji_tag'] = tag_for_repo_hint(repo, dver)
    elif opt_str == '--repo':
        assert kojiinter  # shouldn't get here without kojiinter
        parser.values.repo = value
        for dver in DVERS:
            targetopts_by_dver[dver]['koji_target'] = target_for_repo_hint(value, dver)
            targetopts_by_dver[dver]['koji_tag'] = tag_for_repo_hint(value, dver)
    else:
        dver = get_dver_from_string(value)

        if not dver:
            raise OptionValueError('Unable to determine redhat release in parameter %r: %r' % (opt_str, value))

        if dver not in enabled_dvers:
            enabled_dvers.add(dver)
            log.debug("Implicitly enabled building for el%s due to %r argument %r" % (dver, opt_str, value))

        if opt_name == 'ktt':
            targetopts_by_dver[dver]['koji_tag'] = value
            targetopts_by_dver[dver]['koji_target'] = value
        else:
            targetopts_by_dver[dver][opt_name] = value
        if not verify_release_in_targetopts_by_dver(targetopts_by_dver[dver]):
            raise OptionValueError('Inconsistent redhat release in parameter %s: %s' % (opt_str, value))
# end of parser_targetopts_callback()



def get_task(args):
    """Return the task the user specified in the first positional argument,
    if it is a valid task. Allow the user to enter only the first few
    characters if the task is unambiguous. Raise UsageError if task is
    unspecified, invalid, or ambiguous.

    """
    if len(args) < 1:
        raise UsageError('Need task!')
    task = args[0]

    valid_tasks = ['koji', 'lint', 'mock', 'prebuild', 'prepare', 'quilt', 'rpmbuild']

    matching_tasks = [x for x in valid_tasks if x.startswith(task)]

    if len(matching_tasks) > 1:
        raise UsageError('Ambiguous task. Matching tasks are:' + ", ".join(matching_tasks))
    elif not matching_tasks:
        raise UsageError('No valid task')
    else:
        real_task = matching_tasks[0]

    return real_task
# end of get_task()


def get_buildopts(options, task):
    """Return a dict of the build options to use, based on the
    command-line arguments.

    """
    # The previous implementation also used a config file, which has two implications:
    # first, you should be able to override any option
    # with a subsequent option. Second, I can't set a 'default' value for any of
    # the options in the OptionParser object, because I need to distinguish
    # between the option not having been specified, and the option explicitly
    # being the default.
    #
    # TODO Now that the config file has been removed, simplify the code because I
    # no longer have to deal with the above.


    buildopts = DEFAULT_BUILDOPTS_COMMON.copy()

    # Backward compatibility for 'svn' option:
    buildopts['vcs'] = buildopts.get('vcs') or buildopts.get('svn')

    # Overrides from command line
    for optname in options.__dict__.keys():
        optval = getattr(options, optname, None)
        if optval is not None:
            buildopts[optname] = optval

    # Special case for working_directory being TEMP
    if buildopts['working_directory'].upper() == 'TEMP':
        buildopts['working_directory'] = (tempfile.mkdtemp(prefix='osg-build-'))
        log.debug('Working directory is %s', buildopts['working_directory'])

    # Special case for cache_prefix being AFS or VDT
    if buildopts['cache_prefix'].upper() == 'AFS':
        buildopts['cache_prefix'] = AFS_CACHE_PREFIX
    elif buildopts['cache_prefix'].upper() == 'VDT':
        buildopts['cache_prefix'] = WEB_CACHE_PREFIX
    elif buildopts['cache_prefix'].upper() == 'AUTO':
        if os.path.exists(AFS_CACHE_PATH):
            buildopts['cache_prefix'] = AFS_CACHE_PREFIX
        else:
            buildopts['cache_prefix'] = WEB_CACHE_PREFIX

    # If nothing has set targetopts_by_dver, set it here
    if not buildopts.get('targetopts_by_dver', None):
        buildopts['targetopts_by_dver'] = dict()
        for dver in DVERS:
            buildopts['targetopts_by_dver'][dver] = DEFAULT_BUILDOPTS_BY_DVER[dver].copy()

    # Which distro versions are we building for? If not specified on the
    # command line, either build for all (koji) or the dver of the local machine
    # (others)
    enabled_dvers = getattr(options, 'enabled_dvers', None)
    if not enabled_dvers:
        if task == 'koji':
            if buildopts['repo'] in DEFAULT_DVERS_BY_REPO:
                buildopts['enabled_dvers'] = set(DEFAULT_DVERS_BY_REPO[buildopts['repo']])
            else:
                buildopts['enabled_dvers'] = set(DEFAULT_DVERS)
        else:
            machine_dver = utils.get_local_machine_dver() or FALLBACK_DVER
            buildopts['enabled_dvers'] = set([machine_dver])

    # Hack: make --mock-config on command line override
    # --mock-config-from-koji from config file
    if getattr(options, 'mock_config', None) is not None:
        buildopts['mock_config_from_koji'] = None

    # If set, --mock-config-from-koji overrides --mock-config
    if buildopts.get('mock_config_from_koji', None):
        buildopts['mock_config'] = None

    if kojiinter and buildopts['vcs'] is None and task == 'koji':
        if buildopts['scratch']:
            buildopts['vcs'] = False
        else:
            buildopts['vcs'] = True

    return buildopts
# end of get_buildopts()


def print_version_and_exit():
    """Print version and exit"""
    scriptpath = utils.shell_quote(os.path.dirname(os.path.realpath(sys.argv[0])))
    out, ret = "", 0
    try:
        out, ret = utils.sbacktick("cd %s && git describe --tags 2>/dev/null" % scriptpath,
                                   err2out=False, shell=True)
    except OSError:
        pass
    if not ret:
        print("osg-build git " + out)
    else:
        print("osg-build " + __version__)
    sys.exit(0)


def verify_release_in_targetopts_by_dver(targetopts_by_dver):
    """Verify that the values for distro_tag, koji_target and koji_tag are
    consistent. If consistent, return the dver; else, return None.
    Also return None if none of the values are specified.
    """
    redhat_release, distro_tag, koji_target, koji_tag = (
        targetopts_by_dver.get('redhat_release'),
        targetopts_by_dver.get('distro_tag'),
        targetopts_by_dver.get('koji_target'),
        targetopts_by_dver.get('koji_tag'))
    dver = 'el' + str(redhat_release)
    if koji_tag == 'TARGET': # HACK
        koji_tag = None
    def same_or_none2(a, b):
        return (a == b) or a is None or b is None
    def same_or_none(*args):
        return all((same_or_none2(args[x], args[y]) for x in range(len(args)) for y in range(x, len(args))))

    # Verify consistency
    dist_dver = get_dver_from_string(distro_tag)
    target_dver = get_dver_from_string(koji_target)
    tag_dver = get_dver_from_string(koji_tag)

    if not same_or_none(dver, dist_dver, tag_dver, target_dver):
        return None

    return dver or dist_dver or target_dver or tag_dver


def guess_pkg_dir(start_dir):
    guess_dir = os.path.realpath(os.path.expanduser(start_dir))
    if os.path.basename(guess_dir) == 'osg' or os.path.basename(guess_dir) == 'upstream':
        return os.path.dirname(guess_dir)
    guess_dirlist = guess_dir.split('/')
    if guess_dirlist[0] == '':
        guess_dirlist[0] = '/'
    for udir in [WD_RESULTS, WD_PREBUILD, WD_UNPACKED, WD_UNPACKED_TARBALL, WD_QUILT]:
        try:
            idx = guess_dirlist.index(udir)
            return os.path.join(*guess_dirlist[0:idx])
        except ValueError:
            continue

    return guess_dir


if __name__ == '__main__':
    sys.exit(main(sys.argv))

