"""osg build script

Wishlist:
* Better message printing. Should distinguish between when to use logging.*
  versus print.
* Better support for multiple packages. If a single build runs into an error,
  the user should be given a choice to skip that package. Some kind of report
  afterward showing successful/failed packages should be printed.
  Should be some sanity checks on all packages before any work on any of them
  is done.
* Better exceptions. Should review where they should _really_ be used.
* Have unit tests for every chunk of code I change.
"""
# pylint: disable=W0614,W0602,C0103
import logging
from optparse import OptionGroup, OptionParser, OptionValueError
import re
import os
import sys
import tempfile
import ConfigParser

from osgbuild.constants import *
from osgbuild.error import UsageError
from osgbuild import koji
from osgbuild import mock
from osgbuild import srpm
from osgbuild import svn
from osgbuild import utils

__version__ = '@VERSION@'

# logging. Can't use root logger because its loglevel can't be changed once set
log = logging.getLogger('osgbuild')
log.setLevel(logging.INFO)
log_consolehandler = logging.StreamHandler()
log_consolehandler.setLevel(logging.INFO)
log_formatter = logging.Formatter("%(levelname)s:osg-build:%(message)s")
log_consolehandler.setFormatter(log_formatter)
log.addHandler(log_consolehandler)

#-------------------------------------------------------------------------------
# Main function
#-------------------------------------------------------------------------------
def main(argv):
    """Main function."""

    buildopts, package_dirs, task = init(argv)
    koji_obj = None
    mock_obj = None

    # checks
    if task == 'allbuild' or (task == 'koji' and buildopts['svn']):
        # verify svn working dirs
        for pkg in package_dirs:
            if not svn.verify_working_dir(pkg):
                print "Exiting"
                return 1
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

    if (task == 'koji' and not buildopts['scratch'] and
            not buildopts['svn']):
        log.warning("Non-scratch Koji builds should be from SVN!")

    # main loop 
    for pkg in package_dirs:
        if task == 'allbuild':
            # allbuild is special--we ignore most options and use
            # a slightly different set of defaults.
            for rel in REDHAT_RELEASES:
                rel_buildopts = buildopts.copy()
                rel_buildopts.update(
                    DEFAULT_BUILDOPTS_BY_REDHAT_RELEASE[rel])
                for key in ALLBUILD_ALLOWED_OPTNAMES:
                    rel_buildopts[key] = buildopts[key]

                svn.koji(pkg, koji.Koji(rel_buildopts), rel_buildopts)

        else:
            targetparams = buildopts['targetparams']
            for rel in targetparams:
                rel_buildopts = buildopts.copy()
                rel_buildopts.update(targetparams[rel])

                mock_obj = None
                koji_obj = None
                if (task == 'koji' or
                        (task == 'mock' and
                         rel_buildopts['mock_config_from_koji'])):
                    koji_obj = koji.Koji(rel_buildopts)
                if task == 'mock':
                    mock_obj = mock.Mock(rel_buildopts, koji_obj)
                
                if buildopts['svn'] and task == 'koji':
                    svn.koji(pkg, koji_obj, rel_buildopts)

                else:
                    builder = srpm.SRPMBuild(pkg,
                                             rel_buildopts,
                                             mock_obj=mock_obj,
                                             koji_obj=koji_obj)
                    builder.maybe_autoclean()
                    getattr(builder, task)()
    # end of main loop

    return 0
# end of main()


def init(argv):
    """Initialization. Get build options and packages.

    """
    options, args, optnames = parse_cmdline_args(argv)

    if options.version:
        print_version_and_exit()
    # if loglevel is passed on the command line, make it take into effect
    # immediately so we see debug messages in get_buildopts
    if options.loglevel:
        set_loglevel(options.loglevel)

    task = get_task(args)
    buildopts = get_buildopts(options, optnames, task)
    set_loglevel(buildopts.get('loglevel', 'INFO'))

    if len(args) < 2:
        raise UsageError('Need package directories for this task!')

    package_dirs = args[1:]

    return (buildopts, package_dirs, task)
# end of init()


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
    optnames:   a list of the option names (valid attributes of 'options')

    """
    parser = OptionParser("""
   %prog TASK PACKAGE1 <PACKAGE2..n> [options]

Valid tasks are:
allbuild     Build out of SVN using koji for all supported platforms into the
             default tags/targets for each platform
koji         Build using koji
lint         Discover potential package problems using rpmlint
mock         Build using mock(1) on the local machine
prebuild     Preprocess the package, create SRPM to be submitted, and stop
prepare      Use rpmbuild -bp to unpack and patch the package
quilt        Preprocess the package and run 'quilt setup' on the spec file to
             unpack the source files and prepare a quilt(1) series file.
rpmbuild     Build using rpmbuild(8) on the local machine
""")
    parser.add_option(
        "-a", "--autoclean", action="store_true",
        help="Clean out the following directories before each build: "
        "'%s', '%s', '%s', '%s'" % (
            WD_RESULTS, WD_PREBUILD, WD_UNPACKED, WD_UNPACKED_TARBALL))
    parser.add_option(
        "--no-autoclean", action="store_false", dest="autoclean",
        help="Disable autoclean")
    parser.add_option(
        "-c", "--cache-prefix",
        help="The prefix for the software cache to take source files from. "
        "The following special caches exist: "
        "AFS (%s), VDT (%s), and AUTO (AFS if avaliable, VDT if not). "
        "The default cache is AUTO." % (AFS_CACHE_PREFIX, WEB_CACHE_PREFIX))
    parser.add_option(
        "-C", "--config-file",
        help="The file to get configuration for this script.")
    parser.add_option(
        "--el5", action="callback", callback=parser_targetparams_callback,
        type=None,
        dest="redhat_release",
        help="Build for RHEL 5-compatible. Equivalent to --redhat-release=5")
    parser.add_option(
        "--el6", action="callback", callback=parser_targetparams_callback,
        type=None,
        dest="redhat_release",
        help="Build for RHEL 6-compatible. Equivalent to --redhat-release=6")
    parser.add_option(
        "--loglevel",
        help="The level of logging the script should do. "
        "Valid values are: DEBUG,INFO,WARNING,ERROR,CRITICAL")
    parser.add_option(
        "-q", "--quiet", action="store_const", const="warning", dest="loglevel",
        help="Display less information. Equivalent to --loglevel=warning")
    parser.add_option(
        "--redhat-release", action="callback",
        callback=parser_targetparams_callback,
        dest="redhat_release",
        type="string",
        help="The version of the distribution to build the package for. "
        "Valid values are: 5 (for RHEL 5), 6 (for RHEL 6). "
        "If not specified, will build for all releases (koji task) or the "
        "platform you are running this on (other tasks)")
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
        "is used.")

    prebuild_group = OptionGroup(parser,
                                 "prebuild task options")
    prebuild_group.add_option(
        "--full-extract", action="store_true",
        help="Fully extract all source files.")

    rpmbuild_mock_group = OptionGroup(parser, 
                                      "rpmbuild and mock task options")
    rpmbuild_mock_group.add_option(
        "--distro-tag",
        help="The distribution tag to append to the end of the release. "
        "(Default: osg.el5 or osg.el6, depending on --redhat-release)")
    rpmbuild_mock_group.add_option(
        "-t", "--target-arch",
        help="The target architecture to build for ")

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
        help="The location of the mock config file. "
        "defaults to AUTO to use an autogenerated file "
        "recommended for OSG builds")
    mock_group.add_option(
        "--mock-config-from-koji",
        help="Use a mock config based on a koji buildroot (build tag, "
        "such as el5-osg-build).")

    koji_group = OptionGroup(parser,
                             "koji task options")
    koji_group.add_option(
        "--dry-run", action="store_true",
        help="Do not invoke koji, only show what would be done.")
    koji_group.add_option(
        "-k", "--kojilogin", "--koji-login", dest="kojilogin",
        help="The login you use for koji (most likely your CN, e.g."
        "'Matyas Selmeci 564109')")
    koji_group.add_option(
        "--koji-target",
        action="callback",
        callback=parser_targetparams_callback,
        type="string",
        help="The koji target to use for building. Default: "
        "el5-osg or el6-osg depending on --redhat-release")
    koji_group.add_option(
        "--koji-tag",
        action="callback",
        callback=parser_targetparams_callback,
        type="string",
        help="The koji tag to add packages to. The special value TARGET "
        "uses the destination tag defined in the koji target. Default: "
        "el5-osg or el6-osg depending on --redhat-release")
    koji_group.add_option(
        "--koji-target-and-tag", "--ktt",
        action="callback",
        callback=parser_targetparams_callback,
        type="string",
        dest="ktt",
        metavar='ARG',
        help="Specifies both the koji tag to add packages to and the target "
        "to use for building. '--ktt ARG' is equivalent to '--koji-target ARG "
        " --koji-tag ARG'.")
    koji_group.add_option(
        "--koji-wrapper", action="store_true", dest="koji_wrapper",
        help="Use the 'osg-koji' koji wrapper. (Default)")
    koji_group.add_option(
        "--no-koji-wrapper", action="store_false", dest="koji_wrapper",
        help="Do not use the 'osg-koji' koji wrapper, even if found.")
    koji_group.add_option(
        "--no-wait", "--nowait", action="store_true", dest="no_wait",
        help="Do not wait for the build to finish")
    koji_group.add_option(
        "--wait", action="store_false", dest="no_wait",
        help="Wait for the build to finish")
    koji_group.add_option(
        "--regen-repos", action="store_true",
        help="Perform a regen-repo on the build and destination repos after "
        "each koji build. Allows doing builds that depend on each other. "
        "Use sparingly, as this slows down builds and uses more disk space on "
        "koji-hub.")
    koji_group.add_option(
        "--scratch", action="store_true",
        help="Perform a scratch build")
    koji_group.add_option(
        "--no-scratch", "--noscratch", action="store_false", dest="scratch",
        help="Do not perform a scratch build")
    koji_group.add_option(
        "--svn", action="store_true",
        help="Build package directly from SVN "
        "(default for non-scratch builds)")
    koji_group.add_option(
        "--no-svn", "--nosvn", action="store_false", dest="svn",
        help="Do not build package directly from SVN "
        "(default for scratch builds)")

    optnames = [x.dest for x in parser.option_list if x.dest is not None]
    for grp in [prebuild_group, rpmbuild_mock_group, mock_group, koji_group]:
        parser.add_option_group(grp)
        optnames.extend([x.dest for x in grp.option_list if x.dest is not None])
    optnames = set(optnames)

    options, args = parser.parse_args(argv[1:])

    return (options, args, optnames)
# end of parse_cmdline_args()


def get_el_release_from_string(s):
    """Get the EL major version from a string containing it.
    Return None if not found."""
    match = re.search(r'\bel(\d+)\b', s)
    if match is not None:
        return match.group(1)
    else:
        return None


def parser_targetparams_callback(option, opt_str, value, parser, *args,
                                **kwargs):
    """Handle options in the 'targetparams' set, such as --koji-tag,
    --redhat-release, etc. targetparams is a dict keyed by redhat release
    and the values are dicts containing the options to use for building
    with that release. For example, targetparams['5']['koji_tag'] is the
    koji tag to use when building for RHEL 5.

    Figure out the redhat release that an option is meant for from the
    value, and set that option in the dict for that redhat release.

    Also handle --ktt (--koji-tag-and-target), which sets both koji_tag
    and koji_target.

    """
    # for options that have aliases, option.dest gives us the
    # canonical name of the option (as opposed to opt_str, which gives us
    # what the user typed in)
    opt_name = option.dest

    if not getattr(parser.values, 'targetparams', None):
        parser.values.targetparams = dict()
    targetparams = parser.values.targetparams
    rel = None
    if value is None: value = ''
    if opt_name == 'redhat_release':
        if opt_str == '--el5':
            rel = '5'
        elif opt_str == '--el6':
            rel = '6'
        elif opt_str == '--redhat-release':
            rel = value
    else:
        rel = get_el_release_from_string(value)

    if not rel:
        raise OptionValueError('Unable to determine redhat release '
                               'in parameter %s: %s' % (opt_str, value))

    targetparams.setdefault(rel,
        DEFAULT_BUILDOPTS_BY_REDHAT_RELEASE[rel].copy())

    if opt_name == 'ktt':
        targetparams[rel]['koji_tag'] = value
        targetparams[rel]['koji_target'] = value
    elif opt_name != 'redhat_release':
        targetparams[rel][opt_name] = value
    if not verify_release_in_targetparams(targetparams[rel]):
        raise OptionValueError('Inconsistent redhat release '
                               'in parameter %s: %s' % (opt_str, value))
# end of parser_targetparams_callback()
    


def get_task(args):
    """Return the task the user specified in the first positional argument,
    if it is a valid task. Allow the user to enter only the first few
    characters if the task is unambiguous. Raise UsageError if task is
    unspecified, invalid, or ambiguous.

    """
    if len(args) < 1:
        raise UsageError('Need task!')
    task = args[0]

    valid_tasks = ['allbuild', 'koji', 'lint', 'mock', 'prebuild', 'prepare',
                   'quilt', 'rpmbuild']

    matching_tasks = [x for x in valid_tasks if x.startswith(task)]

    if len(matching_tasks) > 1:
        raise UsageError('Ambiguous task. Matching tasks are:' +
                         ", ".join(matching_tasks))
    elif not matching_tasks:
        raise UsageError('No valid task')
    else:
        real_task = matching_tasks[0]

    return real_task
# end of get_task()


def get_buildopts(options, optnames, task):
    """Return a dict of the build options to use, based on the config file and
    command-line arguments.

    """
    # Hack: if the task is "allbuild", use a different set of
    # defaults, ignore the config file, and most options.
    if task == 'allbuild':
        buildopts = ALLBUILD_BUILDOPTS.copy()
        for optname in ALLBUILD_ALLOWED_OPTNAMES:
            optval = getattr(options, optname, None)
            if optval is not None:
                buildopts[optname] = optval
        return buildopts

    # otherwise...
    buildopts = DEFAULT_BUILDOPTS_COMMON.copy()

    cfg_items = read_config_file(options.config_file)
    buildopts.update(cfg_items)

    # Overrides from command line
    for optname in optnames:
        optval = getattr(options, optname, None)
        if optval is not None:
            buildopts[optname] = optval

    # Special case for working_directory being TEMP
    if buildopts['working_directory'].upper() == 'TEMP':
        buildopts['working_directory'] = (
            tempfile.mkdtemp(prefix='osg-build-'))
        log.debug('Working directory is %s',
                  buildopts['working_directory'])

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

    # TODO lots of hacks here
    targetparams = getattr(options, 'targetparams', None)
    if not targetparams:
        if task == 'koji':
            buildopts['targetparams'] = (
                DEFAULT_BUILDOPTS_BY_REDHAT_RELEASE.copy())
        else:
            rh_rel = get_local_machine_rh_rel()
            buildopts['targetparams'] = {
                rh_rel: DEFAULT_BUILDOPTS_BY_REDHAT_RELEASE[rh_rel].copy()}
    else:
        buildopts['targetparams'] = targetparams

    # Hack: make --mock-config on command line override
    # --mock-config-from-koji from config file
    if options.mock_config is not None:
        buildopts['mock_config_from_koji'] = None

    # If set, --mock-config-from-koji overrides --mock-config
    if buildopts['mock_config_from_koji']:
        buildopts['mock_config'] = None

    if buildopts['svn'] is None and task == 'koji':
        if buildopts['scratch']:
            buildopts['svn'] = False
        else:
            buildopts['svn'] = True

    return buildopts
# end of get_buildopts()


def read_config_file(given_cfg_file=None):
    """Return a dict of items read from a config file. If given_cfg_file
    is None, uses one of the default config file locations.

    """
    cfg_file = None
    if given_cfg_file:
        cfg_file = given_cfg_file
    else:
        if os.path.exists(DEFAULT_CONFIG_FILE):
            cfg_file = DEFAULT_CONFIG_FILE
        else:
            log.debug("Didn't find default config at %s",
                      DEFAULT_CONFIG_FILE)
            if os.path.exists(ALT_DEFAULT_CONFIG_FILE):
                cfg_file = ALT_DEFAULT_CONFIG_FILE

    if cfg_file and os.path.isfile(cfg_file):
        try:
            cfg = ConfigParser.ConfigParser()
            cfg.read(cfg_file)
            log.debug("Read default config from %s", cfg_file)
            return cfg.items('options')
        except ConfigParser.Error, err:
            log.warning("Error reading configuration from %s: %s",
                        cfg_file, str(err))
    else:
        return {}

            
def print_version_and_exit():
    """Print version and exit"""
    # '@'+'VERSION'+'@' is so sed will leave it alone during 'make dist'
    if __version__ == '@' + 'VERSION' + '@':
        print "osg-build SVN"
        out, ret = utils.sbacktick("svn info " + sys.argv[0], err2out=True)
        if ret:
            print "no info"
        else:
            print "SVN info:\n" + out
    else:
        print "osg-build " + __version__
    sys.exit(0)


def verify_release_in_targetparams(targetparams):
    """Verify that the values for distro_tag, koji_target and koji_tag are
    consistent. If consistent, return the release; else, return None.
    Also return None if none of the values are specified.
    """
    redhat_release, distro_tag, koji_target, koji_tag = (
        targetparams.get('redhat_release'),
        targetparams.get('distro_tag'),
        targetparams.get('koji_target'),
        targetparams.get('koji_tag'))
    def same_or_none(a, b):
        return (a == b) or a is None or b is None
    def same_or_none4(a, b, c, d):
        return (same_or_none(a, b) and same_or_none(a, c) and
                same_or_none(a, d) and same_or_none(b, c) and
                same_or_none(b, d) and same_or_none(c, d))

    # Verify consistency
    dist_rel = get_el_release_from_string(distro_tag)
    target_rel = get_el_release_from_string(koji_target)
    tag_rel = get_el_release_from_string(koji_tag)

    if not same_or_none4(redhat_release, dist_rel, tag_rel, target_rel):
        return None

    rel = redhat_release or dist_rel or target_rel or tag_rel
    return rel


def get_local_machine_rh_rel():
    "Return the major redhat release of the local machine or None"
    redhat_release_contents = utils.slurp('/etc/redhat-release')
    try:
        match = re.search(r'release (\d)', redhat_release_contents)
        return match.group(1)
    except (TypeError, AttributeError):
        return None

if __name__ == '__main__':
    sys.exit(main(sys.argv))

