#!/bin/sh

if [ $# -eq 0 ] ; then
	for I in $(ls static/js/*.js); do
		echo js-beautify -tnr --brace-style=end-expand "$I"
		js-beautify -tnr --brace-style=end-expand "$I"
	done
else
	js-beautify -tnr --brace-style=end-expand $*
fi

