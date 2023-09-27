#!/usr/bin/env python3
"""integration tests for the osg-build tasks
"""
# pylint: disable=C0103,R0904,W0614,C0111

import re
import os
from os.path import join as opj
import sys
import tarfile
import unittest
from unittest import makeSuite, TestCase

import osgbuild.constants as C
from osgbuild import srpm
from osgbuild.test.common import OSG_36, regex_in_list, go_to_temp_dir, common_setUp, \
    backtick_osg_build, checked_osg_build
from osgbuild.utils import (
    checked_backtick,
    checked_call,
    CalledProcessError,
    errprintf,
    unslurp)


class TestLint(TestCase):
    """Tests for 'lint' task"""

    def setUp(self):
        self.pkg_dir = common_setUp(opj(OSG_36, "condor"), "{2023-07-21}")

    def test_lint(self):
        out = backtick_osg_build(["lint", self.pkg_dir])
        try:
            self.assertRegexpMatches(
                out,
                re.escape("1 packages and 0 specfiles checked"),
                "unexpected number of packages checked")
            self.assertRegexpMatches(
                out,
                re.escape("rpmlint ok for condor"),
                "rpmlint not ok for condor")
        except:
            errprintf("Problems found. Output:\n%s", out)
            raise


class TestRpmbuild(TestCase):
    """Tests for 'rpmbuild' task"""

    def setUp(self):
        self.pkg_dir = common_setUp(opj(OSG_36, "osg-xrootd"),
                                    "{2023-07-21}")

    def test_rpmbuild(self):
        out = backtick_osg_build(["rpmbuild", self.pkg_dir])
        try:
            self.assertRegexpMatches(
                out,
                r'(?ms)The following RPM[(]s[)] have been created:\n',
                "rpm created message not found")
        except:
            errprintf("Problems found. Output:\n%s", out)
            raise


class TestPrebuild(TestCase):
    """Tests for 'prebuild' task"""

    def test_prebuild(self):
        pkg_dir = common_setUp(opj(OSG_36, "xrootd"),
                               "{2023-07-21}")
        checked_osg_build(["prebuild", pkg_dir])
        upstream_contents = os.listdir(opj(pkg_dir, C.WD_UNPACKED))
        final_contents = os.listdir(opj(pkg_dir, C.WD_PREBUILD))

        self.assertTrue(
            "xrootd.spec" in upstream_contents,
            "spec file not in upstream contents")
        self.assertTrue(
            "xrootd.tar.gz" in upstream_contents,
            "source tarball not in upstream contents")
        self.assertTrue(
            "xrootd.spec" in final_contents,
            "spec file not in final contents")
        self.assertTrue(
            "1868-env-hostname-override.patch" in final_contents,
            "osg patch not in final contents")
        self.assertTrue(
            regex_in_list(r"xrootd-5[.]6[.]1-1[.]1[.]osg[.]el\d+[.]src[.]rpm", final_contents),
            "srpm not successfully built")

    def test_prebuild_osgonly(self):
        pkg_osgonly_dir = common_setUp(opj(OSG_36, "osg-xrootd"),
                                       "{2023-07-21}")
        checked_osg_build(["prebuild", pkg_osgonly_dir])
        final_contents = os.listdir(opj(pkg_osgonly_dir, C.WD_PREBUILD))

        self.assertTrue(
            regex_in_list(
                r"osg-xrootd-3[.]6-20[.]osg[.]el\d+[.]src[.]rpm",
                final_contents),
            "srpm not successfully built")

    def test_prebuild_passthrough(self):
        pkg_passthrough_dir = common_setUp(opj(OSG_36, "htgettoken"),
                                           "{2023-07-21}")
        checked_osg_build(["prebuild", pkg_passthrough_dir])
        final_contents = os.listdir(opj(pkg_passthrough_dir, C.WD_PREBUILD))

        self.assertTrue(
            regex_in_list(
                r"htgettoken-1[.]18-1[.]osg[.]el\d+[.]src[.]rpm",
                final_contents),
            "srpm not successfully built")

    def test_prebuild_full_extract(self):
        pkg_dir = common_setUp(opj(OSG_36, "xrootd-multiuser"),
                               "{2023-07-21}")
        out = backtick_osg_build(["prebuild", "--full-extract", pkg_dir])
        ut_contents = os.listdir(opj(pkg_dir, C.WD_UNPACKED_TARBALL))
        tarball_contents = os.listdir(opj(pkg_dir, C.WD_UNPACKED_TARBALL,
                                           "xrootd-multiuser-2.1.3"))

        self.assertNotRegexpMatches(
            out,
            re.escape("cpio: premature end of archive"),
            "file unreadable by cpio")
        self.assertTrue(
            "README.md" in tarball_contents,
            "expected file not in unpacked sources")
# end of TestPrebuild


class TestPrepare(TestCase):
    """Tests for 'prepare' task"""

    def setUp(self):
        self.pkg_dir = common_setUp(opj(OSG_36, "xrootd-multiuser"),
                                    "{2023-07-21}")

    def test_prepare(self):
        checked_osg_build(["prepare", self.pkg_dir])
        srcdir = opj(self.pkg_dir, C.WD_RESULTS, "BUILD", "xrootd-multiuser-2.1.3")
        self.assertTrue(os.path.exists(srcdir), "SRPM not unpacked")
        try:
            checked_call(["grep", "-Fq", "ThreadSetgroups(0, nullptr)", opj(srcdir, "src/UserSentry.hh")])
        except CalledProcessError:
            self.fail("Patches not applied")


class TestFetch(TestCase):
    """Tests for fetch-sources"""
    @staticmethod
    def fetch_sources(pdir, nocheck=False):
        cmd = [sys.executable, "-m", "osgbuild.fetch_sources", pdir]
        if nocheck:
            cmd += ["--nocheck", "--quiet"]
        checked_call(cmd)
        return os.listdir(pdir)

    def test_cache_fetch(self):
        common_setUp(opj(OSG_36, "xrootd"), "{2023-07-21}")
        contents = self.fetch_sources("xrootd")

        self.assertTrue(
            "xrootd.spec" in contents,
            "spec file not found")
        self.assertTrue(
            "xrootd.tar.gz" in contents,
            "source tarball not found")
        head_out = checked_backtick(
            ["head", "-n", "1", "xrootd/xrootd.spec"])
        self.assertRegexpMatches(
            head_out,
            r"# OSG additions",
            "Spec file not overridden")

    def test_git_fetch(self):
        common_setUp(opj(OSG_36, "xrootd-multiuser"), "{2023-07-21}")
        contents = self.fetch_sources("xrootd-multiuser")

        self.assertTrue(
            "xrootd-multiuser.spec" in contents,
            "spec file not found")
        self.assertTrue(
            "xrootd-multiuser-2.1.3.tar.gz" in contents,
            "source tarball not found")

    def test_git_fetch_with_release(self):
        go_to_temp_dir()
        os.mkdir("upstream")
        unslurp("upstream/github.source",
                "type=git url=https://github.com/opensciencegrid/cvmfs-config-osg.git tag=v2.1-2 hash=5ea1914b621cef204879ec1cc55e0216e3812785")
        contents = self.fetch_sources(".")

        self.assertFalse("cvmfs-config-osg-2.1-2.tar.gz" in contents, "source tarball has incorrect name")
        self.assertTrue("cvmfs-config-osg-2.1.tar.gz" in contents, "source tarball not found")

    def test_github_fetch_with_release(self):
        go_to_temp_dir()
        os.mkdir("upstream")
        unslurp("upstream/github.source",
                "type=github repo=opensciencegrid/cvmfs-config-osg tag=v2.1-2 hash=5ea1914b621cef204879ec1cc55e0216e3812785")
        contents = self.fetch_sources(".")

        self.assertFalse("cvmfs-config-osg-2.1-2.tar.gz" in contents, "source tarball has incorrect name")
        self.assertTrue("cvmfs-config-osg-2.1.tar.gz" in contents, "source tarball not found")

    def test_github_fetch_with_tarball(self):
        go_to_temp_dir()
        tarball = "tarfile.tar.gz"
        hash = "5ea1914b621cef204879ec1cc55e0216e3812785"
        os.mkdir("upstream")
        unslurp("upstream/github.source",
                "type=github repo=opensciencegrid/cvmfs-config-osg tag=v2.1-2 tarball=%s hash=%s"
                % (tarball, hash))
        contents = self.fetch_sources(".")

        self.assertTrue(tarball in contents, "source tarball not found")

        tarfh = tarfile.open(tarball, "r")
        try:
            try:
                tardir = tarfh.getmember("tarfile")
            except KeyError:
                self.fail("directory not found in tarball")
            self.assertTrue(tardir.isdir(), "directory not a directory in tarball")
        finally:
            tarfh.close()
        tarhash = checked_backtick("gunzip -c %s | git get-tar-commit-id" % tarball, shell=True)
        self.assertEqual(hash, tarhash, "source tarball has wrong hash")

    def test_github_fetch_wrong_hash(self):
        go_to_temp_dir()
        os.mkdir("upstream")
        unslurp("upstream/github.source",
                "type=github repo=opensciencegrid/cvmfs-config-osg tag=v2.1-2 hash=0000000000000000000000000000000000000000")
        self.assertRaises(CalledProcessError, self.fetch_sources, ".", nocheck=False)
        contents = self.fetch_sources(".", nocheck=True)

        self.assertTrue("cvmfs-config-osg-2.1.tar.gz" in contents, "source tarball not found")

    def test_osgbuild_prebuild_fetch_wrong_hash(self):
        go_to_temp_dir()
        os.mkdir("upstream")
        unslurp("upstream/github.source",
                "type=github repo=opensciencegrid/cvmfs-config-osg tag=v2.1 hash=0000000000000000000000000000000000000000")
        checked_osg_build(["prebuild"])
        contents = os.listdir(C.WD_PREBUILD)

        self.assertTrue(
            regex_in_list(
                r"cvmfs-config-osg-2[.]1-1[.]osg[.]el\d[.]src[.]rpm",
                contents),
            "srpm not successfully built")


class TestMisc(TestCase):
    """Other tests"""

    def test_rpmbuild_defines(self):
        buildopts_el = dict()
        build_el = dict()
        defines_el = dict()
        for dver in ['el8', 'el7']:
            rhel = dver[2:]
            buildopts_el[dver] = C.DEFAULT_BUILDOPTS_COMMON.copy()
            buildopts_el[dver]['redhat_release'] = dver
            buildopts_el[dver].update(C.DEFAULT_BUILDOPTS_BY_DVER[dver])
            build_el[dver] = srpm.SRPMBuild(".", buildopts_el[dver], None, None)
            defines_el[dver] = build_el[dver].get_rpmbuild_defines(True)
            self.assertTrue("--define=rhel %s" % rhel in defines_el[dver],
                            "%%rhel not set correctly for %s build" % dver)

        self.assertTrue('--define=el8 0' in defines_el['el7'],
                        "%el8 not unset for el7 build")
        self.assertTrue('--define=el7 1' in defines_el['el7'],
                        "%el7 not set for el7 build")

        self.assertTrue('--define=el8 1' in defines_el['el8'],
                        "%el8 not set for el8 build")
        self.assertTrue('--define=el7 0' in defines_el['el8'],
                        "%el7 not unset for el8 build")

    def test_version(self):
        try:
            _ = backtick_osg_build(["--version"])
        except (CalledProcessError, OSError):
            self.fail("osg-build --version failed")


short_test_cases = (TestLint, TestRpmbuild, TestPrebuild, TestPrepare, TestFetch, TestMisc)
TestSuiteShort = unittest.TestSuite()
TestSuiteShort.addTests([makeSuite(t) for t in short_test_cases])
TestSuiteAll = TestSuiteShort  # backward compat

if __name__ == '__main__':
    try:
        import osgbuild.main
        errprintf("testing %s", osgbuild.main)
        unittest.main()
    except CalledProcessError as e:
        errprintf("output: %s", e.output)
        raise
