#!/usr/bin/env python

"""
Generate HTML documentation from HTI XML register description documents.

This program parses two different types of XML description file.
First, a file documenting a single component, and all of the
registers that it may contain.  Second, a file documenting an
overall memory map, which instantiates and calls out various
components.

"""

import argparse
import traceback
import os
import sys

from hti_reg_xml import *
import space

class OutputterError(Exception):
    """
    An error because the outputter doesn't know what to do.
    First argument is a string description, second is the
    HtiElement where the error occurred.
    """
    pass
    
########################################################################
# Routines for outputting Components
########################################################################

#
# We need to generate bitfield information for our registers.
#

def generate_register(self, reg_name_fmt):
    return reg_name_fmt(self)
    
def generate_regarray(self, reg_name_fmt):
    return reg_name_fmt(self)
    
Register.generate = generate_register
RegisterArray.generate = generate_regarray
   
#
# We need to generate all of the above for a component.
#
    
def generate_single_component(comp, instance = None):
    """Render down a component tree into a list of strings."""

    if not instance:
        raise Exception("Unbound components not handled.")
        
    mmap = instance.findParent(MemoryMap)
    comp_name = instance['name']
    base_addr = instance['offset']
    
    def reg_name_fmt(reg):
        return "'{comp}:{reg}' : 0x{loc:05X}".format(
            reg = reg['name'],
            loc = (reg.findOffset() * reg.byteWidth()) + base_addr,
            comp = comp_name)
                
    regs = []
    
    # Now go through and handle all of the registers.
    for reg in comp.space.getObjects():
        regs.append(reg.generate(reg_name_fmt))
       
    return regs

Component.generate = generate_single_component
    
########################################################################
# Routines for outputting MemoryMaps
########################################################################

def generate_instance(self):
    """
    Return a list of strings for the registers.
    """
    
    comp = self.binding
    return comp.generate(instance = self)
    
def generate_instancearray(self):
    """
    Generate an instance array's HTML files.
    
    Return a tuple containing the HTML table row for this array,
    and a space seperated list of file names.
    """
    
    x = []
    for c in self.getChildren():
        x.extend(c.generate())
    
    return x

Instance.generate       = generate_instance
InstanceArray.generate  = generate_instancearray
        
def generate_memory_map(mmap):
    """Render down a memory map tree into one big list.
    
    Keyword Arguments:
    mmap - A MemoryMap instance to generate HTML from.
    """
    
    x = []
    for inst in mmap.space.getObjects():
        x.extend(inst.generate())
        
    for line in x:
        print line
        
        
MemoryMap.generate = generate_memory_map

########################################################################
# Main code
########################################################################

def main(argv=None):
    ########################################################
    # Start by parsing the command line options.
    ########################################################
    if argv is None:
        argv = sys.argv[1:]

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', '-o', help="""
        When present, specifies a directory to write output files to.
        Output files will have the same names as the input files they
        correspond to, but with a .html extension, rather than .xml.
        When absent, all output will be written to stdout.
        """)
    ap.add_argument('--no-mmap', '-m', action="store_false", dest = 'mmap', help="""
        Ignore any memory map files; generate only abstract component
        files.
        """)
    ap.add_argument('source', nargs = '+', help="""
        Input files in the HTI XML register or memory map description
        format.
        """)

    args = ap.parse_args(argv)

    if (args.output_dir and not os.path.isdir(args.output_dir)):
        print >>sys.stderr, "Unable to write to directory {0}".format(args.output_dir)
        sys.exit(1)
        
    global output_dir 
    output_dir = args.output_dir

    ########################################################
    # Read all the XML files
    ########################################################

    parser = XmlReader()
    components = []
    maps = []

    for source in args.source:
        try:
            root = parser.Parse(source)
            if isinstance(root, Component):
                root.finish()
                components.append(root)
            
            elif isinstance(root, MemoryMap):
                maps.append(root)
                
        except:
            print >>sys.stderr, "Error parsing {0}".format(source)
            traceback.print_exc()

    ########################################################
    # And generate all of the outputs
    ########################################################
    
    cmap = MemoryMap.build_component_map(components)
    for mmap in maps:
        mmap.finish(cmap)
        mmap.generate()
            
if __name__ == "__main__":
    sys.exit(main())
