#!/usr/bin/env python

from datetime import datetime
import os
import re

from SCons.Action import Action
from SCons.Scanner import Scanner
from SCons.Builder import Builder

def _subdict(d, keys):
    result = {}
    for key in keys:
        result[key] = d[key]
    return result

# COMPILER

archs = {'amd64': '6', '386': '8', 'arm': '5'}

def _get_tool_name(environ, suffix):
    host_arch = environ.get('GOARCH')
    if host_arch is not None:
        return archs[host_arch] + suffix
    else:
        return None

_import_spec = re.compile(r'(?:(\.|[_\w]+)\s+)?(\"[^\"]*\")')
_import_pat = re.compile(r'(?:^|[\n\r])[ \t]*import(\s*\([^\)]*\)|\s+.*)')
def _get_imports(env, go_source):
    for import_struct in _import_pat.finditer(go_source):
        spec_list = []
        # Split specifications
        # (This is a little bit trickier because of the whole automatic
        # semicolon rules, so we split it by newlines, too.
        spec_lines = import_struct.group(1).splitlines()
        for line in spec_lines:
            spec_list += line.split(';')
        # Now parse the import specifications
        for spec in spec_list:
            spec = spec.strip()
            if spec.startswith('('):
                spec = spec[1:-1].strip()
            m = _import_spec.match(spec)
            if m:
                name = eval(m.group(2))
                if name.startswith('./'):
                    package = name[2:] + "." + archs[env['ENV']['GOARCH']]
                    build_dir = env.get('GOBUILDDIR')
                    if build_dir:
                        package = build_dir + '/' + package
                    yield package

def _go_scan_func(node, env, path):
    result = []
    for package in _get_imports(env, node.get_contents()):
        result.append(env.File(package))
    return result

go_scanner = Scanner(function=_go_scan_func, skeys=['.go'])

def gc(source, target, env, for_signature):
    flags = []
    for include in env.get('GOINCLUDE', []):
        flags += ['-I', include]
    build_dir = env.get('GOBUILDDIR')
    if build_dir:
        sources = [s.get_abspath() for s in source]
        target = target[0].get_abspath()
    else:
        sources = [str(s) for s in source]
        target = str(target[0])
    args = [env['GOCOMPILER'], '-o', target] + flags + sources
    return Action([args], chdir=build_dir)

def _ld_scan_func(node, env, path):
    obj_suffix = '.' + archs[env['ENV']['GOARCH']]
    result = []
    for child in node.children():
        if str(child).endswith(obj_suffix):
            result.append(child)
    return result

def ld(source, target, env, for_signature):
    sources = [str(s) for s in source]
    target = str(target[0])
    args = [env['GOLINKER'], '-o', target] + sources
    return Action([args])

def _go_object_suffix(env, sources):
    return "." + archs[env['ENV']['GOARCH']]

def _go_program_prefix(env, sources):
    return env['PROGPREFIX']

def _go_program_suffix(env, sources):
    return env['PROGSUFFIX']

go_compiler = Builder(
    generator=gc,
    suffix=_go_object_suffix,
    ensure_suffix=True,
    src_suffix='.go',
)
go_linker = Builder(
    generator=ld,
    prefix=_go_program_prefix,
    suffix=_go_program_suffix,
    src_builder=go_compiler,
    source_scanner=Scanner(function=_ld_scan_func, recursive=True),
)

# TESTING

_package_pattern = re.compile(r"^package\s+([_a-zA-Z0-9]+)")
def get_package_name(path, root=None):
    """Returns (package_name, import_path)"""
    # Determine path-based package
    if not root:
        root = os.path.curdir
    abs_root = os.path.abspath(root)
    if not abs_root.endswith(os.path.sep):
        abs_root += os.path.sep
    abs_path = os.path.abspath(path)
    if abs_path.startswith(abs_root):
        build_path = abs_path[len(abs_root):]
    else:
        build_path = path
    root_package = os.path.dirname(build_path)
    # Analyze source for package name
    source_file = open(path, 'r')
    try:
        # Get package name from source file
        for line in source_file:
            m = _package_pattern.match(line)
            if m:
                package_name = m.group(1)
                break
        else:
            raise ValueError("Source file has no package directive")
        # Determine package path
        if root_package.split(os.path.sep)[-1] == package_name:
            import_path = root_package
        else:
            import_path = root_package + os.path.sep + package_name
        import_path = import_path.replace(os.path.sep, '/')
        return package_name, import_path
    finally:
        source_file.close()

_func_pattern = re.compile(r"^func\s+([_a-zA-Z0-9]+)")
_test_name_pattern = re.compile(r"Test[A-Z].*")
def get_test_names(f):
    for line in f:
        m = _func_pattern.match(line)
        if m:
            func_name = m.group(1)
            if _test_name_pattern.match(func_name):
                yield func_name

def write_test_file(f, import_list, test_list):
    print >> f, "// Generated by Ross's SCons gotest on %s" % \
        (datetime.now().isoformat())
    print >> f, "// DO NOT MODIFY!"
    print >> f, """\
package main
import
(
    "testing";"""
    for i in import_list:
        print >> f, '    "./%s";' % (i)
    print >> f, ")"
    
    print >> f, """\
var tests = []testing.Test
{"""
    for test in test_list:
        print >> f, '    testing.Test{"%s", %s},' % (test, test)
    print >> f, '}'
    
    print >> f, """
func main()
{
    testing.Main(tests);
}"""

def gotest(source, target, env):
    # Build test information
    import_list = []
    test_list = []
    for node in source:
        package_name, import_path = get_package_name(
            str(node), env['GOBUILDDIR'])
        import_list.append(import_path)
        f = open(str(node))
        try:
            test_names = get_test_names(f)
            test_list += [package_name + '.' + n for n in test_names]
        finally:
            f.close()
    # Write it out
    target = open(str(target[0]), 'w')
    try:
        write_test_file(target, import_list, test_list)
    finally:
        target.close()

go_tester = Builder(action=gotest,
                    suffix='.go',
                    src_suffix='.go',)

# API

def generate(env):
    # Get Go environment variables
    environ = _subdict(os.environ, ['GOROOT', 'GOOS', 'GOARCH', 'GOBIN'])
    environ.setdefault('GOBIN', os.path.join(os.environ['HOME'], 'bin'))
    # Set default compiler and linker
    env['GOCOMPILER'] = os.path.join(environ['GOBIN'],
                                     _get_tool_name(environ, 'g'))
    env['GOLINKER'] = os.path.join(environ['GOBIN'],
                                   _get_tool_name(environ, 'l'))
    # Inject necessary environment
    env.Append(ENV=environ)
    env.Append(BUILDERS={'Go': go_compiler, 'GoProgram': go_linker,
                         'GoTests': go_tester})
    env.Append(SCANNERS=[go_scanner])

def exists(env):
    if 'GOROOT' not in os.environ:
        return False
    gobin = os.environ.get('GOBIN')
    if gobin is not None:
        compiler = _get_tool_name(os.environ, 'g')
        linker = _get_tool_name(os.environ, 'l')
        if compiler and linker:
            return os.path.exists(os.path.join(gobin, compiler)) and \
                   os.path.exists(os.path.join(gobin, linker))
        else:
            return False
    else:
        return False
