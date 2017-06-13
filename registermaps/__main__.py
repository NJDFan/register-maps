"""Main executable for registermap."""

import argparse
import sys
import traceback
import os.path
import importlib
from itertools import chain
from . import __version__, ProgramGlobals

from . import xml_parser, import_object

def main(argv = None):
    if argv is None:
        argv = sys.argv[1:]
        
    parser = argparse.ArgumentParser(description='Translate register map XML files into other formats')
    parser.add_argument('format')
    parser.add_argument('srcdir')
    parser.add_argument('--output', help='Output directory for files.', default=None)
    parser.add_argument('--verbose', help='Name files as they are created.', action="store_true")
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('--debug', nargs='?', help='Run with debugger.  pdb by default, ipdb works as well, anything with a post_mortem() function should.', const='pdb')
    
    args = parser.parse_args(argv)
    
    # Load our output formatter
    ofparts = args.format.rsplit('.', maxsplit=1)
    if len(ofparts) == 2:
        package, kls = ofparts
    else:
        package, kls = '.', ofparts[0]
    formatkls = import_object(package, kls)
    
    # Enable debugging if requested
    if args.debug:
        post_mortem = importlib.import_module(args.debug).post_mortem
        def info(type, value, tb):
            traceback.print_exception(type, value, tb)
            post_mortem(tb)
        sys.excepthook = info
        
    # And verbosity
    ProgramGlobals['verbose'] = args.verbose
        
    # Start by reading in the source files.
    parser = xml_parser.XmlParser()
    parser.processDirectory(args.srcdir)
    
    # And do the outputs.
    if args.output is not None:
        formatkls.preparedir(args.output)
        
    for v in chain(parser.components.values(), parser.memorymaps.values()):
        f = formatkls(output='-', directory=args.output)
        f.execute(v)
        
if __name__ == '__main__':
    main()
