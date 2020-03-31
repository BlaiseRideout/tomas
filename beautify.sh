#!/bin/sh

if [ $# -eq 0 ] ; then
	for I in $(ls static/js/*.js); do
		if [[ `echo "$I" | grep '\.min\.js$'` == "" ]] ; then
			echo js-beautify -tnr --brace-style=end-expand "$I"
			js-beautify -tnr --brace-style=end-expand "$I"
		fi
	done
else
	js-beautify -tnr --brace-style=end-expand $*
fi

