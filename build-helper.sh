#!/bin/bash
#
#	build-helper.sh
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

# Determine architecture
case "$GOARCH" in
	"amd64" ) ARCHPREFIX="6";;
	"386"   ) ARCHPREFIX="8";;
	"arm"   ) ARCHPREFIX="5";;
	* )
		echo "Unrecognized or unset GOARCH" 1>&2
		exit 1
	;;
esac

# Determine tool paths
if [ "$GOBIN" = "" ]
    then export GOBIN="${HOME}/bin"
fi

GC="${GOBIN}/${ARCHPREFIX}g"
LD="${GOBIN}/${ARCHPREFIX}l"

if [[ -e "$GC" && -e "$LD" ]]
then
    # Build it!
    TEMPDIR="`mktemp -d -t scons-go-helper.XXXXXX`" || { echo "**Couldn't create temporary directory" 1>&2 ; exit 1 ; }
    $GC -o "${TEMPDIR}/helper.$ARCHPREFIX" helper.go || { echo "**Compile failed" 1>&2 ; exit 1 ; }
    $LD -o "${TEMPDIR}/scons-go-helper" "${TEMPDIR}/helper.$ARCHPREFIX" || { echo "**Linking failed" 1>&2 ; exit 1 ; }
else
    echo "**Toolset not found" 1>&2
    exit 1
fi

# Copy helper to designated directory (defaults to GOBIN)
if [ $# -eq 0 ]
then
    cp "${TEMPDIR}/scons-go-helper" "$GOBIN/scons-go-helper"
else
    cp "${TEMPDIR}/scons-go-helper" "$1"
fi
