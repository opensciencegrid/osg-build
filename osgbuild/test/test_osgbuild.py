#!/usr/bin/python
"""unit tests for the osg-build tasks
"""
# pylint: disable=C0103,R0904,W0614,C0111

import atexit
import grp
import re
import os
from os.path import join as opj
import pwd
import shutil
import tempfile
import tarfile
import unittest
from unittest import makeSuite
import sys

import osgbuild.constants as C
from osgbuild import main
from osgbuild import srpm
from osgbuild.utils import (
    checked_backtick,
    checked_call,
    CalledProcessError,
    find_file,
    errprintf,
    unslurp)

TRUNK = "native/redhat/trunk"

initial_wd = os.getcwd()
osg_build_path = find_file('osg-build', [initial_wd,
                                         '/usr/bin'])

if not osg_build_path:
    errprintf("osg-build script not found!")
    sys.exit(255)

osg_build_command = [osg_build_path]


def go_to_temp_dir():
    working_dir = tempfile.mkdtemp(prefix="osg-build-test-")
    atexit.register(shutil.rmtree, working_dir)
    os.chdir(working_dir)
    return working_dir


def common_setUp(path, rev):
    """Create a temporary directory, ensure it gets deleted on exit, cd to it,
    and check out a specific revision of a path from our SVN.

    """
    working_dir = go_to_temp_dir()
    svn_export(path, rev, os.path.basename(path))
    return opj(working_dir, os.path.basename(path))


def backtick_osg_build(cmd_args, *args, **kwargs):
    kwargs['clocale'] = True
    kwargs['err2out'] = True
    return checked_backtick(osg_build_command + cmd_args, *args, **kwargs)


def checked_osg_build(cmd_args, *args, **kwargs):
    return checked_call(osg_build_command + cmd_args, *args, **kwargs)


def svn_export(path, rev, destpath):
    """Run svn export on a revision rev of path into destpath"""
    try:
        checked_backtick(
            ["svn", "export", opj(C.SVN_ROOT, path) + "@" + rev, "-r", rev, destpath],
            err2out=True)
    except CalledProcessError as err:
        errprintf("Error in svn export:\n%s", err.output)
        raise


def get_listing(directory):
    return checked_backtick(
            ["ls", directory]).split("\n")


def regex_in_list(pattern, listing):
    return [x for x in listing if re.match(pattern, x)]


class XTestCase(unittest.TestCase):
    """XTestCase (extended test case) adds some useful assertions to
    unittest.TestCase

    """
    # unittest.TestCase does not have a failureException in 2.4
    failureException = getattr(super, 'failureException', AssertionError)

    # Code from unittest in Python 2.7 (c) Python Software Foundation
    def assertRegexpMatches(self, text, regexp, msg=None):
        """Fail if 'text' does not match 'regexp'"""
        if isinstance(regexp, re._pattern_type):
            re_pattern = regexp
        else:
            re_pattern = re.compile(regexp)
        if not re_pattern.search(text):
            msg = msg or "Regexp didn't match"
            msg = '%s: %r not found in %r' % (msg, re_pattern.pattern, text)
            raise self.failureException(msg)

    # Code from unittest in Python 2.7 (c) Python Software Foundation
    def assertNotRegexpMatches(self, text, regexp, msg=None):
        """Fail if 'text' matches 'regex'"""
        if isinstance(regexp, re._pattern_type):
            re_pattern = regexp
        else:
            re_pattern = re.compile(regexp)
        match = re_pattern.search(text)
        if match:
            msg = msg or "Regexp matched"
            msg = '%s: %r matches %r in %r' % (msg, text[match.start():match.end()], re_pattern.pattern, text)
            raise self.failureException(msg)


class TestLint(XTestCase):
    """Tests for 'lint' task"""

    def setUp(self):
        self.pkg_dir = common_setUp(opj(TRUNK, "yum-remove-osg"), "{2011-12-06}")

    def test_lint(self):
        out = backtick_osg_build(["lint", self.pkg_dir])
        try:
            self.assertRegexpMatches(
                out,
                re.escape("yum-remove-osg.src:25: E: hardcoded-library-path"),
                "expected error not found")
            self.assertRegexpMatches(
                out,
                re.escape("1 packages and 0 specfiles checked"),
                "unexpected number of packages checked")
            self.assertRegexpMatches(
                out,
                re.escape("rpmlint found problems with yum-remove-osg"),
                "expected problems not found")
        except:
            errprintf("Problems found. Output:\n%s", out)
            raise


class TestRpmbuild(XTestCase):
    """Tests for 'rpmbuild' task"""

    def setUp(self):
        self.pkg_dir = common_setUp(opj(TRUNK, "yum-remove-osg"),
                                    "{2011-12-06}")

    def test_rpmbuild(self):
        out = backtick_osg_build(["rpmbuild", self.pkg_dir])
        try:
            self.assertRegexpMatches(
                out,
                r'(?ms) >> The following RPM[(]s[)] have been created:\n'
                r'[^\n]+'
                r'yum-remove-osg-1[.]0-0[.]2[.]osg[.]el\d[.]noarch[.]rpm',
                "rpm created message not found")
        except:
            errprintf("Problems found. Output:\n%s", out)
            raise


class TestPrebuild(XTestCase):
    """Tests for 'prebuild' task"""

    def test_prebuild(self):
        pkg_dir = common_setUp(opj(TRUNK, "mash"),
                               "{2011-12-08}")
        checked_osg_build(["prebuild", pkg_dir])
        upstream_contents = get_listing(opj(pkg_dir, C.WD_UNPACKED))
        final_contents = get_listing(opj(pkg_dir, C.WD_PREBUILD))

        self.assertTrue(
            "mash.spec" in upstream_contents,
            "spec file not in upstream contents")
        self.assertTrue(
            "mash-0.5.22.tar.gz" in upstream_contents,
            "source tarball not in upstream contents")
        self.assertTrue(
            "mash.spec" in final_contents,
            "spec file not in final contents")
        self.assertTrue(
            "multilib-python.patch" in final_contents,
            "osg patch not in final contents")
        self.assertTrue(
            regex_in_list(r"mash-0[.]5[.]22-2[.]osg[.]el\d[.]src[.]rpm", final_contents),
            "srpm not successfully built")

    def test_prebuild_osgonly(self):
        pkg_osgonly_dir = common_setUp(opj(TRUNK, "yum-remove-osg"),
                                       "{2012-01-26}")
        checked_osg_build(["prebuild", pkg_osgonly_dir])
        final_contents = get_listing(opj(pkg_osgonly_dir, C.WD_PREBUILD))

        self.assertTrue(
            regex_in_list(
                r"yum-remove-osg-1[.]0-0[.]2[.]osg.el\d[.]src[.]rpm",
                final_contents),
            "srpm not successfully built")

    def test_prebuild_passthrough(self):
        pkg_passthrough_dir = common_setUp(opj(TRUNK, "globus-core"),
                                           "{2012-01-26}")
        checked_osg_build(["prebuild", pkg_passthrough_dir])
        final_contents = get_listing(opj(pkg_passthrough_dir, C.WD_PREBUILD))

        self.assertTrue(
            regex_in_list(
                r"globus-core-8[.]5-2[.]osg[.]el\d[.]src[.]rpm",
                final_contents),
            "srpm not successfully built")

    def test_prebuild_full_extract(self):
        pkg_dir = common_setUp(opj(TRUNK, "mash"),
                               "{2011-12-08}")
        out = backtick_osg_build(["prebuild", "--full-extract", pkg_dir])
        ut_contents = get_listing(opj(pkg_dir, C.WD_UNPACKED_TARBALL))
        tarball_contents = get_listing(opj(pkg_dir, C.WD_UNPACKED_TARBALL,
                                           "mash-0.5.22"))

        self.assertNotRegexpMatches(
            out,
            re.escape("cpio: premature end of archive"),
            "file unreadable by cpio")
        self.assertTrue(
            "mash.spec" in ut_contents,
            "spec file not in unpacked tarball dir")
        self.assertTrue(
            "README" in tarball_contents,
            "expected file not in unpacked sources")
# end of TestPrebuild


class TestPrepare(XTestCase):
    """Tests for 'prepare' task"""

    def setUp(self):
        self.pkg_dir = common_setUp(opj(TRUNK, "globus-gatekeeper"),
                                    "{2011-12-14}")

    def test_prepare(self):
        checked_osg_build(["prepare", self.pkg_dir])
        self.assertTrue(os.path.exists(opj(self.pkg_dir, C.WD_RESULTS, "BUILD",
                        "globus_gatekeeper-8.1")), "SRPM unpacked")
        head_out = checked_backtick(
            ["head", "-n", "10", opj(self.pkg_dir, C.WD_RESULTS, "BUILD",
            "globus_gatekeeper-8.1", "init", "globus-gatekeeper-lsb.in")])
        self.assertRegexpMatches(
            head_out,
            r"Default-Stop:\s+0 1 2 3 4 5 6",
            "Patches not applied")


class TestFetch(XTestCase):
    """Tests for fetch-sources"""
    @staticmethod
    def fetch_sources(pdir, nocheck=False):
        cmd = ["python", "-m", "osgbuild.fetch_sources", pdir]
        if nocheck:
            cmd.append("--nocheck")
        checked_call(cmd)
        return get_listing(pdir)

    def test_cache_fetch(self):
        common_setUp(opj(TRUNK, "mash"), "{2011-12-08}")
        contents = self.fetch_sources("mash")

        self.assertTrue(
            "mash.spec" in contents,
            "spec file not found")
        self.assertTrue(
            "mash-0.5.22.tar.gz" in contents,
            "source tarball not found")
        head_out = checked_backtick(
            ["head", "-n", "15", "mash/mash.spec"])
        self.assertRegexpMatches(
            head_out,
            r"Patch0:\s+multilib-python.patch",
            "Spec file not overridden")

    def test_git_fetch(self):
        common_setUp("native/redhat/branches/matyas/osg-build", "{2017-04-26}")
        contents = self.fetch_sources("osg-build")

        self.assertTrue(
            "osg-build.spec" in contents,
            "spec file not found")
        self.assertTrue(
            "osg-build-1.8.90.tar.gz" in contents,
            "source tarball not found")

    def test_git_fetch_spec(self):
        common_setUp(opj(TRUNK, "osg-build"), "{2018-01-24}")
        contents = self.fetch_sources("osg-build")

        self.assertTrue(
            "osg-build.spec" in contents,
            "spec file not found")
        self.assertTrue(
            "osg-build-1.11.1.tar.gz" in contents,
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
        os.mkdir("upstream")
        unslurp("upstream/github.source",
                "type=github repo=opensciencegrid/cvmfs-config-osg tag=v2.1-2 tarball=tarfile.tar.gz hash=5ea1914b621cef204879ec1cc55e0216e3812785")
        contents = self.fetch_sources(".")

        self.assertTrue("tarfile.tar.gz" in contents, "source tarball not found")

        tarfh = tarfile.open("./tarfile.tar.gz", "r")
        try:
            try:
                tardir = tarfh.getmember("tarfile")
            except KeyError:
                self.fail("directory not found in tarball")
            self.assertTrue(tardir.isdir(), "directory not a directory in tarball")
        finally:
            tarfh.close()

    def test_github_fetch_hash_only(self):
        go_to_temp_dir()
        tarball = "tarfile.tar.gz"
        hash = "5ea1914b621cef204879ec1cc55e0216e3812785"
        os.mkdir("upstream")
        unslurp("upstream/github.source",
                "type=github repo=opensciencegrid/cvmfs-config-osg tarball=%s hash=%s" % (tarball, hash))
        self.assertRaises(CalledProcessError, self.fetch_sources, ".", nocheck=False)
        contents = self.fetch_sources(".", nocheck=True)

        self.assertTrue(tarball in contents, "source tarball not found")
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
        contents = get_listing(C.WD_PREBUILD)

        self.assertTrue(
            regex_in_list(
                r"cvmfs-config-osg-2[.]1-1[.]osg[.]el\d[.]src[.]rpm",
                contents),
            "srpm not successfully built")



class TestMock(XTestCase):
    """Tests for mock"""

    def setUp(self):
        self.pkg_dir = common_setUp(opj(TRUNK, "koji"),
                                    "{2012-01-25}")

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
            checked_osg_build(["mock", self.pkg_dir, "--el7", "--mock-config-from-koji=osg-3.4-el7-build"])


class TestKoji(XTestCase):
    """Tests for koji"""

    def setUp(self):
        self.pkg_dir = common_setUp(opj(TRUNK, "koji"),
                                    "{2012-01-25}")

    kdr_shell = ["koji", "--dry-run", "--koji-backend=shell"]
    kdr_lib = ["koji", "--dry-run", "--koji-backend=kojilib"]
    def test_koji_shell_args1(self):
        output = backtick_osg_build(self.kdr_shell + ["--scratch", self.pkg_dir])
        out_list = output.split("\n")
        self.assertTrue(
            regex_in_list(r"(osg-)?koji .*build osg-el7", out_list),
            "not building for el7")
        self.assertTrue(
            regex_in_list(r"(osg-)?koji .*build osg-el6", out_list),
            "not building for el6")

    def test_koji_shell_args2(self):
        output = backtick_osg_build(self.kdr_shell + ["--el7", "--scratch", self.pkg_dir])
        out_list = output.split("\n")
        self.assertTrue(
            regex_in_list(r"(osg-)?koji .*build osg-el7", out_list),
            "not building for el7")
        self.assertFalse(
            regex_in_list(r"(osg-)?koji .*build osg-el6", out_list),
            "falsely building for el6")

    def test_koji_shell_args3(self):
        output = backtick_osg_build(self.kdr_shell + ["--ktt", "osg-el6", "--scratch", self.pkg_dir])
        out_list = output.split("\n")
        self.assertFalse(
            regex_in_list(r"(osg-)?koji .*build osg-el7", out_list),
            "falsely building for el7")
        self.assertTrue(
            regex_in_list(r"(osg-)?koji .*build osg-el6", out_list),
            "not building for el6 for the right target")

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
            regex_in_list(r".*kojisession.build\([^,]+?, 'osg-el[76]', " + re.escape("{'scratch': True}") + r", None\)", out_list))

    def test_koji_lib_upcoming(self):
        output = backtick_osg_build(self.kdr_lib + ["--upcoming", "--scratch", self.pkg_dir])
        out_list = output.split("\n")
        self.assertTrue(regex_in_list(r".*kojisession.build\([^,]+?, 'osg-upcoming-el7'", out_list))
        self.assertTrue(regex_in_list(r".*kojisession.build\([^,]+?, 'osg-upcoming-el6'", out_list))

    def test_koji_lib_upcoming2(self):
        # Make sure that passing --el5 turns off el6 builds even with --upcoming.
        output = backtick_osg_build(self.kdr_lib + ["--upcoming", "--scratch", "--el7", self.pkg_dir])
        out_list = output.split("\n")
        self.assertTrue(regex_in_list(r".*kojisession.build\([^,]+?, 'osg-upcoming-el7'", out_list))
        self.assertFalse(regex_in_list(r".*kojisession.build\([^,]+?, 'osg-upcoming-el6'", out_list))

    def test_koji_shell_upcoming(self):
        output = backtick_osg_build(self.kdr_shell + ["--el7", "--upcoming", "--scratch", self.pkg_dir])
        out_list = output.split("\n")
        self.assertTrue(
            regex_in_list(r"(osg-)?koji .*build osg-upcoming-el7", out_list),
            "not building for el7-upcoming")
        self.assertFalse(
            regex_in_list(r"(osg-)?koji .*build osg-upcoming-el6", out_list),
            "falsely building for el6-upcoming")

    def test_verify_correct_branch(self):
        try:
            _ = backtick_osg_build(self.kdr_lib + ["--upcoming", "--dry-run", opj(C.SVN_ROOT, 'native/redhat/trunk/koji')])
        except CalledProcessError as err:
            out_list = err.output.split("\n")
            self.assertTrue(
                regex_in_list(r".*Forbidden to build from .+ branch into .+ target", out_list),
                "did not detect attempt to build for wrong branch (wrong error message)")
            return
        self.fail("did not detect attempt to build for wrong branch (no error message)")


class TestKojiLong(XTestCase):
    def setUp(self):
        self.pkg_dir = common_setUp(opj(TRUNK, "koji"),
                                    "{2012-01-25}")
        self.arch_pkg_dir = common_setUp(opj(TRUNK, "osg-ce"),
                                    "{2014-12-17}")

    def test_koji_build(self):
        checked_osg_build(["koji", "--el7", "--scratch", self.pkg_dir, "--wait"])

    def test_koji_build_with_target_arch(self):
        output = backtick_osg_build(["koji", "--el6", "--scratch", "--target-arch=x86_64", self.arch_pkg_dir, "--wait"])
        self.assertNotRegexpMatches(
            output,
            r".*buildArch [(][^)]+?i[3-6]86[)]",
            "Building for 32-bit platform even though x86_64 arch was requested")
        self.assertRegexpMatches(
            output,
            r".*buildArch [(][^)]+?x86_64[)]",
            "Not building for 64-bit platform even though x86_64 arch was requested")


class TestMisc(XTestCase):
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
        for dver in ['el6', 'el7']:
            rhel = dver[2:]
            buildopts_el[dver] = C.DEFAULT_BUILDOPTS_COMMON.copy()
            buildopts_el[dver]['redhat_release'] = dver
            buildopts_el[dver].update(C.DEFAULT_BUILDOPTS_BY_DVER[dver])
            build_el[dver] = srpm.SRPMBuild(".", buildopts_el[dver], None, None)
            defines_el[dver] = build_el[dver].get_rpmbuild_defines(True)
            self.assertTrue("--define=rhel %s" % rhel in defines_el[dver],
                            "%%rhel not set correctly for %s build" % dver)

        self.assertTrue('--define=el6 0' in defines_el['el7'],
                        "%el6 not unset for el7 build")
        self.assertTrue('--define=el7 1' in defines_el['el7'],
                        "%el7 not set for el7 build")

        self.assertTrue('--define=el6 1' in defines_el['el6'],
                        "%el6 not set for el6 build")
        self.assertTrue('--define=el7 0' in defines_el['el6'],
                        "%el7 not unset for el6 build")


short_test_cases = (TestLint, TestRpmbuild, TestPrebuild, TestPrepare, TestFetch, TestMisc, TestKoji)
TestSuiteShort = unittest.TestSuite()
TestSuiteShort.addTests([makeSuite(t) for t in short_test_cases])
# Make sure TestKoji comes first since it requires user interaction.
TestSuiteAll = unittest.TestSuite((makeSuite(TestKojiLong), TestSuiteShort, makeSuite(TestMock)))

if __name__ == '__main__':
    try:
        errprintf("testing %s", osg_build_path)
        unittest.main()
    except CalledProcessError as e:
        errprintf("output: %s", e.output)
        raise
