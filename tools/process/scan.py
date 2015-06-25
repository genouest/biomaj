#!/usr/bin/env python

import os,sys
import argparse
import logging.config

from biomaj.utils import Utils

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument('-s', '--scan', dest="directory",help="Directory to scan")
    parser.add_argument('--type', dest="ftype",help="Files type")
    parser.add_argument('--tags', dest="tags", action="append", default=[],
         help="tags, format key:value, can be repeated multiple times")

    args = parser.parse_args()

    if not os.path.exists(args.directory):
        sys.exit(1)

    res = {}
    for (path, dirs, files) in os.walk(args.directory):
        for file in files:
            filename = os.path.join(path, file)
            (file_format, mime) = Utils.detect_format(filename)
            if file_format is not None:
                file_format = file_format.replace('application/','')
            filename = filename.replace(args.directory+'/','')
            if file_format is not None:
                if file_format not in res:
                    res[file_format] = [filename]
                else:
                    res[file_format].append(filename)

    f_type = ''
    if args.ftype:
        f_type = args.ftype
    tags = ''
    if args.tags:
        tags = ','.join(args.tags)
    for fformat in res.keys():
        print '##BIOMAJ#'+fformat+'#'+f_type+'#'+tags+'#'+','.join(res[fformat])


if __name__ == '__main__':
    main()
