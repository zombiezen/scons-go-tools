#!/bin/bash

case "$GOARCH" in
	"amd64" ) ARCHPREFIX="6";;
	"386"   ) ARCHPREFIX="8";;
	"arm"   ) ARCHPREFIX="5";;
	* )
		echo "Unrecognized or unset GOARCH"
		exit 1
	;;
esac

GC="${ARCHPREFIX}g"
LD="${ARCHPREFIX}l"

$GC helper.go || { echo "**Compile failed" ; exit 1; }
$LD -o scons-go-helper helper.$ARCHPREFIX || { echo "**Linking failed" ; exit 1; }

GOBIN=`scons-go-helper -value GOBIN`

cp scons-go-helper "$GOBIN"
