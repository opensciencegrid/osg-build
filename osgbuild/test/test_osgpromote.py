#!/usr/bin/env python3
import os
import sys

import logging
import unittest
from io import StringIO

import osgbuild.kojiinter

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/../.."))

from osgbuild import promoter
from osgbuild import osg_sign
from osgbuild import constants
from osgbuild import utils
from osgbuild.kojiinter import RpmKeyidsPair

log = logging.getLogger('promoter')
log.setLevel(logging.ERROR)


KEY_OSG_2 = "96d2b90f"
KEY_OSG_4 = "1887c61a"
KEY_OSG_23_developer = "92897c00"


TAGS = ['condor-el6',
        'condor-el7',
        'condor-el7-build',
        'devops-el7-build',
        'devops-el7-itb',
        'devops-el7-production',
        'devops-el8-build',
        'devops-el8-itb',
        'devops-el8-production',
        'devops-el9-build',
        'devops-el9-itb',
        'devops-el9-production',
        'dist-el6',
        'dist-el7',
        'dist-el7-build',
        'dist-el8',
        'dist-el8-build',
        'dist-el9',
        'dist-el9-build',
        'epelrescue-el6',
        'epelrescue-el7',
        'goc-el6-itb',
        'goc-el6-production',
        'goc-el7-itb',
        'goc-el7-production',
        'hcc-el6',
        'hcc-el6-release',
        'hcc-el6-testing',
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
        'kojira-fake',
        'osg-23-el8-contrib',
        'osg-23-el8-empty',
        'osg-23-el9-contrib',
        'osg-23-el9-empty',
        'osg-23-internal-el8-build',
        'osg-23-internal-el8-development',
        'osg-23-internal-el8-release',
        'osg-23-internal-el9-build',
        'osg-23-internal-el9-development',
        'osg-23-internal-el9-release',
        'osg-23-main-el8-bootstrap',
        'osg-23-main-el8-build',
        'osg-23-main-el8-development',
        'osg-23-main-el8-prerelease',
        'osg-23-main-el8-release',
        'osg-23-main-el8-testing',
        'osg-23-main-el9-bootstrap',
        'osg-23-main-el9-build',
        'osg-23-main-el9-development',
        'osg-23-main-el9-prerelease',
        'osg-23-main-el9-release',
        'osg-23-main-el9-testing',
        'osg-23-upcoming-el8-build',
        'osg-23-upcoming-el8-development',
        'osg-23-upcoming-el8-prerelease',
        'osg-23-upcoming-el8-release',
        'osg-23-upcoming-el8-testing',
        'osg-23-upcoming-el9-build',
        'osg-23-upcoming-el9-development',
        'osg-23-upcoming-el9-prerelease',
        'osg-23-upcoming-el9-release',
        'osg-23-upcoming-el9-testing',
        'osg-3.4-el6-contrib',
        'osg-3.4-el6-development',
        'osg-3.4-el6-empty',
        'osg-3.4-el6-prerelease',
        'osg-3.4-el6-release',
        'osg-3.4-el6-rolling',
        'osg-3.4-el6-testing',
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
        'osg-3.5-el7-release-build',
        'osg-3.5-el7-rolling',
        'osg-3.5-el7-testing',
        'osg-3.5-el8-build',
        'osg-3.5-el8-contrib',
        'osg-3.5-el8-development',
        'osg-3.5-el8-empty',
        'osg-3.5-el8-prerelease',
        'osg-3.5-el8-release',
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
        'osg-3.6-el9-rolling',
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
        'osg-3.6-upcoming-el9-rolling',
        'osg-3.6-upcoming-el9-testing',
        'osg-el6',
        'osg-el6-internal',
        'osg-el7',
        'osg-el7-internal',
        'osg-el7-internal-build',
        'osg-el8',
        'osg-el8-internal',
        'osg-el8-internal-build',
        'osg-el9',
        'osg-el9-internal',
        'osg-el9-internal-build',
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
            'osg-23-main-el9-development': [
                {'nvr': 'goodpkg-2000-1.osg23.el9', 'latest': True},
                {'nvr': 'reject-distinct-repos-1-1.osg23.el9', 'latest': True},
                ],
            'osg-23-main-el8-development': [
                {'nvr': 'goodpkg-2000-1.osg23.el8', 'latest': True},
                {'nvr': 'reject-distinct-repos-1-1.osg23.el8', 'latest': True},
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
            'osg-23-upcoming-el9-development': [
                {'nvr': 'goodpkg-2000-1.osg23up.el9', 'latest': True},
                {'nvr': 'reject-distinct-repos-1-1.osg23up.el9', 'latest': True},
                {'nvr': 'reject-invalid-key-1-1.osg23up.el9', 'latest': True},
            ],
            'osg-23-upcoming-el8-development': [
                {'nvr': 'goodpkg-2000-1.osg23up.el8', 'latest': True},
                {'nvr': 'reject-distinct-repos-1-1.osg23up.el8', 'latest': True},
                {'nvr': 'reject-invalid-key-1-1.osg23up.el8', 'latest': True},
            ],
            'osg-3.6-upcoming-el7-development': [
                {'nvr': 'goodpkg-2000-1.osg36up.el7', 'latest': True},
                {'nvr': 'reject-distinct-repos-1-1.osg36up.el7', 'latest': True},
            ],
            'osg-3.6-upcoming-el8-development': [
                {'nvr': 'goodpkg-2000-1.osg36up.el8', 'latest': True},
                {'nvr': 'reject-distinct-repos-1-1.osg36up.el8', 'latest': True},
            ],
            'osg-3.6-upcoming-el9-development': [
                {'nvr': 'goodpkg-2000-1.osg36up.el9', 'latest': True},
                {'nvr': 'reject-distinct-repos-1-1.osg36up.el9', 'latest': True},
            ],
    }

    rpms_and_keyids_by_nvr = {
        'goodpkg-2000-1.osg36up.el9':
            [RpmKeyidsPair('goodpkg-2000-1.osg36up.el9.x86_64.rpm', {KEY_OSG_4})],
        'goodpkg-2000-1.osg36up.el8':
            [RpmKeyidsPair('goodpkg-2000-1.osg36up.el8.x86_64.rpm', {KEY_OSG_2})],
        'goodpkg-2000-1.osg23up.el9':
            [RpmKeyidsPair('goodpkg-2000-1.osg23up.el9.x86_64.rpm', {KEY_OSG_23_developer})],
        'goodpkg-2000-1.osg23up.el8':
            [RpmKeyidsPair('goodpkg-2000-1.osg23up.el8.x86_64.rpm', {KEY_OSG_23_developer})],
        'reject-invalid-key-1-1.osg23up.el9':
            [RpmKeyidsPair('reject-invalid-key-1-1.osg23up.el9.x86_64.rpm', {KEY_OSG_2})],
        'reject-invalid-key-1-1.osg23up.el8':
            [RpmKeyidsPair('reject-invalid-key-1-1.osg23up.el8.x86_64.rpm', {KEY_OSG_4})],
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

    def get_rpms_and_keyids_in_build(self, build_nvr):
        return self.rpms_and_keyids_by_nvr.get(build_nvr, [])

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
    buildnvr = "osg-build-1.3.2-1.osg23.el9"

    def test_split_nvr(self):
        self.assertEqual(('osg-build', '1.3.2', '1.osg23.el9'), osgbuild.utils.split_nvr(self.buildnvr))

    def test_split_repotag_dver(self):
        self.assertEqual(('osg-build-1.3.2-1', 'osg23', 'el9'), promoter.split_repotag_dver(self.buildnvr))
        self.assertEqual(('foo-1-1', 'osg', ''), promoter.split_repotag_dver('foo-1-1.osg'))
        self.assertEqual(('foo-1-1', '', 'el7'), promoter.split_repotag_dver('foo-1-1.el7'))
        self.assertEqual(('foo-1-1', '', ''), promoter.split_repotag_dver('foo-1-1'))
        # Tests against SOFTWARE-1420:
        self.assertEqual(('foo-1-1', 'osg', ''), promoter.split_repotag_dver('foo-1-1.osg', ['osg']))
        self.assertEqual(('bar-1-1.1', '', ''), promoter.split_repotag_dver('bar-1-1.1'))
        self.assertEqual(('bar-1-1.rc1', '', ''), promoter.split_repotag_dver('bar-1-1.rc1', ['osg', 'osg35', 'osg36']))


def _config():
    signing_keys_ini = utils.find_file(constants.SIGNING_KEYS_INI,
                                       strict=True)
    signing_keys_config = osg_sign.SigningKeysConfig(signing_keys_ini)
    configuration = promoter.Configuration([
        utils.find_file(constants.PROMOTER_INI),
        "../osgbuild/test/promoter_extra.ini"
    ], signing_keys_config)
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
        self.assertEqual('osg-23-main-%s-development', self.routes['23-main'].from_tag_hint)
        self.assertEqual('osg-23-main-%s-testing', self.routes['23-main'].to_tag_hint)
        self.assertEqual('osg23', self.routes['23-main'].repotag)
        self.assertEqual('osg-23-upcoming-%s-development', self.routes['23-upcoming'].from_tag_hint)
        self.assertEqual('osg-23-upcoming-%s-testing', self.routes['23-upcoming'].to_tag_hint)
        self.assertEqual('osg23up', self.routes['23-upcoming'].repotag)

        self.assertEqual('osg-3.6-%s-development', self.routes['3.6-testing'].from_tag_hint)
        self.assertEqual('osg-3.6-%s-testing', self.routes['3.6-testing'].to_tag_hint)
        self.assertEqual('osg36', self.routes['3.6-testing'].repotag)
        self.assertEqual('osg-3.6-upcoming-%s-development', self.routes['3.6-upcoming'].from_tag_hint)
        self.assertEqual('osg-3.6-upcoming-%s-testing', self.routes['3.6-upcoming'].to_tag_hint)
        self.assertEqual('osg36up', self.routes['3.6-upcoming'].repotag)

    def test_route_alias(self):
        for key in 'from_tag_hint', 'to_tag_hint', 'repotag':
            self.assertEqual(getattr(self.configuration.matching_routes('23-testing')[0], key),
                             getattr(self.routes['23-main'], key))
            self.assertEqual(getattr(self.configuration.matching_routes('3.6-rfr')[0], key),
                             getattr(self.routes['3.6-prerelease'], key))

    def test_type(self):
        for route in self.routes.values():
            self.assertIsInstance(route, promoter.Route)


class TestPromoter(unittest.TestCase):

    def setUp(self):
        self.configuration = _config()
        self.kojihelper = FakeKojiHelper(False)
        self.route_36testing = self.configuration.routes['3.6-testing']
        self.promoter_36testing = self._make_promoter([self.route_36testing],
                                                      dvers=self.route_36testing.dvers)
        self.route_36upcoming = self.configuration.routes['3.6-upcoming']
        self.promoter_36upcoming = self._make_promoter([self.route_36upcoming],
                                                       dvers=self.route_36upcoming.dvers)
        self.route_23main = self.configuration.routes['23-main']
        self.promoter_23main = self._make_promoter([self.route_23main],
                                                   dvers=self.route_23main.dvers)
        self.route_23upcoming = self.configuration.routes['23-upcoming']
        self.promoter_23upcoming = self._make_promoter([self.route_23upcoming],
                                                       dvers=self.route_23upcoming.dvers)
        self.multi_routes = [self.configuration.routes['23-main'], self.configuration.routes['3.6-testing']]

    def _make_promoter(self, routes, dvers):
        pairs = [(route, set(dvers)) for route in routes]
        signing_keys = self.configuration.signing_keys_by_name
        return promoter.Promoter(self.kojihelper, pairs, signing_keys)

    @staticmethod
    def _tagged_nvrs(promoter_obj, route, dver):
        return [x.nvr for x in promoter_obj.tag_pkg_args[route.to_tag_hint % dver]]

    def test_add_promotion(self):
        self.promoter_36testing.add_promotion('goodpkg', ignore_signatures=True)
        for dver in self.route_36testing.dvers:
            self.assertIn(
                'goodpkg-2000-1.osg36.%s' % dver,
                [x.nvr for x in self.promoter_36testing.tag_pkg_args[self.route_36testing.to_tag_hint % dver]])

    def test_add_promotion_with_nvr(self):
        self.promoter_36testing.add_promotion('goodpkg-2000-1.osg36.el8', ignore_signatures=True)
        for dver in self.route_36testing.dvers:
            self.assertIn(
                'goodpkg-2000-1.osg36.%s' % dver,
                [x.nvr for x in self.promoter_36testing.tag_pkg_args[self.route_36testing.to_tag_hint % dver]])

    def test_add_promotion_with_nvr_no_dist(self):
        self.promoter_36testing.add_promotion('goodpkg-2000-1', ignore_signatures=True)
        for dver in self.route_36testing.dvers:
            self.assertIn(
                'goodpkg-2000-1.osg36.%s' % dver,
                [x.nvr for x in self.promoter_36testing.tag_pkg_args[self.route_36testing.to_tag_hint % dver]])

    def test_add_promotion_with_signature_check(self):
        build_base = 'goodpkg-2000-1'
        for route, prom in [(self.route_36upcoming, self.promoter_36upcoming),
                            (self.route_23upcoming, self.promoter_23upcoming)]:
            repotag = route.repotag
            prom.add_promotion(build_base, ignore_signatures=False)
            self.assertEqual(prom.rejects, [])
            for dver in route.dvers:
                build = '%s.%s.%s' % (build_base, repotag, dver)
                self.assertIn(build, self._tagged_nvrs(prom, route, dver))

    def test_reject_signature(self):
        build_base = 'reject-invalid-key-1-1'
        route = self.route_23upcoming
        repotag = route.repotag
        self.promoter_23upcoming.add_promotion(build_base, ignore_signatures=False)
        self.assertNotEqual(self.promoter_23upcoming.rejects, [])
        self.assertTrue(all(
            x.reason == promoter.Reject.REASON_MISSING_REQUIRED_SIGNATURE for x in self.promoter_23upcoming.rejects))
        for dver in route.dvers:
            build = '%s.%s.%s' % (build_base, repotag, dver)
            self.assertNotIn(build,
                             self._tagged_nvrs(self.promoter_23upcoming, route, dver))

    def test_reject_add(self):
        self.promoter_36testing.add_promotion('goodpkg', ignore_signatures=True)
        self.promoter_36testing.add_promotion('reject-distinct-dvers', ignore_signatures=True)
        self.assertNotIn(
            'reject-distinct-dvers-1-1.osg36.el8',
            [x.nvr for x in self.promoter_36testing.tag_pkg_args[self.route_36testing.to_tag_hint % 'el8']])

    def test_reject_add_with_ignore(self):
        self.promoter_36testing.add_promotion('goodpkg', ignore_signatures=True)
        self.promoter_36testing.add_promotion('reject-distinct-dvers', ignore_rejects=True, ignore_signatures=True)
        self.assertIn(
            'reject-distinct-dvers-1-1.osg36.el8',
            [x.nvr for x in self.promoter_36testing.tag_pkg_args[self.route_36testing.to_tag_hint % 'el8']])
        self.assertIn(
            'reject-distinct-dvers-2-1.osg36.el7',
            [x.nvr for x in self.promoter_36testing.tag_pkg_args[self.route_36testing.to_tag_hint % 'el7']])

    def test_new_reject(self):
        self.promoter_36testing.add_promotion('reject-distinct-dvers', ignore_signatures=True)
        rejs = self.promoter_36testing.rejects
        self.assertEqual(1, len(rejs))
        self.assertEqual('reject-distinct-dvers', rejs[0].pkg_or_build)
        self.assertEqual(promoter.Reject.REASON_DISTINCT_ACROSS_DISTS, rejs[0].reason)

    def test_multi_promote(self):
        prom = self._make_promoter(self.multi_routes,
                                   dvers=self.route_23main.dvers)
        prom.add_promotion('goodpkg-2000-1', ignore_signatures=True)
        for dver in self.route_23main.dvers:
            for osgver, repo in [('23', '23-main'), ('3.6', '3.6')]:
                tag = 'osg-%s-%s-testing' % (repo, dver)
                dist = 'osg%s.%s' % (osgver.replace(".", ""), dver)
                pkg = 'goodpkg-2000-1.%s' % dist

                self.assertIn(tag, prom.tag_pkg_args)
                self.assertIn(pkg, [x.nvr for x in prom.tag_pkg_args[tag]])

    def test_cross_dist_reject(self):
        prom = self._make_promoter(self.multi_routes, ['el8'])
        prom.add_promotion('reject-distinct-repos', ignore_signatures=True)
        rejs = prom.rejects
        self.assertEqual(1, len(rejs))
        self.assertEqual(promoter.Reject.REASON_DISTINCT_ACROSS_DISTS, rejs[0].reason)

    def test_do_promotions(self):
        self.promoter_36testing.add_promotion('goodpkg', ignore_signatures=True)
        promoted_builds = self.promoter_36testing.do_promotions()
        self.assertEqual(3, len(self.kojihelper.newly_tagged_packages))
        for dver in self.route_36testing.dvers:
            tag = 'osg-3.6-%s-testing' % dver
            dist = 'osg36.%s' % dver
            nvr = 'goodpkg-2000-1.%s' % dist
            self.assertIn(tag, promoted_builds)
            self.assertIn(nvr, [x.nvr for x in promoted_builds[tag]])
            self.assertEqual(1, len(promoted_builds[tag]))
        self.assertEqual(3, len(promoted_builds))

    def test_do_multi_promotions(self):
        prom = self._make_promoter(self.multi_routes,
                                   dvers=self.route_23main.dvers)
        prom.add_promotion('goodpkg-2000-1', ignore_signatures=True)
        promoted_builds = prom.do_promotions()
        self.assertEqual(4, len(self.kojihelper.newly_tagged_packages))
        for osgver, repo in [('23', '23-main'), ('3.6', '3.6')]:
            for dver in self.route_23main.dvers:
                tag = 'osg-%s-%s-testing' % (repo, dver)
                dist = 'osg%s.%s' % (osgver.replace(".", ""), dver)
                nvr = 'goodpkg-2000-1.%s' % dist
                self.assertIn(tag, promoted_builds)
                self.assertIn(nvr, [x.nvr for x in promoted_builds[tag]])
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

    def _test_write_jira(self, real_promotions):
        out = StringIO()
        promoted_builds = {}
        if real_promotions:
            prom = self._make_promoter(self.multi_routes,
                                       dvers=self.route_23main.dvers)
            prom.add_promotion('goodpkg-2000-1', ignore_signatures=True)
            promoted_builds = prom.do_promotions()
        expected_lines = [
            "**Promotions**",
            "Promoted goodpkg-2000-1 to osg-23-main-el*-testing, osg-3.6-el*-testing",
            "**Build** | **Tag**",
            "--- | ---",
        ]
        for osgver, repo in [('23', '23-main'), ('3.6', '3.6')]:
            for dver in self.route_23main.dvers:
                tag = 'osg-%s-%s-testing' % (repo, dver)
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

    def test_write_jira(self):
        self._test_write_jira(real_promotions=False)

    def test_all(self):
        self._test_write_jira(real_promotions=True)


if __name__ == '__main__':
    unittest.main()
