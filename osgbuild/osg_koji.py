#!/usr/bin/env python3
import configparser
import os
import shutil
from string import Template
import sys

from optparse import OptionParser

from osgbuild.constants import (
    DATA_FILE_SEARCH_PATH,
    DEFAULT_AUTHTYPE,
    KOJI_USER_CONFIG_DIR,     # old koji config dir
    OSG_KOJI_USER_CONFIG_DIR) # new koji config dir (created by this script)
from osgbuild.utils import (
    ask,
    ask_yn,
    find_file,
    safe_make_backup,
    safe_makedirs,
    shell_quote)
from osgbuild.error import Error, KojiError
from osgbuild import kojiinter


OLD_CLIENT_CERT_FILE = os.path.join(KOJI_USER_CONFIG_DIR, "client.crt")
GLOBUS_DIR = os.path.expanduser("~/.globus")
KOJI_CONFIG_FILE = "config"
KOJI_CONFIG_TEMPLATE = "osg-koji.conf.in"
SERVERCA_REDHAT = "/etc/pki/tls/certs/ca-bundle.crt"
SERVERCA_UBUNTU = "/etc/ssl/certs"
DEFAULT_CLIENT_CERT_FILE = "client.crt"

PROGRAM_NAME = os.path.basename(sys.argv[0])

RUN_SETUP_MSG = """
Run '%s setup' to set up a koji environment containing the
necessary files in %s.""" % (PROGRAM_NAME, OSG_KOJI_USER_CONFIG_DIR)

EXTRA_HELP = """
%s adds the following commands:
        setup                     Initialize the configuration in %s
                                  See "setup --help" for options.
""" % (PROGRAM_NAME, OSG_KOJI_USER_CONFIG_DIR)

MANUAL_CERT_INSTALL_MSG_TEMPLATE = """
Could not find user cert (%(user_cert)s) and/or key (%(user_key)s).
You must manually copy your certs:

    (cat usercert.pem; echo; cat userkey.pem) > %(new_client_cert_path)s
    dos2unix %(new_client_cert_path)s
    chmod 0600 %(new_client_cert_path)s

where 'usercert.pem' and 'userkey.pem' are your X.509 public and private keys.
"""

KERBEROS_AUTH_BLOCK = """
; configuration for Kerberos/GSSAPI authentication
authtype = kerberos
; specify 'principal' to force using a specific Kerberos principal
"""

SSL_AUTH_BLOCK = """
; configuration for SSL authentication
authtype = ssl
; client certificate
cert = ~/.osg-koji/client.crt
"""

class RunSetupError(Error):
    """Some sort of error where we suggest that the user run `osg-koji setup`"""


def setup_parse_args(args):
    """Parse the arguments given on the command line for the setup command.
    Return the 'options' object, containing the keyword arguments.
    """

    parser = OptionParser("""%prog setup [options]""")

    parser.add_option(
        "-u", "--usercert", "--user-cert", dest="user_cert", metavar="FILE",
        help="Path to user certificate file. Default: %default")

    parser.add_option(
        "-k", "--userkey", "--user-key", dest="user_key", metavar="FILE",
        help="Path to user private key file. Default: %default")

    parser.add_option(
        "--write-client-conf", action="store_true",
        help="Overwrite the client config file. Default: ask")

    parser.add_option(
        "--no-write-client-conf", action="store_false",
        dest="write_client_conf",
        help="Do not overwrite the client config file. Default: ask")

    parser.add_option(
        "--dot-koji-symlink", action="store_true",
        help="Create a ~/.koji -> ~/.osg-koji symlink. Default: ask")

    parser.add_option(
        "--no-dot-koji-symlink", action="store_false",
        dest="dot_koji_symlink",
        help="Do not create a ~/.koji -> ~/.osg-koji symlink. Default: ask")

    parser.add_option(
        "--authtype",
        choices=["kerberos", "ssl", "ask"],
        default="ask",
        dest="authtype",
        help="The authentication method to use. Default: %default"
    )

    parser.add_option(
        "--principal", dest="principal",
        help="Set the principal to use for Kerberos auth; will use the default if not specified or 'default'"
    )

    parser.set_defaults(
        user_cert=os.path.join(GLOBUS_DIR, "usercert.pem"),
        user_key=os.path.join(GLOBUS_DIR, "userkey.pem"),
        write_client_conf=None,
        dot_koji_symlink=None,
        principal=None,
    )

    options = parser.parse_args(args)[0]

    return options


def make_config_text(authtype, principal):
    template_path = find_file(KOJI_CONFIG_TEMPLATE, DATA_FILE_SEARCH_PATH)
    if os.path.exists(SERVERCA_REDHAT):
        serverca = SERVERCA_REDHAT
    elif os.path.exists(SERVERCA_UBUNTU):
        serverca = SERVERCA_UBUNTU
    else:
        raise Error("System CA certificates bundle not found (looked in %s and %s)" % (SERVERCA_UBUNTU, SERVERCA_REDHAT))

    if authtype == "kerberos":
        print("Configuring the Koji client for Kerberos auth.")
        auth_block = KERBEROS_AUTH_BLOCK

        if principal is None:
            # Principal not specified; ask interactively
            print("")
            print("Please enter the Kerberos principal you want to use, or just press Enter")
            print("to use the default principal.")
            print("")
            try:
                principal = input("> ")
            except EOFError:
                principal = ""

        if str(principal).lower() not in ["", "none", "default"]:
            assert isinstance(principal, str)
            if "@" not in principal:
                raise Error(f"Invalid principal {principal}: must have an '@' sign")
            # Let's be nice and fix the domain of the principal
            username, atsign, domain = principal.partition("@")
            principal_ = username + atsign + domain.upper()
            auth_block += f"principal = {principal_}\n"
        else:
            auth_block += ";principal =\n"
    elif authtype == "ssl":
        print("Configuring the Koji client for SSL auth.")
        auth_block = SSL_AUTH_BLOCK
    else:
        raise ValueError(f"Invalid authtype {authtype}")

    with open(template_path, "r") as template_fh:
        config_text = Template(template_fh.read()).safe_substitute({
            "SERVERCA": serverca,
            "AUTH_BLOCK": auth_block,
        })
        return config_text


def setup_koji_config_file(write_client_conf, authtype, principal):
    """Create the koji config file (if needed)."""
    new_koji_config_path = os.path.join(OSG_KOJI_USER_CONFIG_DIR,
                                        KOJI_CONFIG_FILE)
    if os.path.exists(new_koji_config_path):
        if write_client_conf is False:
            return
        if write_client_conf is None and not ask_yn("""\
Koji configuration file '%s' already exists.
Overwrite it with a new config file? Unless you have made changes to the file,
you should say yes.
""" % new_koji_config_path):
            return
        safe_make_backup(new_koji_config_path, simple_suffix=True)

    if authtype == "ask":
        if DEFAULT_AUTHTYPE == "kerberos":
            choices = ("K", "s")  # capitalize the default for emphasis
        else:
            assert DEFAULT_AUTHTYPE == "ssl"
            choices = ("S", "k")
        answer = ask(f"Use Kerberos (k) or SSL (s)? Default: {DEFAULT_AUTHTYPE}",
                     choices, choices[0]).lower()[0]
        if answer == "k":
            authtype = "kerberos"
        else:
            assert answer == "s"
            authtype = "ssl"
    config_text = make_config_text(authtype, principal)
    with open(new_koji_config_path, "w") as config_fh:
        config_fh.write(config_text)


def with_safe_umask(function_to_wrap):
    """decorator to set the umask to 0077 and restore it when we're done"""
    def wrapped_function(*args, **kwargs):  # pylint: disable=missing-docstring
        old_umask = os.umask(0o077)
        try:
            return function_to_wrap(*args, **kwargs)
        finally:
            os.umask(old_umask)
    return wrapped_function


@with_safe_umask
def copy_old_client_cert(new_client_cert_path):
    """Copy an old client cert to the new destination"""
    safe_make_backup(new_client_cert_path)
    try:
        shutil.copy(OLD_CLIENT_CERT_FILE, new_client_cert_path)
    except EnvironmentError as err:
        raise Error("Unable to copy client cert: %s" % err)


@with_safe_umask
def create_client_cert_from_cert_and_key(new_client_cert_path, user_cert, user_key):  # pylint: disable=invalid-name
    """Combine `user_cert` and `user_key` to create a new cert file at
    `new_client_cert_path`.
    """
    safe_make_backup(new_client_cert_path)
    # Concatenate the cert and key; make sure there is a newline between them
    os.system("(cat %s; echo; cat %s) > %s" % (shell_quote(user_cert),
                                               shell_quote(user_key),
                                               shell_quote(new_client_cert_path)))
    # Convert DOS line endings; use sed because dos2unix might not be installed
    os.system("sed -i -e 's/\015$//g' %s" % shell_quote(new_client_cert_path))


def setup_koji_client_cert(user_cert, user_key):
    """Create or copy the client cert file (if needed)."""
    new_client_cert_path = os.path.join(OSG_KOJI_USER_CONFIG_DIR, DEFAULT_CLIENT_CERT_FILE)

    if (os.path.lexists(new_client_cert_path) and
            not ask_yn("""
Client certificate file '%s' already exists.
Do you want to recreate it now? Enter yes if you have trouble logging in via
the command-line tools or if you got a new certificate.
""" % new_client_cert_path)):

        print("Not writing client cert file " + new_client_cert_path)
        return

    if (os.path.exists(KOJI_USER_CONFIG_DIR) and
            (os.path.isdir(OSG_KOJI_USER_CONFIG_DIR) and
             not os.path.samefile(KOJI_USER_CONFIG_DIR,
                                  OSG_KOJI_USER_CONFIG_DIR)) and
            os.path.isfile(OLD_CLIENT_CERT_FILE)):

        if ask_yn("""
You already have a client certificate at '%s'.
Reuse that file?
""" % OLD_CLIENT_CERT_FILE):
            copy_old_client_cert(new_client_cert_path)
            return

    if os.path.isfile(user_cert) and os.path.isfile(user_key):
        create_client_cert_from_cert_and_key(new_client_cert_path,
                                             user_cert, user_key)
        print("Created %s from %s and %s" % (new_client_cert_path,
                                             user_cert, user_key))
        return
    # if we get here, nothing worked
    print(MANUAL_CERT_INSTALL_MSG_TEMPLATE % locals())
    sys.exit(1)


def run_setup(options):
    """Set up the koji config dir"""
    safe_makedirs(OSG_KOJI_USER_CONFIG_DIR)
    setup_koji_config_file(options.write_client_conf, options.authtype, options.principal)
    if options.authtype == "ssl":
        user_cert, user_key = options.user_cert, options.user_key
        setup_koji_client_cert(user_cert, user_key)

    if not os.path.exists(KOJI_USER_CONFIG_DIR):
        if (options.dot_koji_symlink or
            (options.dot_koji_symlink is None and
             ask_yn("Create symlink %s -> %s ?" % (KOJI_USER_CONFIG_DIR,
                                                   OSG_KOJI_USER_CONFIG_DIR))
            )):

            os.symlink(OSG_KOJI_USER_CONFIG_DIR, KOJI_USER_CONFIG_DIR)


def verify_koji_config(config_file):
    """Ensure the koji config file exists and the files it references also exist.
    Returns the koji config."""
    try:
        koji_config = kojiinter.get_koji_config(config_file)
    except KojiError as err:
        raise RunSetupError("%s\nKoji config file not found at %s, "
                            "or has invalid contents." % (err, config_file))
    try:
        authtype = koji_config.get("koji", "authtype")
    except configparser.NoOptionError:
        authtype = DEFAULT_AUTHTYPE
    if authtype == "ssl":
        try:
            client_cert_file = os.path.expanduser(koji_config.get("koji", "cert"))
        except configparser.NoOptionError:
            raise RunSetupError("SSL auth requested but client certificate ('cert') not provided in Koji config.")

        config_dir = os.path.dirname(config_file)
        fullpath = os.path.join(config_dir, client_cert_file)
        if not os.path.lexists(fullpath):
            raise RunSetupError("Client cert file not found at %s" % fullpath)
        elif not os.path.exists(fullpath):
            # lexists() is True for a broken symlink, exists() is False
            target = os.readlink(fullpath)
            print("%s -> %s is a broken symlink.\n"
                  "Note: grid certificates no longer function; if you were using them before,\n"
                  "please re-run osg-koji setup."
                  % (fullpath, target),
                  file=sys.stderr)
    return koji_config


def run_koji(args=None, use_exec=False):
    """Run koji with the given list of args.  Replaces current process if use_exec is true.
    Returns return code of os.system() otherwise.
    Catches missing koji binary.
    """
    args = args or []
    try:
        if use_exec:
            os.execlp("koji", "koji", *args)
        else:
            cmd = "koji"
            if args:
                cmd += " " + " ".join(shell_quote(x) for x in args)
            return os.system(cmd)
    except OSError as err:
        if err.errno == 2:  # file not found
            raise Error("Couldn't find `koji` binary.  Is koji installed and in your PATH?")
        raise


def main(argv=None, use_exec=True):
    """Main function"""
    if argv is None:
        argv = sys.argv

    koji_config_path = os.path.join(OSG_KOJI_USER_CONFIG_DIR, KOJI_CONFIG_FILE)
    try:
        if len(argv) > 1:
            if argv[1] == "setup":
                options = setup_parse_args(argv[2:])
                run_setup(options)
                koji_config = verify_koji_config(koji_config_path)
                try:
                    authtype = koji_config.get("koji", "authtype")
                except configparser.NoOptionError:
                    authtype = DEFAULT_AUTHTYPE
                print("""
Setup is done. You may verify that you can log in via the command-line
tools by running:

    %s hello

""" % (PROGRAM_NAME))
                if authtype == "kerberos":
                    print("""\
Koji has been configured to use Kerberos auth.
You may need to run `kinit` before running the above command.
""")
            elif argv[1] == "help":
                run_koji(args=argv[1:])
                print(EXTRA_HELP)
            else:
                if not os.path.exists(koji_config_path):
                    raise RunSetupError(f"No Koji config found at {koji_config_path}")
                koji_config = verify_koji_config(koji_config_path)
                try:
                    authtype = koji_config.get("koji", "authtype")
                except configparser.NoOptionError:
                    authtype = DEFAULT_AUTHTYPE
                args = ["--config=" + koji_config_path,
                        "--authtype=%s" % authtype] + argv[1:]
                return run_koji(args=args, use_exec=use_exec)
        else:
            run_koji()
            print(EXTRA_HELP)
    except SystemExit as err:
        return err.code
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 3
    except RunSetupError as err:
        print(err, file=sys.stderr)
        print(RUN_SETUP_MSG, file=sys.stderr)
        return 1
    except Error as err:
        print(err, file=sys.stderr)
        return 1
    except Exception as err:
        print("Unhandled exception: " + str(err), file=sys.stderr)
        raise

    return 0


if __name__ == "__main__":
    sys.exit(main())
