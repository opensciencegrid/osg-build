#!/usr/bin/env python
"""integration tests for the osg-build tasks
"""
# pylint: disable=C0103,R0904,W0614,C0111

import grp
import re
import os
from os.path import join as opj
import pwd
import tarfile
import unittest
from unittest import makeSuite, TestCase

import osgbuild.constants as C
from osgbuild import main
from osgbuild import srpm
from osgbuild.test.common import OSG_36, regex_in_list, get_osg_build_path, go_to_temp_dir, common_setUp, \
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
                re.escape("rpmlint found problems with condor"),
                "expected problems not found")
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
        cmd = ["python", "-m", "osgbuild.fetch_sources", pdir]
        if nocheck:
            cmd.append("--nocheck")
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



class TestMock(TestCase):
    """Tests for mock"""

    def setUp(self):
        self.pkg_dir = common_setUp(opj(OSG_36, "osg-ce"),
                                    "{2023-07-21}")

    def check_for_mock_group(self):
        username = pwd.getpwuid(os.getuid()).pw_name
        try:
            mock_group = grp.getgrnam('mock')
        except KeyError:
            errprintf("mock group not found")
            return False
        try:
            if username in mock_group.gr_mem:
                return True
        except AttributeError:
            pass
        errprintf("%s not in mock group", username)
        return False

    def test_mock_koji_cfg(self):
        if self.check_for_mock_group():
            checked_osg_build(["mock", self.pkg_dir, "--el7", "--mock-config-from-koji=osg-3.6-el7-build"])


class TestKoji(TestCase):
    """Tests for koji"""

    def setUp(self):
        self.pkg_dir = common_setUp(opj(OSG_36, "osg-ce"),
                                    "{2023-07-21}")

    kdr_shell = ["koji", "--dry-run", "--koji-backend=shell"]
    kdr_lib = ["koji", "--dry-run", "--koji-backend=kojilib"]

    build_target_lib_regex = r"^.*kojisession.build\([^,]+?, '%s'"
    build_target_shell_regex = r"(osg-)?koji .*build %s"

    def is_building_for(self, target, output):
        return (re.search(self.build_target_lib_regex % target, output, re.MULTILINE) or
                re.search(self.build_target_shell_regex % target, output, re.MULTILINE))

    def test_koji_shell_args1(self):
        output = backtick_osg_build(self.kdr_shell + ["--scratch", self.pkg_dir])
        self.assertTrue(self.is_building_for("osg.+el7", output),
                        "not building for el7")
        self.assertTrue(self.is_building_for("osg.+el8", output),
                        "not building for el8")
        self.assertTrue(self.is_building_for("osg.+el9", output),
                        "not building for el9")

    def test_koji_shell_args2(self):
        output = backtick_osg_build(self.kdr_shell + ["--el7", "--scratch", self.pkg_dir])
        self.assertTrue(self.is_building_for("osg.+el7", output),
                        "not building for el7")
        self.assertFalse(self.is_building_for("osg.+el8", output),
                         "falsely building for el8")

    def test_koji_shell_args3(self):
        output = backtick_osg_build(self.kdr_shell + ["--ktt", "osg-el8", "--scratch", self.pkg_dir])
        self.assertFalse(
            self.is_building_for("osg.+el7", output),
            "falsely building for el7")
        self.assertTrue(
            self.is_building_for("osg.+el8", output),
            "not building for el8 for the right target")

    def test_koji_shell_args4(self):
        output = backtick_osg_build(self.kdr_shell + ["--el7", "--koji-target", "osg-el7", "--koji-tag", "TARGET", "--scratch", self.pkg_dir])
        out_list = output.split("\n")
        self.assertFalse(
            regex_in_list(r"Unable to determine redhat release", out_list),
            "Bad error with --koji-tag=TARGET")

    def test_koji_lib_args1(self):
        output = backtick_osg_build(self.kdr_lib + ["--scratch", self.pkg_dir])
        out_list = output.split("\n")
        self.assertTrue(
            regex_in_list(r".*kojisession.build\([^,]+?, 'osg.+el[78]', " + re.escape("{'scratch': True}") + r", None\)", out_list))

    def test_verify_correct_branch_svn(self):
        try:
            _ = backtick_osg_build(self.kdr_lib + ["--3.6-upcoming", "--dry-run", opj(C.SVN_ROOT, OSG_36, "osg-xrootd")])
        except CalledProcessError as err:
            out_list = err.output.split("\n")
            self.assertTrue(
                regex_in_list(r".*Forbidden to build from .+ branch into .+ target", out_list),
                "did not detect attempt to build for wrong branch (wrong error message)")
            return
        self.fail("did not detect attempt to build for wrong branch (no error message)")

    def test_verify_correct_branch_git(self):
        try:
            # SCM URI format is 'git+https://host/.../repo.git?path#revision'
            gitbranch = re.sub(r"^native/redhat/branches/", "", OSG_36)
            scm_uri = "git+%s?%s#%s" % (C.OSG_REMOTE, "osg-xrootd", gitbranch)
            _ = backtick_osg_build(self.kdr_lib + ["--3.6-upcoming", "--dry-run", scm_uri])
        except CalledProcessError as err:
            out_list = err.output.split("\n")
            self.assertTrue(
                regex_in_list(r".*Forbidden to build from .+ branch into .+ target", out_list),
                "did not detect attempt to build for wrong branch (wrong error message)")
            return
        self.fail("did not detect attempt to build for wrong branch (no error message)")


class TestKojiNewUpcoming(TestCase):
    def setUp(self):
        self.pkg_dir = common_setUp(opj(OSG_36, "osg-xrootd"),
                                    "{2023-07-21}")

    kdr_shell = ["koji", "--dry-run", "--koji-backend=shell"]
    kdr_lib = ["koji", "--dry-run", "--koji-backend=kojilib"]

    build_target_lib_regex = r"^.*kojisession.build\([^,]+?, '%s'"
    build_target_shell_regex = r"(osg-)?koji .*build %s"

    def is_building_for(self, target, output):
        return (re.search(self.build_target_lib_regex % target, output, re.MULTILINE) or
                re.search(self.build_target_shell_regex % target, output, re.MULTILINE))

    def test_koji_lib_35upcoming(self):
        output = backtick_osg_build(self.kdr_lib + ["--repo", "3.5-upcoming", "--scratch", self.pkg_dir])
        self.assertTrue(self.is_building_for("osg-3.5-upcoming-el7", output))
        self.assertTrue(self.is_building_for("osg-3.5-upcoming-el8", output))

    def test_koji_lib_35upcoming_shorthand(self):
        output = backtick_osg_build(self.kdr_lib + ["--3.5-upcoming", "--scratch", self.pkg_dir])
        self.assertTrue(self.is_building_for("osg-3.5-upcoming-el7", output))
        self.assertTrue(self.is_building_for("osg-3.5-upcoming-el8", output))

    def test_koji_lib_36upcoming(self):
        output = backtick_osg_build(self.kdr_lib + ["--repo", "3.6-upcoming", "--scratch", self.pkg_dir])
        self.assertTrue(self.is_building_for("osg-3.6-upcoming-el7", output))
        self.assertTrue(self.is_building_for("osg-3.6-upcoming-el8", output))

    def test_koji_lib_36upcoming_shorthand(self):
        output = backtick_osg_build(self.kdr_lib + ["--3.6-upcoming", "--scratch", self.pkg_dir])
        self.assertTrue(self.is_building_for("osg-3.6-upcoming-el7", output))
        self.assertTrue(self.is_building_for("osg-3.6-upcoming-el8", output))

    def test_koji_shell_35upcoming(self):
        output = backtick_osg_build(self.kdr_shell + ["--repo", "3.5-upcoming", "--scratch", self.pkg_dir])
        self.assertTrue(self.is_building_for("osg-3.5-upcoming-el7", output))
        self.assertTrue(self.is_building_for("osg-3.5-upcoming-el8", output))

    def test_koji_shell_36upcoming(self):
        output = backtick_osg_build(self.kdr_shell + ["--repo", "3.6-upcoming", "--scratch", self.pkg_dir])
        self.assertTrue(self.is_building_for("osg-3.6-upcoming-el7", output))
        self.assertTrue(self.is_building_for("osg-3.6-upcoming-el8", output))


class TestKojiLong(TestCase):
    def setUp(self):
        self.pkg_dir = common_setUp(opj(OSG_36, "osg-xrootd"),
                                    "{2023-07-21}")

    def test_koji_build(self):
        checked_osg_build(["koji", "--el7", "--scratch", self.pkg_dir, "--wait"])


class TestMisc(TestCase):
    """Other tests"""

    def test_cmdline_scratch_svn(self):
        buildopts = main.init(
            ["osg-build", "koji", "--scratch", "."])[0]
        self.assertFalse(buildopts['vcs'],
                         "vcs not false for scratch build")

        buildopts = main.init(
            ["osg-build", "koji", "."])[0]
        self.assertTrue(buildopts['vcs'],
                        "vcs not true for non-scratch build")

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


short_test_cases = (TestLint, TestRpmbuild, TestPrebuild, TestPrepare, TestFetch, TestMisc, TestKoji, TestKojiNewUpcoming)
TestSuiteShort = unittest.TestSuite()
TestSuiteShort.addTests([makeSuite(t) for t in short_test_cases])
# Make sure TestKojiLong comes first since it requires user interaction.
TestSuiteAll = unittest.TestSuite((makeSuite(TestKojiLong), TestSuiteShort, makeSuite(TestMock)))

if __name__ == '__main__':
    try:
        errprintf("testing %s", get_osg_build_path())
        unittest.main()
    except CalledProcessError as e:
        errprintf("output: %s", e.output)
        raise
