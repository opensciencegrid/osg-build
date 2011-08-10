import os
import re
import subprocess


class CalledProcessError(Exception):
    pass


def checked_call(*args, **kwargs):
    """A wrapper around subprocess.call() that raises CalledProcessError on
    a nonzero return code. Similar to subprocess.check_call() in 2.7+, but
    prints the command to run and the result unless 'quiet=True' is passed.
    Also, if the first argument is a string and shell=False isn't passed,
    then shell=True is passed to subprocess.call().

    """
    err = unchecked_call(*args, **kwargs)
    if err:
        raise CalledProcessError(
            "Error in checked_call(%s, %s): subprocess returned %s" % \
            (str(args), str(kwargs), str(err)))


def unchecked_call(*args, **kwargs):
    """A wrapper around subprocess.call() with the same semantics as checked_call: 
    Prints the command to run and the result unless 'quiet=True' is passed.
    Also, if the first argument is a string and shell=False isn't passed,
    then shell=True is passed to subprocess.call().

    """
    quiet = kwargs.pop('quiet', False)
    if not quiet:
        if type(args[0]) == type(''):
            cmd = args[0]
        elif type(args[0]) == type([]) or type(args[0]) == type(()):
            cmd = "'" + "' '".join(args[0]) + "'"
        print "Running " + cmd

    if type(args[0]) == type('') and 'shell' not in kwargs:
        kwargs['shell'] = True

    err = subprocess.call(*args, **kwargs)
    if not quiet:
        print "Subprocess returned " + str(err)
    return err


def backtick(*args, **kwargs):
    if type(args[0]) == type('') and 'shell' not in kwargs:
        kwargs['shell'] = True

    kwargs['stdout'] = subprocess.PIPE
    proc = subprocess.Popen(*args, **kwargs)

    return proc.communicate()[0].strip()


def get_rpmrc():
    """A naive way of parsing the output of rpm --showrc to get the variables"""

    showrc = subprocess.Popen(['rpm', '--showrc'], stdout=subprocess.PIPE).communicate()[0]
    # The variables are separated from the rest of the output by '=' x 24
    showrc_trimmed = re.sub("\A.*(?ms)={24}(?P<meat>.*)={24}.*\Z", "\g<meat>", showrc).strip()
    vars_array = re.split(r'''(?m)^-1[0-9]: ''', showrc_trimmed)
    vars_dict = dict([entry.rstrip().split("\t", 1) for entry in vars_array if entry != ''])

    return vars_dict


def slurp(filename):
    try:
        fh = open(filename, 'r')
        contents = fh.read()
    finally:
        fh.close()
    return contents


def unslurp(filename, contents):
    try:
        fh = open(filename, 'w')
        fh.write(contents)
    finally:
        fh.close()


def find_file(filename, paths):
    """Go through each directory in paths and look for filename in it. Return
    the first match.

    """
    matches = find_files(filename, paths)
    if matches:
        return matches[0]
    else:
        return None


def find_files(filename, paths):
    """Go through each directory in paths and look for filename in it. Return
    all matches.

    """
    matches = []
    for p in paths:
        j = os.path.join(p, filename)
        if os.path.exists(j):
            matches += [j]
    return matches
            

def _spec_replvar(macro_vars, match):
    '''Helper function for spec_expand_macros'''

    if match.group(2) in macro_vars:
        return macro_vars[match.group(2)]
    else:
        if match.group(1) == '?':
            return ''
        else:
            return match.group(0)


def spec_expand_macros(macro_vars, string):
    '''Expand the macro variables in macro_vars in string'''

    done = False
    macro_vars['%']='%'
    estring = string
    while not done:
        old_estring = estring
        (estring, nsubs) = re.subn(r"""(?xms)
            (?<!%)[%] # leading % (but not 2)
            [{]?      # maybe {
            ([?]?)    # maybe ? -- substitution behaves differently if present so capture it
            (\w+)     # macro name
            [}]?      # maybe }
            """, lambda match: _spec_replvar(macro_vars, match), estring)
        if nsubs == 0 or estring == old_estring:
            done = True
    return estring
    

def spec_parse(spec_contents):
    '''A simple parser for spec files. Handles simple macros (ones
    without arguments or macro directives like %expand, %define, etc.)'''

    # Some of this comes from spectool from Red Hat's rpmdevtools package
    rpm_sections = [
        "package",
        "description",
        "prep",
        "build",
        "install",
        "clean",
        "pre",
        "preun",
        "post",
        "postun",
        "triggerin",
        "triggerun",
        "triggerpostun",
        "files",
        "changelog", ]
    important_metadata_keys = [
        "name",
        "version",
        "release",
        "epoch", ]
    #predefined_vars = get_rpmrc()
    # Split on newlines except when they come right after a continuation
    # character (\) followed by optional non-newline whitespace:
    spec_split = re.split(r'''(?ms)(?<!\\)[ \t]*\n''', spec_contents)
    expanded_spec = ''
    #macro_vars = predefined_vars.copy()
    macro_vars = {}
    in_preamble = True
    for line in spec_split:
        sline = line.strip()

        if in_preamble:
            section_start_match = re.match(r"(?ms)%(\w+)", line)
            metadata_match = re.match(r"(?ms)(\w+)\s*:\s*(.+)", line)
            if section_start_match:
                word = section_start_match.group(1).strip().lower()
                if word in rpm_sections:
                    in_preamble = False
            elif metadata_match:
                metadata_key = metadata_match.group(1).strip().lower()
                if metadata_key in important_metadata_keys or \
                        metadata_key.startswith("source") or \
                        metadata_key.startswith("patch"):
                    metadata_value = metadata_match.group(2).strip()
                    exp_value = spec_expand_macros(macro_vars, metadata_value)
                    # Special cases: 'source' => 'source0', 'patch' => 'patch0'
                    if metadata_key == 'source':
                        macro_vars['source0'] = exp_value
                    elif metadata_key == 'patch':
                        macro_vars['patch0'] = exp_value
                    else:
                        macro_vars[metadata_key] = exp_value
                    
        defmatch = re.match(r"""(?xms)
            [%](?:define|global)  # %define or %global
            \s+
            (\w+)                 # the macro name
            (?:
                [(][^)]*[)]       # arguments
            )?                    # (maybe)
            \s+
            (.+)                  # macro definition
            """, sline)
        if defmatch:
            macro_name = defmatch.group(1)
            macro_defn = defmatch.group(2)
            exp_macro_defn = spec_expand_macros(macro_vars, macro_defn)        
            macro_vars[macro_name] = exp_macro_defn
        else:
            sline = spec_expand_macros(macro_vars, sline)
            expanded_spec += sline + "\n"

    return (macro_vars, expanded_spec)


def super_unpack(*compressed_files):
    '''Extracts compressed files, calling the appropriate expansion
    program based on the file extension.'''

    handlers = [
        ('.tar.bz2',  'tar xjf %s'),
        ('.tar.gz',   'tar xzf %s'),
        ('.bz2',      'bunzip2 %s'),
        ('.rar',      'unrar x %s'),
        ('.gz',       'gunzip %s'),
        ('.tar',      'tar xf %s'),
        ('.tbz2',     'tar xjf %s'),
        ('.tgz',      'tar xzf %s'),
        ('.zip',      'unzip %s'),
        ('.Z',        'uncompress %s'),
        ('.7z',       '7z x %s'),
        ('.tar.xz',   'xz -d %s -c | tar xf -'),
        ('.xz',       'xz -d %s'),
        ('.rpm',      'rpm2cpio %s | cpio -id'),
    ]
    for cf in compressed_files:
        for (ext, cmd) in handlers:
            if cf.endswith(ext):
                subprocess.call(cmd % re.escape(cf), shell=True)
                break


def safe_makedirs(directory, mode=0777):
    if not os.path.isdir(directory):
        os.makedirs(directory, mode)
        
