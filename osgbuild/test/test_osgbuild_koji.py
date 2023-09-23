import grp
import os
import re
from os.path import join as opj
import pwd
import unittest
from unittest import TestCase

import osgbuild.constants as C
from osgbuild import main
from osgbuild.test.common import OSG_23_MAIN, OSG_36, common_setUp, backtick_osg_build, regex_in_list, checked_osg_build
from osgbuild.utils import CalledProcessError, errprintf


class TestKoji(TestCase):
    """Tests for koji"""

    def setUp(self):
        self.pkg_dir = common_setUp(opj(OSG_23_MAIN, "osg-xrootd"),
                                    "{2023-09-21}")

    kdr_shell = ["koji", "--dry-run", "--koji-backend=shell"]
    kdr_lib = ["koji", "--dry-run", "--koji-backend=kojilib"]

    build_target_lib_regex = r"^.*kojisession.build\([^,]+?, '%s'"
    build_target_shell_regex = r"(osg-)?koji .*build %s"

    def is_building_for(self, target, output):
        return (re.search(self.build_target_lib_regex % target, output, re.MULTILINE) or
                re.search(self.build_target_shell_regex % target, output, re.MULTILINE))

    def test_koji_shell_args1(self):
        output = backtick_osg_build(self.kdr_shell + ["--scratch", self.pkg_dir])
        self.assertTrue(self.is_building_for("osg.+el8", output),
                        "not building for el8")
        self.assertTrue(self.is_building_for("osg.+el9", output),
                        "not building for el9")

    def test_koji_shell_args2(self):
        output = backtick_osg_build(self.kdr_shell + ["--el9", "--scratch", self.pkg_dir])
        self.assertFalse(self.is_building_for("osg.+el8", output),
                         "falsely building for el8")
        self.assertTrue(self.is_building_for("osg.+el9", output),
                        "not building for el9")

    def test_koji_shell_args3(self):
        output = backtick_osg_build(self.kdr_shell + ["--ktt", "osg-23-main-el8", "--scratch", self.pkg_dir])
        self.assertFalse(
            self.is_building_for("osg.+el9", output),
            "falsely building for el9")
        self.assertTrue(
            self.is_building_for("osg.+el8", output),
            "not building for el8 for the right target")

    def test_koji_shell_args4(self):
        output = backtick_osg_build(self.kdr_shell + ["--el9", "--koji-target", "osg-23-main-el9", "--koji-tag", "TARGET", "--scratch", self.pkg_dir])
        out_list = output.split("\n")
        self.assertFalse(
            regex_in_list(r"Unable to determine redhat release", out_list),
            "Bad error with --koji-tag=TARGET")

    def test_koji_lib_args1(self):
        output = backtick_osg_build(self.kdr_lib + ["--scratch", self.pkg_dir])
        out_list = output.split("\n")
        self.assertTrue(
            regex_in_list(r".*kojisession.build\([^,]+?, 'osg.+el[89]', " + re.escape("{'scratch': True}") + r", None\)", out_list))

    def test_verify_correct_branch_svn(self):
        try:
            _ = backtick_osg_build(self.kdr_lib + ["--repo", "3.6-upcoming", "--dry-run", opj(C.SVN_ROOT, OSG_23_MAIN, "osg-xrootd")])
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
            _ = backtick_osg_build(self.kdr_lib + ["--repo", "3.6-upcoming", "--dry-run", scm_uri])
        except CalledProcessError as err:
            out_list = err.output.split("\n")
            self.assertTrue(
                regex_in_list(r".*Forbidden to build from .+ branch into .+ target", out_list),
                "did not detect attempt to build for wrong branch (wrong error message)")
            return
        self.fail("did not detect attempt to build for wrong branch (no error message)")


class TestKojiNewUpcoming(TestCase):
    def setUp(self):
        self.pkg_dir = common_setUp(opj(OSG_23_MAIN, "osg-xrootd"),
                                    "{2023-09-21}")

    kdr_shell = ["koji", "--dry-run", "--koji-backend=shell"]
    kdr_lib = ["koji", "--dry-run", "--koji-backend=kojilib"]

    build_target_lib_regex = r"^.*kojisession.build\([^,]+?, '%s'"
    build_target_shell_regex = r"(osg-)?koji .*build %s"

    def is_building_for(self, target, output):
        return (re.search(self.build_target_lib_regex % target, output, re.MULTILINE) or
                re.search(self.build_target_shell_regex % target, output, re.MULTILINE))

    def test_koji_lib_23upcoming(self):
        output = backtick_osg_build(self.kdr_lib + ["--repo", "23-upcoming", "--scratch", self.pkg_dir])
        self.assertTrue(self.is_building_for("osg-23-upcoming-el8", output))
        self.assertTrue(self.is_building_for("osg-23-upcoming-el9", output))

    def test_koji_lib_36upcoming(self):
        output = backtick_osg_build(self.kdr_lib + ["--repo", "3.6-upcoming", "--scratch", self.pkg_dir])
        self.assertTrue(self.is_building_for("osg-3.6-upcoming-el8", output))
        self.assertTrue(self.is_building_for("osg-3.6-upcoming-el9", output))

    def test_koji_shell_23upcoming(self):
        output = backtick_osg_build(self.kdr_shell + ["--repo", "23-upcoming", "--scratch", self.pkg_dir])
        self.assertTrue(self.is_building_for("osg-23-upcoming-el8", output))
        self.assertTrue(self.is_building_for("osg-23-upcoming-el9", output))

    def test_koji_shell_36upcoming(self):
        output = backtick_osg_build(self.kdr_shell + ["--repo", "3.6-upcoming", "--scratch", self.pkg_dir])
        self.assertTrue(self.is_building_for("osg-3.6-upcoming-el8", output))
        self.assertTrue(self.is_building_for("osg-3.6-upcoming-el9", output))


class TestKojiLong(TestCase):
    def setUp(self):
        self.pkg_dir = common_setUp(opj(OSG_23_MAIN, "osg-xrootd"),
                                    "{2023-09-21}")

    def test_koji_build(self):
        checked_osg_build(["koji", "--repo", "23-main", "--el9", "--scratch", self.pkg_dir, "--wait"])


class TestKojiMisc(TestCase):
    """Other Koji tests"""
    def test_cmdline_scratch_svn(self):
        buildopts = main.init(
            ["osg-build", "koji", "--scratch", "."])[0]
        self.assertFalse(buildopts['vcs'],
                         "vcs not false for scratch build")

        buildopts = main.init(
            ["osg-build", "koji", "."])[0]
        self.assertTrue(buildopts['vcs'],
                        "vcs not true for non-scratch build")


class TestMock(TestCase):
    """Tests for mock"""

    def setUp(self):
        self.pkg_dir = common_setUp(opj(OSG_36, "osg-ce"),
                                    "{2023-07-21}")

    @staticmethod
    def check_for_mock_group():
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
            checked_osg_build(["mock", self.pkg_dir, "--el9", "--mock-config-from-koji=osg-3.6-el9-build"])


if __name__ == '__main__':
    try:
        errprintf("testing %s", main)
        unittest.main()
    except CalledProcessError as e:
        errprintf("output: %s", e.output)
        raise
