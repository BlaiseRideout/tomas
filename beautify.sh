#!/bin/bash

if [ $# -eq 0 ] ; then
    changed=()
    for I in $(ls static/js/*.js); do
	if [[ `echo "$I" | grep '\.min\.js$'` == "" ]] ; then
	    echo js-beautify -tnr --brace-style=end-expand "$I"
	    result=`js-beautify -tnr --brace-style=end-expand "$I"`
	    echo $result
	    if [[ `echo "$result" | sed -n '/unchanged$/p'` == '' ]] ; then
		changed=($changed $I)
	    fi
	fi
    done
    if [ ${#changed[*]} -eq 0 ] ; then
	echo 'No files changed'
    else
	echo -n ${#changed[*]} File
	if [ ${#changed[*]} -gt 1 ] ; then echo -n s ; fi
	echo ' changed:'
	for file in ${changed[*]} ; do
	    echo " " $file
	done
    fi
else
    js-beautify -tnr --brace-style=end-expand $*
fi

