#!/usr/bin/env python
#
#   go.py
#   SCons Go Tools
#   
#   Copyright (c) 2010, Ross Light.
#   All rights reserved.
#
#   Redistribution and use in source and binary forms, with or without
#   modification, are permitted provided that the following conditions are met:
#
#       Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#
#       Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#
#       Neither the name of the SCons Go Tools nor the names of its contributors
#       may be used to endorse or promote products derived from this software
#       without specific prior written permission.
#
#   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#   AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#   IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
#   ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
#   LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
#   CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
#   SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
#   INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
#   CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
#   ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
#   POSSIBILITY OF SUCH DAMAGE.
#

import os
import posixpath
import subprocess

from SCons.Action import Action
from SCons.Scanner import Scanner
from SCons.Builder import Builder

def _subdict(d, keys):
    result = {}
    for key in keys:
        result[key] = d[key]
    return result

# COMPILER

def _go_scan_func(node, env, paths):
    package_paths = env['GOLIBPATH'] + [env['GOPKGROOT']]
    source_imports = _run_helper(env, ['-mode=imports', node.rstr()]).splitlines()
    result = []
    for package_name in source_imports:
        if package_name.startswith("./"):
            result.append(env.File(package_name))
            continue
        # Search for import
        package_dir, package_name = posixpath.split(package_name)
        subpaths = [posixpath.join(p, package_dir) for p in package_paths]
        # Check for a static library
        package = env.FindFile(
            package_name + os.path.extsep + 'a',
            subpaths,
        )
        if package is not None:
            result.append(package)
            continue
        # Check for a build result
        package = env.FindFile(
            package_name + os.path.extsep + env['GOARCHNAME'],
            subpaths,
        )
        if package is not None:
            result.append(package)
            continue
    return result

go_scanner = Scanner(function=_go_scan_func, skeys=['.go'])

def gc(source, target, env, for_signature):
    flags = []
    for include in env.get('GOLIBPATH', []):
        flags += ['-I', include]
    sources = [str(s) for s in source]
    target = str(target[0])
    args = [env['GOCOMPILER'], '-o', target] + flags + sources
    return Action([args])

def _ld_scan_func(node, env, path):
    obj_suffix = os.path.extsep + env['GOARCHNAME']
    result = []
    for child in node.children():
        if str(child).endswith(obj_suffix):
            result.append(child)
    return result

def ld(source, target, env, for_signature):
    flags = []
    for libdir in env.get('GOLIBPATH', []):
        flags += ['-L', libdir]
    sources = [str(s) for s in source]
    target = str(target[0])
    args = [env['GOLINKER'], '-o', target] + flags + sources
    return Action([args])

def _go_object_suffix(env, sources):
    return os.path.extsep + env['GOARCHNAME']

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
    single_source=True,
    source_scanner=Scanner(function=_ld_scan_func, recursive=True),
)

# HELPER TOOL

def _get_PATH(env):
    if isinstance(env['ENV']['PATH'], (list, tuple)):
        return list(env['ENV']['PATH'])
    else:
        return env['ENV']['PATH'].split(os.path.pathsep)

def _get_gobin():
    try:
        return os.environ['GOBIN']
    except KeyError:
        home = os.environ.get('HOME')
        if home:
            return os.path.join(home, 'bin')
        else:
            return None

def _parse_config(data):
    result = {}
    for line in data.splitlines():
        name, value = line.split('=', 1)
        result[name] = value
    return result

def _setup_helper(env):
    # See if we can find a shared helper
    helper_node = _find_helper(env)
    if helper_node is None:
        # None to be found.  Does the build script have a desirable place?
        if 'GOHELPER' in env:
            helper_node = env.File(env['GOHELPER'])
        else:
            # Stick it in the root project directory.
            helper_node = env.Dir(env.GetLaunchDir()).File('scons-go-helper')
    # If the helper doesn't exist, build it.
    if not helper_node.exists():
        helper_node.prepare()
        _install_helper(helper_node.abspath)
    env['GOHELPER'] = helper_node.abspath

def _install_helper(location):
    tool_dir = os.path.dirname(__file__)
    retcode = subprocess.call(
        [os.path.join(tool_dir, 'build-helper.sh'), location],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,
        cwd=tool_dir,
    )
    if retcode != 0:
        raise RuntimeError("Could not install Go helper")

def _run_helper(env, args):
    proc = subprocess.Popen(
        [env['GOHELPER']] + list(args),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env['ENV'],
    )
    stdout, stderr = proc.communicate()
    return stdout

def _find_helper(env):
    paths = _get_PATH(env)
    gobin = _get_gobin()
    if gobin:
        paths.insert(0, gobin)
    return env.FindFile('scons-go-helper', paths)

# API

def generate(env):
    if 'HOME' not in env['ENV']:
        env['ENV']['HOME'] = os.environ['HOME']
    # Ensure that we have the helper
    _setup_helper(env)
    # Now set up the environment
    config = _parse_config(_run_helper(env, []))
    env.Append(ENV=_subdict(config, ['GOROOT', 'GOOS', 'GOARCH', 'GOBIN']))
    env['GOCOMPILER'] = config['gc']
    env['GOLINKER'] = config['ld']
    env['GOLIBPATH'] = []
    env['GOARCHNAME'] = config['archname']
    env['GOPKGROOT'] = config['pkgroot']
    env.Append(
        BUILDERS={
            'Go': go_compiler,
            'GoProgram': go_linker,
        },
        SCANNERS=[go_scanner],
    )

def exists(env):
    if _find_helper(env) is not None:
        return True
    else:
        # Check to see whether we have the build script handy
        build_script = os.path.join(os.path.dirname(__file__), 'build-helper.sh')
        if not os.path.exists(build_script):
            return False
        # The required environment variables must be present
        for evar in ('GOROOT', 'GOOS', 'GOARCH'):
            if evar not in os.environ:
                return False
        # Check for the compiler and linker
        gobin = _get_gobin()
        if not gobin:
            return False
        archs = {'amd64': '6', '386': '8', 'arm': '5'}
        gc_path = os.path.join(gobin, archs[os.environ['GOARCH']] + 'g')
        ld_path = os.path.join(gobin, archs[os.environ['GOARCH']] + 'l')
        return os.path.exists(gc_path) and os.path.exists(ld_path)
