"""A package promotion script for OSG"""


import logging
import os
import re
import sys
from typing import List, Optional, Dict, Set, Tuple

from osgbuild.kojiinter import KojiHelper
from . import constants
from . import error
from . import osg_sign
from . import utils
from .osg_sign import SigningKey, SigningKeysConfig
from .utils import comma_join, printf, print_table, IniConfiguration, split_nvr
from optparse import OptionParser

log = logging.getLogger(__name__)


class KojiTagsAreMessedUp(Exception):
    """Raised when Koji tags are in an inconsistent or unusable state.

    This can happen if one half of a route does not exist for a given dver
    (e.g. osg-3.1-el5-development exists but not osg-3.1-el5-testing).
    """


class Route(object):
    """Information about a promotion route"""
    def __init__(self, from_tag_hint, to_tag_hint, repotag, dvers, extra_dvers, required_keys=None):
        # type: (str, str, str, List[str], List[str], List[SigningKey]) -> None
        self.from_tag_hint = from_tag_hint
        self.to_tag_hint = to_tag_hint
        self.repotag = repotag
        self.dvers = dvers
        self.extra_dvers = extra_dvers
        self.required_keys = required_keys or []

    def required_keys_for_dver(self, dver):
        # type: (str) -> List[SigningKey]
        """The key ids of the keys required for the given dver for this route"""
        return [x for x in self.required_keys if dver in x.dvers]


class Build(object):
    def __init__(self, name, version, release_no_dist, repotag, dver):
        self.name = name
        self.version = version
        self.release_no_dist = release_no_dist
        self.repotag = repotag
        self.dver = dver

    @staticmethod
    def new_from_nvr(nvr):
        name, version, release = split_nvr(nvr)
        release_no_dist, repotag, dver = split_repotag_dver(release)

        return Build(name, version, release_no_dist, repotag, dver)

    @property
    def vr_no_dist(self):
        return '-'.join([self.version, self.release_no_dist])

    @property
    def vr(self):
        return '.'.join([self.vr_no_dist, self.dist]).strip('.')

    @property
    def nvr(self):
        return '-'.join([self.name, self.vr])

    @property
    def nvr_no_dist(self):
        return '-'.join([self.name, self.vr_no_dist])

    @property
    def dist(self):
        return '.'.join([self.repotag, self.dver]).strip('.')


class Reject(object):
    REASON_DISTINCT_ACROSS_DISTS = "%(pkg_or_build)s: Matching build versions distinct across dist tags"
    REASON_NOMATCHING_FOR_DIST = "%(pkg_or_build)s: No matching build for dist %(dist)s"
    REASON_MISSING_REQUIRED_SIGNATURE = "%(pkg_or_build)s: RPM %(rpm)s missing required signature (%(signing_keys)s)"

    def __init__(self, pkg_or_build, reason, details=None):
        # type: (str, str, Optional[Dict]) -> None
        if not details:
            details = {}
        self.pkg_or_build = pkg_or_build
        self.reason = reason
        self.details = {
            'pkg_or_build': self.pkg_or_build,
            'dist': "?",
            'rpm': "?",
            'signing_keys': [],
        }
        self.details.update(details)

    def __str__(self):
        details = self.details.copy()
        details['signing_keys'] = " or ".join(str(x) for x in details['signing_keys'])
        return self.reason % details

    def __lt__(self, other):
        return ((self.pkg_or_build, self.details['dist'], self.reason) <
                (other.pkg_or_build, other.details['dist'], other.reason))

    def __repr__(self):
        return "Reject(%r, %r, %r)" % (self.pkg_or_build, self.reason, self.details)


class Configuration(IniConfiguration):
    def __init__(self, inifiles, signing_keys_config: SigningKeysConfig):
        super().__init__(inifiles)

        self.signing_keys_config = signing_keys_config
        self.signing_keys_by_name = signing_keys_config.signing_keys_by_name

        route_sections = [sec for sec in self.cp.sections() if sec.startswith('route ')]
        self.routes = self.parse_routes(route_sections, self.signing_keys_by_name)
        self.aliases = self.parse_aliases(self.routes)

    def parse_routes(self, route_sections, signing_keys):
        # type: (List[str], Dict[str, SigningKey]) -> Dict[str, Route]
        """Parse the 'route X' sections of the config file

        A section called "route X" creates a route named "X".
        Required attributes in a route section are:
        - from_tag_hint: the name of the koji tag to promote from, with '%s'
          where the dver would be
        - to_tag_hint: the name of the koji tag to promote to, with '%s' where
          the dver would be
        - repotag: the 'repo' part of the dist tag, e.g. 'osg33' for a dist tag
          like '.osg33.el5'
        - dvers: a comma or space separated list of distro versions (dvers)
          supported by default for the tags in the route, e.g. "el5 el6"
        The optional attributes are:
        - extra_dvers: a comma or space separated list of dvers that are supported
          by the tags in the route but should not be on by default
        - required_keys: a comma or space separated list of signing key names;
          if present, the packages being promoted must be signed by one of them.
          There must be a key section corresponding to each key.

        """
        routes = {}
        for sec in route_sections:
            routename = sec.split(None, 1)[1]
            from_tag_hint = self.config_safe_get(sec, 'from')
            to_tag_hint = self.config_safe_get(sec, 'to')
            repotag = self.config_safe_get(sec, 'repotag')
            dvers = self.config_safe_get_list(sec, 'dvers')
            extra_dvers = self.config_safe_get_list(sec, 'extra_dvers')
            required_keys = self.config_safe_get_list(sec, 'required_keys')

            errors = []
            if not from_tag_hint:
                errors.append("'from' not provided or empty")
            if not to_tag_hint:
                errors.append("'to' not provided or empty")
            if not repotag:
                errors.append("'repotag' not provided or empty")
            if not dvers:
                errors.append("'dvers' not provided or empty")
            required_key_objs = []
            for rk in required_keys:
                if rk in signing_keys:
                    required_key_objs.append(signing_keys[rk])
                else:
                    errors.append("unknown required_key %r" % rk)
            if errors:
                raise error.ConfigErrors("Section %r" % sec, errors)

            routes[routename] = Route(from_tag_hint,
                                      to_tag_hint,
                                      repotag,
                                      dvers,
                                      extra_dvers,
                                      required_key_objs)
        return routes

    def parse_aliases(self, routes):
        # type: (Dict[str, Route]) -> Dict[str, List[str]]
        """Parse an 'aliases' section.

        A section called "aliases" defines alternate names for a route.
        The key of each attribute in the section is the new name, and the value
        is the old name, e.g. "testing=3.2-testing".  Aliases to aliases cannot be
        defined.

        """
        if 'aliases' not in self.cp:
            return {}
        aliases = {}
        errors = []
        for newname, target in self.cp.items('aliases'):
            routelist = self._parse_list_str(target)
            for route in routelist:
                if route not in routes:
                    errors.append("Alias %s to %s failed: route named %s is not defined" % (newname, target, route))
                    break
            else:
                aliases[newname] = routelist
        if errors:
            raise error.ConfigErrors("Aliases", errors)
        return aliases

    def matching_route_names(self, route_or_alias):
        if route_or_alias in self.routes:
            return [route_or_alias]
        elif route_or_alias in self.aliases:
            return self.aliases[route_or_alias]
        return []

    def matching_routes(self, route_or_alias):
        names = self.matching_route_names(route_or_alias)
        return [self.routes[n] for n in names]

    @property
    def all_names(self):
        return list(self.routes.keys()) + list(self.aliases.keys())

    @property
    def all_dvers(self):
        dvers = set()
        for route in self.routes.values():
            dvers.update(route.dvers)
            dvers.update(route.extra_dvers)
        return dvers



#
# Utility functions
#


def split_repotag_dver(build, known_repotags=None):
    """Split out the dist tag from the NVR of a build, returning a tuple
    containing (NVR (without dist tag), repo tag, dver).
    For example, split_repotag_dver("foobar-1-1.osg32.el5") returns
    ("foobar-1-1", "osg32", "el5").
    The empty string is returned for any of the components that aren't present.

    Since the dist tag isn't a well-defined entity, I'm using the following
    heuristic to distinguish it:
        1. If the dist tag exists, it's at the end of the release.
            (only known exception: gridsite-1.7.15-4.osg.3. This is not
            handled, but it's not worth the extra code)
        2. If the dver is in the release, it is at the end of the dist tag.
        3. The dist tag contains at most 2 components, separated by '.'
    If known_repos is specified (as a list), then the repo component must be
    one of the strings in that list. Otherwise, the repo component must start
    with [a-z]. This is a workaround to prevent misidentifying the repo
    tag on a release like "1.11".

    """
    build_no_dist = build
    repotag = ""
    dver = ""

    build_no_dist_pat = r"(?P<build_no_dist>.+)"
    repotag_pat = r"(?P<repotag>[a-z]\w+)"
    dver_pat = r"(?P<dver>el\d+)"
    if known_repotags is not None:
        repotag_pat = r"(?P<repotag>" + "|".join(known_repotags) + ")"

    # order matters since later patterns are less specific and would match more
    pat_1_repotag_and_dver = re.compile(build_no_dist_pat + r"\." + repotag_pat + r"\." + dver_pat + "$")
    pat_2_dver_only = re.compile(build_no_dist_pat + r"\." + dver_pat + "$")
    pat_3_repotag_only = re.compile(build_no_dist_pat + r"\." + repotag_pat + "$")

    match = (pat_1_repotag_and_dver.match(build) or
             pat_2_dver_only.match(build) or
             pat_3_repotag_only.match(build))

    if match:
        groupdict = match.groupdict()
        build_no_dist, repotag, dver = groupdict['build_no_dist'], groupdict.get('repotag', ''), groupdict.get('dver', '')

    return build_no_dist, repotag, dver


def _bulletedlist(lst, prefix=" - "):
    return prefix + ("\n"+prefix).join(str(x) for x in sorted(lst))


class Promoter(object):
    """For promoting sets of packages.
    Usage is to add packages or builds via add_promotion and then call
    do_promotions to actually promote.
    do_promotions should not be called twice.

    """
    def __init__(self, kojihelper, route_dvers_pairs):
        """kojihelper is an instance of KojiHelper. routes is a list of Route objects. dvers is a list of strings.
        """
        self.tag_pkg_args = {}
        self.rejects = []
        self.kojihelper = kojihelper
        self.route_dvers_pairs = route_dvers_pairs
        self.repotags = set(route.repotag for route, _ in self.route_dvers_pairs)

    def add_promotion(self, pkg_or_build, ignore_rejects=False):
        """Run get_builds() for 'pkg_or_build', using from_tag_hint as the
        tag hint.
        Returns nothing; builds to promote are added to tag_pkg_args, which
        is a dict keyed by tag (actual tag, not tag hint) of koji builds that
        should be added to that tag.

        """
        tag_build_pairs = []
        for route, dvers in self.route_dvers_pairs:
            builds = self.get_builds(route, dvers, pkg_or_build, ignore_rejects)
            for build_dver in builds:
                to_tag = route.to_tag_hint % build_dver
                tag_build_pairs.append((to_tag, builds[build_dver]))

        if not ignore_rejects and self.any_distinct_across_dists(tag_build_pairs):
            self.rejects.append(Reject(pkg_or_build, Reject.REASON_DISTINCT_ACROSS_DISTS))
        else:
            for tag, build in tag_build_pairs:
                self.tag_pkg_args.setdefault(tag, [])
                self.tag_pkg_args[tag].append(build)

    def _get_build(self, tag_hint, repotag, dver, pkg_or_build):
        """Get a single build (as a Build object) out of the tag given by
        tag_hint % dver that matches pkg_or_build. This only returns builds
        where the Release field contains a dist tag with both a repo and a dver
        (e.g. osg31.el5).

        If given a build where the dist tag does not match the repo and/or
        dver, will strip off the dist tag, put on the one that is appropriate
        for the repo and dver, and return _that_ build.

        If given a package (i.e. just a name and not an NVR, then the latest
        build for the tag is returned (latest meaning most recently added to
        that tag)).

        Return None if no matching build was found.

        """
        tag = self._get_valid_tag_for_dver(tag_hint, dver)
        pkg_or_build_no_dist = split_repotag_dver(pkg_or_build, self.repotags)[0]
        # Case 1: pkg_or_build is a build, in which case take off its dist tag
        # and put the dist tag specified dist tag on, then find a build for that.
        build_nvr_1 = self.kojihelper.get_build_in_tag(tag, ".".join([pkg_or_build_no_dist, repotag, dver]))
        # Case 2: pkg_or_build is a package, in which case putting a dist tag
        # on doesn't help--just find the latest build in the tag.
        build_nvr_2 = self.kojihelper.get_build_in_tag(tag, pkg_or_build_no_dist)

        build_nvr = build_nvr_1 or build_nvr_2 or None

        if build_nvr:
            build_obj = Build.new_from_nvr(build_nvr)
            return build_obj

    def get_builds(self, route, dvers, pkg_or_build, ignore_rejects=False):
        """Get a dict of builds keyed by dver for pkg_or_build.
        Uses _get_build to get the build matching pkg_or_build for the given
        route and all given dvers.

        If matching builds are found for one but not all dvers then all builds
        will be rejected, unless ignore_rejects is True. Rejections are added
        to self.rejects.

        In case of a rejection (or no matching packages found at all), an
        empty dict is returned.

        """
        # TODO Both this and add_promotion currently handle rejections.
        # I think this should be refactored such that: get_builds goes through
        # all routes, not just one, and rejection handling should be done in
        # add_promotion.
        tag_hint = route.from_tag_hint
        repotag = route.repotag
        builds = {}
        # Find each build for all dvers matching pkg_or_build
        for dver in dvers:
            dist = "%s.%s" % (repotag, dver)
            build = self._get_build(tag_hint, repotag, dver, pkg_or_build)
            if not build:
                if not ignore_rejects:
                    self.rejects.append(
                        Reject(pkg_or_build,
                               Reject.REASON_NOMATCHING_FOR_DIST,
                               details={'dist': dist}))
                    return {}
                else:
                    continue
            builds[dver] = build

        return builds

    def any_distinct_across_dists(self, tag_build_pairs):
        distinct_nvrs = set()
        for _, build in tag_build_pairs:
            distinct_nvrs.add(build.nvr_no_dist)
        return len(distinct_nvrs) > 1

    def _get_valid_tag_for_dver(self, tag_hint, dver):
        """Find tag_hint % dver in koji's list of tags (as queried via
        kojihelper). Return the tag if found; raise KojiTagsAreMessedUp if
        not.

        RouteDiscovery should have already validated the route being used, but
        this is an extra layer of protection to catch mistakes.

        """
        tag = tag_hint % dver
        if not self.kojihelper.get_first_tag('exact', tag):
            raise KojiTagsAreMessedUp("Can't find tag %s in koji" % tag)
        return tag

    def do_promotions(self, dry_run=False, regen=False):
        """Tag all builds selected to be tagged in self.tag_pkg_args.
        self.tag_pkg_args is a list of (tag, [builds]) pairs.

        If dry_run is True, no actual tagging happens.  If
        regen is True, then each repository that gets modified will be
        regenerated after all tagging is done.

        Will not attempt to tag builds already in the destination tag.

        Return builds successfully promoted.

        """
        printf("--- Tagging builds")
        tasks = dict()
        for tag, builds in self.tag_pkg_args.items():
            for build in builds:
                try:
                    # Make sure the build isn't already in tag
                    if build.nvr in self.kojihelper.get_tagged_builds(tag):
                        printf("Skipping %s, already in %s", build.nvr, tag)
                        continue
                except KeyError:
                    pass

                # Launch the builds
                if not dry_run:
                    task_id = self.kojihelper.tag_build(tag, build.nvr)
                    tasks[task_id] = (tag, build)
                else:
                    printf("tagBuild('%s', '%s')", tag, build.nvr)

        promoted_builds = dict(self.tag_pkg_args)
        if not dry_run:
            promoted_builds = self.watch_builds(tasks)

            if regen:
                print("--- Regenerating repos")
                self.kojihelper.regen_repos(tags_to_regen=self.tag_pkg_args.keys())
        return promoted_builds

    def watch_builds(self, tasks):
        """Helper for do_promotions(). Watch builds being promoted and return
        successful ones.
        'tasks' is a dict of koji tasks keyed by the koji task ID
        Promoted builds are returned as a dict keyed by 'build_no_dver' (i.e.
        the NVR with the dver chopped off), containing dicts keyed by dver,
        containing the build (i.e. NVR as string).

        """
        self.kojihelper.watch_tasks(list(tasks.keys()))

        promoted_builds = {}
        for task_id, (tag, build) in tasks.items():
            if self.kojihelper.get_task_state(task_id) == 'CLOSED':
                promoted_builds.setdefault(tag, [])
                promoted_builds[tag].append(build)
            else:
                printf("* Error promoting build %s", build.nvr)

        return promoted_builds


#
# JIRA writing
#


def write_old_jira(kojihelper, promoted_builds, routes, out=None):
    """Write input suitable for embedding into a JIRA ticket (old syntax)
    """
    # Format
    # | build-1.2.osg31.el5 | TAG |
    out = out or sys.stdout
    out.write("*Promotions*\n")

    build_tag_table = [[build, tag] for tag in promoted_builds for build in promoted_builds[tag]]
    build_tag_table.sort(key=lambda x: x[0].nvr)

    nvrs_no_dist = set()
    table_str = "|| Build || Tag ||\n"
    for build, tag in build_tag_table:
        uri = kojihelper.get_build_uri(build.nvr)
        table_str += "| [%s|%s] | %s |\n" % (build.nvr, uri, tag)
        nvrs_no_dist.add(build.nvr_no_dist)

    out.write("Promoted %s to %s\n" % (
        ", ".join(sorted(nvrs_no_dist)), ", ".join([x.to_tag_hint % "el*" for x in routes])))
    out.write(table_str)


def write_jira(kojihelper, promoted_builds, routes, out=None):
    """Write input suitable for pasting into a JIRA comment.
    """
    out = out or sys.stdout
    out.write("**Promotions**\n")

    build_tag_table = [[build, tag] for tag in promoted_builds for build in promoted_builds[tag]]
    build_tag_table.sort(key=lambda x: x[0].nvr)

    nvrs_no_dist = set()
    table_str = "**Build** | **Tag**\n"
    table_str += "--- | ---\n"
    for build, tag in build_tag_table:
        uri = kojihelper.get_build_uri(build.nvr)
        table_str += " [%s](%s) | %s\n" % (build.nvr, uri, tag)
        nvrs_no_dist.add(build.nvr_no_dist)

    out.write("Promoted %s to %s\n" % (
        ", ".join(sorted(nvrs_no_dist)), ", ".join([x.to_tag_hint % "el*" for x in routes])))
    out.write(table_str)


#
# Command line and main
#
def format_valid_routes(valid_routes):
    formatted = ""
    for route_name in sorted(valid_routes):
        route = valid_routes[route_name]
        dvers_list = comma_join(route.dvers)
        if route.extra_dvers:
            dvers_list += ', [%s]' % comma_join(route.extra_dvers)
        formatted += " - %-25s: %-31s -> %-31s (%s)\n" % (
            route_name,
            route.from_tag_hint % '*',
            route.to_tag_hint % '*',
            dvers_list
        )
    return formatted


def format_aliases(aliases):
    """ Return a pretty-printed string of the available aliases, for use in the help message.
    :param aliases: The aliases from a Configuration object
    :rtype: str
    """
    return "\n".join(
        [" - %-25s: %s" % (name, comma_join(aliases[name]))
         for name in sorted(aliases)]
    )


def parse_cmdline_args(configuration, argv):
    """
    :param configuration: A Configuration object.
                          We need the routes to build the various dver arguments
                          and the list of routes in the help text.
    :param argv: sys.argv
    :return: the options, the list of route names the user wants to use,
             and the list of packages or builds to promote
    """
    helpstring = "%prog -r|--route ROUTE... [options] <packages or builds>"
    helpstring += "\n\nThe following routes exist:\n"
    helpstring += format_valid_routes(configuration.routes)
    if configuration.aliases:
        helpstring += "\nThe following aliases to routes exist:\n"
        helpstring += format_aliases(configuration.aliases)

    all_dvers = configuration.all_dvers

    parser = OptionParser(helpstring)

    parser.add_option("--debug", dest="loglevel", action="store_const", const=logging.DEBUG,
                      help="Print debug messages")
    parser.add_option("-r", "--route", dest="routes", action="append",
                      help="The promotion route to use. May be specified multiple times. "
                      "Multiple routes may also be separated by commas")
    parser.add_option("-n", "--dry-run", action="store_true", default=False,
                      help="Do not promote, just show what would be done")
    parser.add_option("--ignore-rejects", dest="ignore_rejects", action="store_true", default=False,
                      help="Ignore rejections due to version mismatch between dvers or missing package for one dver")
    parser.add_option("--regen", default=False, action="store_true",
                      help="Regenerate repo(s) afterward")
    parser.add_option("-y", "--assume-yes", action="store_true", default=False,
                      help="Do not prompt before promotion")
    parser.set_default("loglevel", logging.INFO)
    for dver in all_dvers:
        parser.add_option("--%s-only" % dver,                action="store_const",  dest="only_dver",   const=dver,
                          default=None, help="Promote only %s builds" % dver)
        parser.add_option("--no-%s" % dver, "--no%s" % dver, action="append_const", dest="no_dvers",    const=dver,
                          default=[],   help="Do not promote %s builds, even if they are default for the route(s)" % dver)
        parser.add_option("--%s" % dver,                     action="append_const", dest="extra_dvers", const=dver,
                          default=[],   help="Promote %s builds if the route(s) support them" % dver)

    if len(argv) < 2:
        parser.print_help()
        sys.exit(2)

    options, pkgs_or_builds = parser.parse_args(argv[1:])

    wanted_routes = None
    if not options.routes:
        parser.error("You must specify a promotion route")
    else:
        try:
            wanted_routes = _get_wanted_routes(configuration, options.routes)
        except error.Error as err:
            parser.error(str(err))

    return options, wanted_routes, pkgs_or_builds


def starting_match(partial, choices):
    return [x for x in choices if x.startswith(partial)]


def _get_wanted_routes(configuration, route_args):
    matched_routes = set()

    expanded_routes = set()
    for arg in route_args:
        expanded_routes.update(arg.split(','))

    # User is allowed to specify the shortest unambiguous prefix of a route
    for arg in expanded_routes:
        if arg in configuration.all_names:
            # exact match
            matched_routes.update(configuration.matching_route_names(arg))
        else:
            matching_routes = starting_match(arg, configuration.all_names)
            if len(matching_routes) > 1:
                raise error.Error("Ambiguous route '%s'.\nMatching routes are: %s" % (arg, comma_join(matching_routes)))
            elif not matching_routes:
                raise error.Error("Invalid route '%s'." % arg)
            else:
                matched_routes.update(configuration.matching_route_names(matching_routes[0]))

    return matched_routes


def _print_route_dvers(routename, route):
    printf("The default dver(s) for %s are: %s", routename, comma_join(route.dvers))
    if route.extra_dvers:
        printf("The route optionally supports these dver(s): %s", comma_join(route.extra_dvers))


def main(argv=None):
    if argv is None:
        argv = sys.argv

    promoter_ini = utils.find_file(constants.PROMOTER_INI, strict=True)
    signing_keys_ini = utils.find_file(constants.SIGNING_KEYS_INI, strict=True)
    signing_keys_config = SigningKeysConfig(signing_keys_ini)
    configuration = Configuration([promoter_ini], signing_keys_config)

    options, wanted_routes, pkgs_or_builds = parse_cmdline_args(configuration, argv)
    if os.path.basename(argv[0]) == "osg-promote":  # HACK. Is there a better way to do this?
        logging.basicConfig(format=f"%(message)s", level=options.loglevel)
    log.setLevel(options.loglevel)
    valid_routes = configuration.routes
    route_dvers_pairs = _get_route_dvers_pairs(wanted_routes, valid_routes, options.extra_dvers, options.no_dvers,
                                               options.only_dver)

    kojihelper = KojiHelper(not options.dry_run)

    for route, dvers in route_dvers_pairs:
        printf("Promoting from %s to %s for dvers: %s",
               route.from_tag_hint % 'el*',
               route.to_tag_hint % 'el*',
               comma_join(dvers))
    printf("Examining the following packages/builds:\n%s", _bulletedlist(pkgs_or_builds))

    dvers = set()
    for _, x in route_dvers_pairs:
        dvers.update(x)
    promoter = Promoter(kojihelper, route_dvers_pairs)
    for pkgb in pkgs_or_builds:
        promoter.add_promotion(pkgb, options.ignore_rejects)

    if promoter.rejects:
        print("Rejected package or builds:\n%s" % _bulletedlist(promoter.rejects))
        print("Rejects will not be promoted!")
        if any(x.reason in (Reject.REASON_DISTINCT_ACROSS_DISTS, Reject.REASON_NOMATCHING_FOR_DIST)
               for x in promoter.rejects):
            print("Rerun with --ignore-rejects to ignore rejections from dver mismatches")

    if any(promoter.tag_pkg_args.values()):
        text_args = {}
        for tag, builds in promoter.tag_pkg_args.items():
            text_args[tag] = [x.nvr for x in builds]
        print("Promotion plan:")
        print_table(text_args)
    else:
        printf("Nothing will be promoted!")
        return 1

    question = "Proceed with promoting the builds?"
    try:
        proceed = (options.assume_yes or not sys.stdin.isatty() or utils.ask_yn(question))
    except KeyboardInterrupt:
        printf("Canceled.")
        return 3

    if proceed:
        promoted_builds = promoter.do_promotions(options.dry_run, options.regen)
        if not options.dry_run:
            printf("\nJIRA code for this set of promotions (old syntax):\n")
            write_old_jira(kojihelper, promoted_builds, [x[0] for x in route_dvers_pairs])
            printf("\nJIRA code for this set of promotions (new syntax):\n")
            write_jira(kojihelper, promoted_builds, [x[0] for x in route_dvers_pairs])
    else:
        printf("Not proceeding.")
        return 1

    return 0


def _get_route_dvers_pairs(routenames, valid_routes, extra_dvers, no_dvers, only_dver):
    route_dvers_pairs = []

    for routename in routenames:
        route = valid_routes[routename]

        if only_dver:
            if only_dver in route.dvers or only_dver in route.extra_dvers:
                route_dvers_pairs.append((route, set([only_dver])))
            else:
                printf("The dver %s is not available for route %s.", only_dver, routename)
                _print_route_dvers(routename, route)
                sys.exit(2)
            continue

        wanted_dvers_for_route = set(route.dvers)
        for extra_dver in extra_dvers:
            if extra_dver in route.extra_dvers:
                wanted_dvers_for_route.add(extra_dver)
        for no_dver in no_dvers:
            wanted_dvers_for_route.discard(no_dver)
        if not wanted_dvers_for_route:
            printf("All dvers for route %s have been disabled.")
            _print_route_dvers(routename, route)
            sys.exit(2)

        route_dvers_pairs.append((route, wanted_dvers_for_route))

    return route_dvers_pairs


def entrypoint():
    """CLI entrypoint for osg-promote"""
    try:
        main()
    except error.Error as e:
        print(e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(entrypoint())
