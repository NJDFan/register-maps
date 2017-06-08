"""Main executable for registermap."""

import argparse
import sys
from itertools import chain

from . import xml_parser, import_object

def main(argv = None):
    if argv is None:
        argv = sys.argv[1:]
        
    parser = argparse.ArgumentParser(description='Translate register map XML files into other formats')
    parser.add_argument('format')
    parser.add_argument('srcdir')
    parser.add_argument('--output', default='-')
    
    args = parser.parse_args(argv)
    
    # Load our output formatter
    ofparts = args.format.rsplit('.', maxsplit=1)
    if len(ofparts) == 2:
        package, kls = ofparts
    else:
        package, kls = '.', ofparts[0]
    formatkls = import_object(package, kls)
    
    # Start by reading in the source files.
    parser = xml_parser.XmlParser()
    parser.processDirectory(args.srcdir)
    
    # And do the outputs.
    for v in chain(parser.components.values(), parser.memorymaps.values()):
        f = formatkls(output=args.output)
        f.execute(v)
        
if __name__ == '__main__':
    main()
