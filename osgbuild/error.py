"""Exception classes for osg-build"""
# pylint: disable=C0103,C0111
import os
import traceback

class Error(Exception):
    """Base class for expected exceptions"""
    def __init__(self, msg, tb=None):
        Exception.__init__(self)
        self.msg = msg
        if tb is None:
            self.traceback = traceback.format_exc()

    def __repr__(self):
        return repr((self.msg, self.traceback))

    def __str__(self):
        return str(self.msg)


class ConfigErrors(Error):
    """Class for errors when validating config; can contain multiple errors."""
    def __init__(self, msg, errors):
        Error.__init__(self, "Config errors: %s" % msg)
        self.errors = errors

    def __str__(self):
        return (self.msg +
                ":\n- " +
                "\n- ".join(self.errors) +
                "\n")

    def __repr__(self):
        return repr((self.msg, self.errors))


class SVNError(Error):
    """Error doing SVN actions"""
    def __init__(self, msg):
        Error.__init__(self, "SVN error: %s" % msg)


class GitError(Error):
    """Error doing Git actions"""
    def __init__(self, msg):
        Error.__init__(self, "Git error: %s" % msg)


class GlobNotFoundError(Error):
    """Error raised when no file matching a given glob was found."""
    def __init__(self, globtext):
        msg = "Couldn't find file matching '%s'." % globtext
        Error.__init__(self, msg)


class FileNotFoundInSearchPathError(Error):
    """Error raised when a required file wasn't found in the search path."""
    def __init__(self, fname, searchpath):
        msg = "Couldn't find file named '%s' in search path %s." % (fname, os.pathsep.join(searchpath))
        Error.__init__(self, msg)


class ProgramNotFoundError(Error):
    """Error raised when a required program wasn't found."""
    def __init__(self, program):
        msg = "Couldn't find required program '%s'." % program
        if "/" not in program:
            Error.__init__(self, msg + " $PATH was:\n%s" % os.environ['PATH'])
        else:
            Error.__init__(self, msg)


class OSGBuildError(Error):
    """Error in the build step"""
    def __init__(self, msg, tb=None):
        Error.__init__(self, "Error in build step: " + msg, tb)


class OSGPrebuildError(Error):
    """Error in the prebuild step"""
    def __init__(self, msg, tb=None):
        Error.__init__(self, "Error in pre-build step: " + msg, tb)


class UsageError(Error):
    """Error raised when invalid arguments are passed"""
    def __init__(self, msg, tb=None):
        Error.__init__(self, "Usage error: " + msg + "\n", tb)


class KojiError(Error):
    """Error in the koji task or otherwise dealing with Koji"""
    def __init__(self, msg, tb=None):
        Error.__init__(self, "Koji error: " + msg, tb)


class MockError(Error):
    """Error in the mock task or otherwise dealing with Mock."""
    def __init__(self, msg, tb=None):
        Error.__init__(self, "Mock error: " + msg, tb)


class ClientCertError(Error):
    """Error raised when there is an issue in the client cert."""
    def __init__(self, filename, msg, tb=None):
        Error.__init__(self, "Client cert error: %s (%s)" % (msg, filename), tb)


def type_of_error(err_object):
    if isinstance(err_object, Exception):
        return str(err_object.__class__.__name__)
    else:
        return "Unknown"

