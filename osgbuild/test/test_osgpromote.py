#!/usr/bin/env python3
import os
import sys

import logging
import unittest
from io import StringIO

import osgbuild.kojiinter

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/../.."))

from osgbuild import promoter
from osgbuild import constants
from osgbuild import utils

INIFILE = "promoter.ini"

log = logging.getLogger('osgpromote')
log.setLevel(logging.ERROR)

TAGS = ['devops-el7-itb',
        'devops-el7-production',
        'devops-el8-itb',
        'devops-el8-production',
        'devops-el9-itb',
        'devops-el9-production',
        'hcc-el7',
        'hcc-el7-build',
        'hcc-el7-release',
        'hcc-el7-testing',
        'hcc-el8',
        'hcc-el8-build',
        'hcc-el8-release',
        'hcc-el8-testing',
        'hcc-el9',
        'hcc-el9-build',
        'hcc-el9-release',
        'hcc-el9-testing',
        'osg-3.4-el7-build',
        'osg-3.4-el7-contrib',
        'osg-3.4-el7-development',
        'osg-3.4-el7-empty',
        'osg-3.4-el7-prerelease',
        'osg-3.4-el7-release',
        'osg-3.4-el7-release-build',
        'osg-3.4-el7-rolling',
        'osg-3.4-el7-testing',
        'osg-3.5-el7-build',
        'osg-3.5-el7-contrib',
        'osg-3.5-el7-development',
        'osg-3.5-el7-empty',
        'osg-3.5-el7-prerelease',
        'osg-3.5-el7-release',
        'osg-3.5-el7-release-3.5.0',
        'osg-3.5-el7-release-3.5.1',
        'osg-3.5-el7-release-3.5.10',
        'osg-3.5-el7-release-3.5.11',
        'osg-3.5-el7-release-3.5.12',
        'osg-3.5-el7-release-3.5.13',
        'osg-3.5-el7-release-3.5.14',
        'osg-3.5-el7-release-3.5.15',
        'osg-3.5-el7-release-3.5.16',
        'osg-3.5-el7-release-3.5.17',
        'osg-3.5-el7-release-3.5.18',
        'osg-3.5-el7-release-3.5.19',
        'osg-3.5-el7-release-3.5.2',
        'osg-3.5-el7-release-3.5.20',
        'osg-3.5-el7-release-3.5.21',
        'osg-3.5-el7-release-3.5.22',
        'osg-3.5-el7-release-3.5.23',
        'osg-3.5-el7-release-3.5.24',
        'osg-3.5-el7-release-3.5.25',
        'osg-3.5-el7-release-3.5.26',
        'osg-3.5-el7-release-3.5.27',
        'osg-3.5-el7-release-3.5.28',
        'osg-3.5-el7-release-3.5.29',
        'osg-3.5-el7-release-3.5.3',
        'osg-3.5-el7-release-3.5.4',
        'osg-3.5-el7-release-3.5.5',
        'osg-3.5-el7-release-3.5.6',
        'osg-3.5-el7-release-3.5.7',
        'osg-3.5-el7-release-3.5.8',
        'osg-3.5-el7-release-3.5.9',
        'osg-3.5-el7-release-build',
        'osg-3.5-el7-rolling',
        'osg-3.5-el7-testing',
        'osg-3.5-el8-build',
        'osg-3.5-el8-contrib',
        'osg-3.5-el8-development',
        'osg-3.5-el8-empty',
        'osg-3.5-el8-prerelease',
        'osg-3.5-el8-release',
        'osg-3.5-el8-release-3.5.21',
        'osg-3.5-el8-release-3.5.22',
        'osg-3.5-el8-release-3.5.23',
        'osg-3.5-el8-release-3.5.24',
        'osg-3.5-el8-release-3.5.25',
        'osg-3.5-el8-release-3.5.26',
        'osg-3.5-el8-release-3.5.27',
        'osg-3.5-el8-release-3.5.28',
        'osg-3.5-el8-release-3.5.29',
        'osg-3.5-el8-release-build',
        'osg-3.5-el8-rolling',
        'osg-3.5-el8-testing',
        'osg-3.5-upcoming-el7-build',
        'osg-3.5-upcoming-el7-development',
        'osg-3.5-upcoming-el7-prerelease',
        'osg-3.5-upcoming-el7-release',
        'osg-3.5-upcoming-el7-rolling',
        'osg-3.5-upcoming-el7-testing',
        'osg-3.5-upcoming-el8-build',
        'osg-3.5-upcoming-el8-development',
        'osg-3.5-upcoming-el8-prerelease',
        'osg-3.5-upcoming-el8-release',
        'osg-3.5-upcoming-el8-rolling',
        'osg-3.5-upcoming-el8-testing',
        'osg-3.6-el7-bootstrap',
        'osg-3.6-el7-build',
        'osg-3.6-el7-contrib',
        'osg-3.6-el7-development',
        'osg-3.6-el7-empty',
        'osg-3.6-el7-prerelease',
        'osg-3.6-el7-release',
        'osg-3.6-el7-release-build',
        'osg-3.6-el7-testing',
        'osg-3.6-el8-bootstrap',
        'osg-3.6-el8-build',
        'osg-3.6-el8-contrib',
        'osg-3.6-el8-development',
        'osg-3.6-el8-empty',
        'osg-3.6-el8-prerelease',
        'osg-3.6-el8-release',
        'osg-3.6-el8-release-build',
        'osg-3.6-el8-testing',
        'osg-3.6-el9-bootstrap',
        'osg-3.6-el9-build',
        'osg-3.6-el9-contrib',
        'osg-3.6-el9-development',
        'osg-3.6-el9-empty',
        'osg-3.6-el9-prerelease',
        'osg-3.6-el9-release',
        'osg-3.6-el9-release-build',
        'osg-3.6-el9-testing',
        'osg-3.6-upcoming-el7-build',
        'osg-3.6-upcoming-el7-development',
        'osg-3.6-upcoming-el7-prerelease',
        'osg-3.6-upcoming-el7-release',
        'osg-3.6-upcoming-el7-testing',
        'osg-3.6-upcoming-el8-build',
        'osg-3.6-upcoming-el8-development',
        'osg-3.6-upcoming-el8-prerelease',
        'osg-3.6-upcoming-el8-release',
        'osg-3.6-upcoming-el8-testing',
        'osg-3.6-upcoming-el9-build',
        'osg-3.6-upcoming-el9-development',
        'osg-3.6-upcoming-el9-prerelease',
        'osg-3.6-upcoming-el9-release',
        'osg-3.6-upcoming-el9-testing',
        'osg-upcoming-el7-build',
        'osg-upcoming-el7-development',
        'osg-upcoming-el7-prerelease',
        'osg-upcoming-el7-release',
        'osg-upcoming-el7-rolling',
        'osg-upcoming-el7-testing',
        'osg-upcoming-el8-build',
        'osg-upcoming-el8-development',
        'osg-upcoming-el8-prerelease',
        'osg-upcoming-el8-release',
        'osg-upcoming-el8-rolling',
        'osg-upcoming-el8-testing',
        ]


class FakeKojiHelper(osgbuild.kojiinter.KojiHelper):
    tagged_builds_by_tag = {
            'osg-3.5-el7-development': [
                {'nvr': 'goodpkg-2000-1.osg35.el7', 'latest': True},
                {'nvr': 'reject-distinct-repos-1-1.osg35.el7', 'latest': True},
                ],
            'osg-3.5-el8-development': [
                {'nvr': 'goodpkg-2000-1.osg35.el8', 'latest': True},
                {'nvr': 'reject-distinct-repos-1-1.osg35.el8', 'latest': True},
                ],
            'osg-3.6-el7-development': [
                {'nvr': 'goodpkg-1999-1.osg36.el7', 'latest': False},
                {'nvr': 'goodpkg-2000-1.osg36.el7', 'latest': True},
                {'nvr': 'reject-distinct-dvers-2-1.osg36.el7', 'latest': True},
                {'nvr': 'partially-overlapping-dvers-in-repo-1-1.osg36.el7', 'latest': True},
                ],
            'osg-3.6-el8-development': [
                {'nvr': 'goodpkg-1999-1.osg36.el8', 'latest': False},
                {'nvr': 'goodpkg-2000-1.osg36.el8', 'latest': True},
                {'nvr': 'reject-distinct-dvers-1-1.osg36.el8', 'latest': True},
                {'nvr': 'reject-distinct-repos-2-1.osg36.el8', 'latest': True},
                {'nvr': 'partially-overlapping-dvers-in-repo-1-1.osg36.el8', 'latest': True},
                ],
            'osg-3.6-el9-development': [
                {'nvr': 'goodpkg-1999-1.osg36.el9', 'latest': False},
                {'nvr': 'goodpkg-2000-1.osg36.el9', 'latest': True},
                {'nvr': 'reject-distinct-dvers-1-1.osg36.el9', 'latest': True},
                {'nvr': 'reject-distinct-repos-2-1.osg36.el9', 'latest': True},
                {'nvr': 'partially-overlapping-dvers-in-repo-1-1.osg36.el9', 'latest': True},
                ],
            'osg-upcoming-el7-development': [
                {'nvr': 'goodpkg-1999-1.osgup.el7', 'latest': False},
                {'nvr': 'goodpkg-2000-1.osgup.el7', 'latest': True},
                {'nvr': 'reject-distinct-dvers-1-1.osgup.el7', 'latest': True},
                {'nvr': 'partially-overlapping-dvers-in-repo-1-1.osgup.el7', 'latest': True},
                ],
            'osg-upcoming-el8-development': [
                {'nvr': 'goodpkg-1999-1.osgup.el8', 'latest': False},
                {'nvr': 'goodpkg-2000-1.osgup.el8', 'latest': True},
                {'nvr': 'reject-distinct-dvers-2-1.osgup.el8', 'latest': True},
                {'nvr': 'partially-overlapping-dvers-in-repo-1-1.osgup.el8', 'latest': True},
                ],
            'osg-3.5-upcoming-el7-development': [
                {'nvr': 'goodpkg-2000-1.osg35.el7', 'latest': True},
                {'nvr': 'reject-distinct-repos-1-1.osg35.el7', 'latest': True},
            ],
            'osg-3.5-upcoming-el8-development': [
                {'nvr': 'goodpkg-2000-1.osg35.el8', 'latest': True},
                {'nvr': 'reject-distinct-repos-1-1.osg35.el8', 'latest': True},
            ],
            'osg-3.6-upcoming-el7-development': [
                {'nvr': 'goodpkg-2000-1.osg35.el7', 'latest': True},
                {'nvr': 'reject-distinct-repos-1-1.osg35.el7', 'latest': True},
            ],
            'osg-3.6-upcoming-el8-development': [
                {'nvr': 'goodpkg-2000-1.osg35.el8', 'latest': True},
                {'nvr': 'reject-distinct-repos-1-1.osg35.el8', 'latest': True},
            ],
            'osg-3.6-upcoming-el9-development': [
                {'nvr': 'goodpkg-2000-1.osg35.el9', 'latest': True},
                {'nvr': 'reject-distinct-repos-1-1.osg35.el9', 'latest': True},
            ],
    }

    want_success = True

    def __init__(self, *args):
        self.tagged_packages_by_tag = {}
        for k, v in self.tagged_builds_by_tag.items():
            nvrs = [x['nvr'] for x in v]
            names = sorted(set([osgbuild.utils.split_nvr(x)[0] for x in nvrs]))
            self.tagged_packages_by_tag[k] = names
        self.newly_tagged_packages = []
        super(FakeKojiHelper, self).__init__(*args)

    def get_first_tag(self, match, terms):
        if match != 'exact': raise NotImplementedError("match!='exact'")
        if terms in TAGS:
            return terms

    def get_tagged_packages(self, tag):
        return self.tagged_packages_by_tag[tag]

    def get_tagged_builds(self, tag):
        return [build['nvr'] for build in self.tagged_builds_by_tag[tag]]

    def get_latest_build(self, package, tag):
        for build in self.tagged_builds_by_tag[tag]:
            if build['nvr'].startswith(package+'-') and build['latest']:
                return build['nvr']
        return None

    def koji_get_build(self, build_nvr):
        return {'id': 319}

    def tag_build(self, tag, build, force=False):
        self.newly_tagged_packages.append(build)
        task_id = len(self.newly_tagged_packages) - 1
        # sys.stdout.write("%d = tag(%s, %s)\n" % (task_id, tag, build))
        return task_id

    def watch_tasks(self, a_list):
        pass

    def get_task_state(self, task_id):
        if len(self.newly_tagged_packages) > task_id and self.want_success:
            return 'CLOSED'
        else:
            return 'FAILED'


class TestUtil(unittest.TestCase):
    buildnvr = "osg-build-1.3.2-1.osg35.el7"
    def test_split_nvr(self):
        self.assertEqual(('osg-build', '1.3.2', '1.osg35.el7'), osgbuild.utils.split_nvr(self.buildnvr))

    def test_split_repo_dver(self):
        self.assertEqual(('osg-build-1.3.2-1', 'osg35', 'el7'), promoter.split_repotag_dver(self.buildnvr))
        self.assertEqual(('foo-1-1', 'osg', ''), promoter.split_repotag_dver('foo-1-1.osg'))
        self.assertEqual(('foo-1-1', '', 'el7'), promoter.split_repotag_dver('foo-1-1.el7'))
        self.assertEqual(('foo-1-1', '', ''), promoter.split_repotag_dver('foo-1-1'))
        # Tests against SOFTWARE-1420:
        self.assertEqual(('foo-1-1', 'osg', ''), promoter.split_repotag_dver('foo-1-1.osg', ['osg']))
        self.assertEqual(('bar-1-1.1', '', ''), promoter.split_repotag_dver('bar-1-1.1'))
        self.assertEqual(('bar-1-1.rc1', '', ''), promoter.split_repotag_dver('bar-1-1.rc1', ['osg', 'osg35', 'osg36']))


def _config():
    configuration = promoter.Configuration()
    configuration.load_inifile(INIFILE)
    configuration.load_inifile("../osgbuild/test/promoter_extra.ini")
    return configuration


class TestRouteLoader(unittest.TestCase):
    def setUp(self):
        self.configuration = _config()
        self.routes = self.configuration.routes

    def test_hcc_route(self):
        self.assertEqual('hcc-%s-testing', self.routes['hcc'].from_tag_hint)
        self.assertEqual('hcc-%s-release', self.routes['hcc'].to_tag_hint)
        self.assertEqual('hcc', self.routes['hcc'].repotag)
        self.assertEqual(['el7'], self.routes['hcc'].dvers)

    def test_osg_route(self):
        self.assertEqual('osg-3.5-%s-development', self.routes['3.5-testing'].from_tag_hint)
        self.assertEqual('osg-3.5-%s-testing', self.routes['3.5-testing'].to_tag_hint)
        self.assertEqual('osg35', self.routes['3.5-testing'].repotag)
        self.assertEqual('osg-3.5-upcoming-%s-development', self.routes['3.5-upcoming'].from_tag_hint)
        self.assertEqual('osg-3.5-upcoming-%s-testing', self.routes['3.5-upcoming'].to_tag_hint)
        self.assertEqual('osg35up', self.routes['3.5-upcoming'].repotag)

        self.assertEqual('osg-3.6-%s-development', self.routes['3.6-testing'].from_tag_hint)
        self.assertEqual('osg-3.6-%s-testing', self.routes['3.6-testing'].to_tag_hint)
        self.assertEqual('osg36', self.routes['3.6-testing'].repotag)
        self.assertEqual('osg-3.6-upcoming-%s-development', self.routes['3.6-upcoming'].from_tag_hint)
        self.assertEqual('osg-3.6-upcoming-%s-testing', self.routes['3.6-upcoming'].to_tag_hint)
        self.assertEqual('osg36up', self.routes['3.6-upcoming'].repotag)

    def test_route_alias(self):
        for key in 'from_tag_hint', 'to_tag_hint', 'repotag':
            self.assertEqual(getattr(self.configuration.matching_routes('testing')[0], key), getattr(self.routes['3.5-testing'], key))
            self.assertEqual(getattr(self.configuration.matching_routes('3.5-rfr')[0], key), getattr(self.routes['3.5-prerelease'], key))
            self.assertEqual(getattr(self.configuration.matching_routes('3.5-rfr')[1], key), getattr(self.routes['3.5-rolling'], key))
            self.assertEqual(getattr(self.configuration.matching_routes('3.6-rfr')[0], key), getattr(self.routes['3.6-prerelease'], key))

    def test_type(self):
        for route in self.routes.values():
            self.assertTrue(isinstance(route, promoter.Route))


class TestPromoter(unittest.TestCase):
    dvers = ['el7', 'el8', 'el9']
    dvers_upcoming = ['el7', 'el8', 'el9']

    def setUp(self):
        self.configuration = _config()
        self.kojihelper = FakeKojiHelper(False)
        self.testing_route = self.configuration.routes['3.6-testing']
        self.testing_promoter = self._make_promoter([self.testing_route])
        self.multi_routes = [self.configuration.routes['3.5-testing'], self.configuration.routes['3.6-testing']]

    def _make_promoter(self, routes, dvers=None):
        dvers = dvers or TestPromoter.dvers
        pairs = [(route, set(dvers)) for route in routes]
        return promoter.Promoter(self.kojihelper, pairs)

    def test_add_promotion(self):
        self.testing_promoter.add_promotion('goodpkg')
        for dver in self.dvers:
            self.assertTrue(
                'goodpkg-2000-1.osg36.%s' % dver in
                [x.nvr for x in self.testing_promoter.tag_pkg_args[self.testing_route.to_tag_hint % dver]])

    def test_add_promotion_with_nvr(self):
        self.testing_promoter.add_promotion('goodpkg-2000-1.osg36.el8')
        for dver in self.dvers:
            self.assertTrue(
                'goodpkg-2000-1.osg36.%s' % dver in
                [x.nvr for x in self.testing_promoter.tag_pkg_args[self.testing_route.to_tag_hint % dver]])

    def test_add_promotion_with_nvr_no_dist(self):
        self.testing_promoter.add_promotion('goodpkg-2000-1')
        for dver in self.dvers:
            self.assertTrue(
                'goodpkg-2000-1.osg36.%s' % dver in
                [x.nvr for x in self.testing_promoter.tag_pkg_args[self.testing_route.to_tag_hint % dver]])

    def test_reject_add(self):
        self.testing_promoter.add_promotion('goodpkg')
        self.testing_promoter.add_promotion('reject-distinct-dvers')
        self.assertFalse(
            'reject-distinct-dvers-1-1.osg36.el8' in
            [x.nvr for x in self.testing_promoter.tag_pkg_args[self.testing_route.to_tag_hint % 'el8']])

    def test_reject_add_with_ignore(self):
        self.testing_promoter.add_promotion('goodpkg')
        self.testing_promoter.add_promotion('reject-distinct-dvers', ignore_rejects=True)
        self.assertTrue(
            'reject-distinct-dvers-1-1.osg36.el8' in
            [x.nvr for x in self.testing_promoter.tag_pkg_args[self.testing_route.to_tag_hint % 'el8']])
        self.assertTrue(
            'reject-distinct-dvers-2-1.osg36.el7' in
            [x.nvr for x in self.testing_promoter.tag_pkg_args[self.testing_route.to_tag_hint % 'el7']])

    def test_new_reject(self):
        self.testing_promoter.add_promotion('reject-distinct-dvers')
        rejs = self.testing_promoter.rejects
        self.assertEqual(1, len(rejs))
        self.assertEqual('reject-distinct-dvers', rejs[0].pkg_or_build)
        self.assertEqual(promoter.Reject.REASON_DISTINCT_ACROSS_DISTS, rejs[0].reason)

    def test_multi_promote(self):
        prom = self._make_promoter(self.multi_routes)
        prom.add_promotion('goodpkg-2000-1')
        for dver in ['el8', 'el7']:
            for osgver in ['3.5', '3.6']:
                tag = 'osg-%s-%s-testing' % (osgver, dver)
                dist = 'osg%s.%s' % (osgver.replace(".", ""), dver)
                pkg = 'goodpkg-2000-1.%s' % dist

                self.assertTrue(tag in prom.tag_pkg_args)
                self.assertTrue(pkg in [x.nvr for x in prom.tag_pkg_args[tag]])

    def test_cross_dist_reject(self):
        prom = self._make_promoter(self.multi_routes, ['el8'])
        prom.add_promotion('reject-distinct-repos')
        rejs = prom.rejects
        self.assertEqual(1, len(rejs))
        self.assertEqual(promoter.Reject.REASON_DISTINCT_ACROSS_DISTS, rejs[0].reason)

    def test_do_promotions(self):
        self.testing_promoter.add_promotion('goodpkg')
        promoted_builds = self.testing_promoter.do_promotions()
        self.assertEqual(2, len(self.kojihelper.newly_tagged_packages))
        for dver in ['el7', 'el8', 'el9']:
            tag = 'osg-3.6-%s-testing' % dver
            dist = 'osg36.%s' % dver
            nvr = 'goodpkg-2000-1.%s' % dist
            self.assertTrue(tag in promoted_builds)
            self.assertTrue(nvr in [x.nvr for x in promoted_builds[tag]])
            self.assertEqual(1, len(promoted_builds[tag]))
        self.assertEqual(2, len(promoted_builds))

    def test_do_multi_promotions(self):
        prom = self._make_promoter(self.multi_routes)
        prom.add_promotion('goodpkg-2000-1')
        promoted_builds = prom.do_promotions()
        self.assertEqual(4, len(self.kojihelper.newly_tagged_packages))
        for osgver in ['3.5', '3.6']:
            for dver in ['el7', 'el8']:
                tag = 'osg-%s-%s-testing' % (osgver, dver)
                dist = 'osg%s.%s' % (osgver.replace(".", ""), dver)
                nvr = 'goodpkg-2000-1.%s' % dist
                self.assertTrue(tag in promoted_builds)
                self.assertTrue(nvr in [x.nvr for x in promoted_builds[tag]])
                self.assertEqual(1, len(promoted_builds[tag]))
        self.assertEqual(4, len(promoted_builds))

    # def test_do_promote_with_partially_overlapping_dvers_between_repos(self):
    #     pairs = [(self.configuration.routes['3.4-testing'], set(['el6', 'el7'])),
    #              (self.configuration.routes['upcoming2'], set(['el7', 'el8']))]
    #     prom = promoter.Promoter(self.kojihelper, pairs)
    #     prom.add_promotion('partially-overlapping-dvers-in-repo')
    #     promoted_builds = prom.do_promotions()
    #     self.assertEqual(4, len(self.kojihelper.newly_tagged_packages))
    #     self.assertEqual(4, len(promoted_builds))

    def _test_write_old_jira(self, real_promotions):
        out = StringIO()
        promoted_builds = {}
        if real_promotions:
            prom = self._make_promoter(self.multi_routes)
            prom.add_promotion('goodpkg-2000-1')
            promoted_builds = prom.do_promotions()
        expected_lines = [
            "*Promotions*",
            "Promoted goodpkg-2000-1 to osg-3.5-el*-testing, osg-3.6-el*-testing",
            "|| Build || Tag ||"]
        for osgver in ['3.5', '3.6']:
            for dver in ['el7', 'el8']:
                tag = 'osg-%s-%s-testing' % (osgver, dver)
                dist = 'osg%s.%s' % (osgver.replace(".", ""), dver)
                nvr = 'goodpkg-2000-1.%s' % dist

                build = promoter.Build.new_from_nvr(nvr)
                if not real_promotions:
                    promoted_builds[tag] = [build]
                build_uri = "%s/koji/buildinfo?buildID=%d" % (constants.KOJI_WEB, 319)
                expected_lines.append("| [%s|%s] | %s |" % (build.nvr, build_uri, tag))
        expected_lines.append("")
        promoter.write_old_jira(self.kojihelper, promoted_builds, self.multi_routes, out)
        actual_lines = out.getvalue().split("\n")
        for idx, expected_line in enumerate(expected_lines):
            self.assertEqual(expected_line, actual_lines[idx])
        self.assertEqual(len(expected_lines), len(actual_lines))

    def _test_write_jira(self, real_promotions):
        out = StringIO()
        promoted_builds = {}
        if real_promotions:
            prom = self._make_promoter(self.multi_routes)
            prom.add_promotion('goodpkg-2000-1')
            promoted_builds = prom.do_promotions()
        expected_lines = [
            "**Promotions**",
            "Promoted goodpkg-2000-1 to osg-3.5-el*-testing, osg-3.6-el*-testing",
            "**Build** | **Tag**",
            "--- | ---",
        ]
        for osgver in ['3.5', '3.6']:
            for dver in ['el7', 'el8']:
                tag = 'osg-%s-%s-testing' % (osgver, dver)
                dist = 'osg%s.%s' % (osgver.replace(".", ""), dver)
                nvr = 'goodpkg-2000-1.%s' % dist

                build = promoter.Build.new_from_nvr(nvr)
                if not real_promotions:
                    promoted_builds[tag] = [build]
                build_uri = "%s/koji/buildinfo?buildID=%d" % (constants.KOJI_WEB, 319)
                expected_lines.append(" [%s](%s) | %s" % (build.nvr, build_uri, tag))
        expected_lines.append("")
        promoter.write_jira(self.kojihelper, promoted_builds, self.multi_routes, out)
        actual_lines = out.getvalue().split("\n")
        for idx, expected_line in enumerate(expected_lines):
            self.assertEqual(expected_line, actual_lines[idx])
        self.assertEqual(len(expected_lines), len(actual_lines))

    def test_write_old_jira(self):
        self._test_write_old_jira(real_promotions=False)

    def test_write_jira(self):
        self._test_write_jira(real_promotions=False)

    def test_all(self):
        self._test_write_jira(real_promotions=True)


if __name__ == '__main__':
    unittest.main()
