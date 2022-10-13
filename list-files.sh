#!/bin/bash
for i in *.pdf; do echo "${i%.*}: $(pdfinfo $i | grep Title | awk '{ print substr( $0, 18 ) }')"; done