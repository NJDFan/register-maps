#!/usr/bin/env python

"""
Generate HTML documentation from HTI XML register description documents.

This program parses two different types of XML description file.
First, a file documenting a single component, and all of the
registers that it may contain.  Second, a file documenting an
overall memory map, which instantiates and calls out various
components.

"""

import textwrap
import datetime
import argparse
import traceback
import codecs
import os
import sys

import xhtml

from hti_reg_xml import *
import space

class OutputterError(Exception):
    """
    An error because the outputter doesn't know what to do.
    First argument is a string description, second is the
    HtiElement where the error occurred.
    """
    pass
	
output_dir = ''
codec = codecs.lookup('utf-8')[-1]
    
########################################################################
# General purpose output formatting stuff
########################################################################

def register_format(r, default = ''):
    """Returns the format (signed, unsigned, or nothing) and access
     class ('Read-Only', 'Write-Only' or a default) of a register.
     
     Places parentheses around if the return text isn't empty.
     """
    fmt = r.get('format', '')
    if (fmt == 'signed'):
        ret = ' Signed'
    elif (fmt == 'unsigned'):
        ret = ' Unsigned'
    else:
        ret = ''
        
    ro = r['readOnly']
    wo = r['writeOnly']
    
    if (ro):
        ret = ret + ' Read-Only'
    elif (wo):
        ret = ret + ' Write-Only'
    else:
        ret = ret + default
        
    ret = ret.strip()
    if ret:
        ret = '(' + ret + ')'
        
    return ret
    
########################################################################
# Routines for outputting Components
########################################################################

#
# We need to generate bitfield information for our registers.
#

def generate_register(self, reg_name_fmt):

    """Generate the description bitfield table and definition list for a register."""
    root = xhtml.block('div', {'class' : 'register', 'id': self['name']})
            
    header = root.block('h3')
    header.text(reg_name_fmt(self))
    
    for d in self.getDescription():
        root.block('p').text(d)
            
   
    ### Write the bitfield tables.
    if self.space:
        # Figure out how many lines we need at 16 bits per line.
        number_of_lines = (self['width'] + 15) / 16
        
        # Split the space of Fields onto these fieldlines
        fieldlines = [space.FiniteSpace(16) for i in range(number_of_lines)]
        
        for obj in self.space:
            line = obj.pos / 16
            pos = obj.pos % 16
            size = obj.size
            
            while (size > 0):
                # Write this object across as many lines as needed.
                localsize = min(size, 16 - pos)
                fieldlines[line].add(obj.obj, localsize, pos)
                size -= localsize
                line += 1
                pos = 0
                
        for f in fieldlines:
            f.compress()
            
        # Write the XHTML table.
        table = root.block('table', {'class' : 'bitfield'})
        for lineno in reversed(range(len(fieldlines))):
            # Write the bit numbers
            row = table.block('tr', {'class' : 'bit_numbers'})
            for bit in reversed(range(lineno * 16, (lineno + 1) * 16)):
                row.inline('td').text(str(bit))
            
            # Write the fields
            row = table.block('tr', {'class' : 'fields'})
            for obj in reversed(tuple(fieldlines[lineno])):
                cell = row.block('td')
                cell.attributes['colspan'] = obj.size
                
                if obj:
                    cell.text(obj.obj['name'])
                    cell.attributes['class'] = 'std_field'
                else:
                    cell.text('-')
                    cell.attributes['class'] = 'reserved_field'
                    
    ### Describe the bitfields.
    if self.has_fields:
        fieldlist = root.block('ul', {'class': 'fieldlist'})
        for f in reversed(tuple(self.space.getObjects())):
            
            
            fielditem = fieldlist.block('li')
            
            if (f['size'] == 1):
                rng = '[{0}]'.format(f['offset'])
            else:
                rng = '[{0}:{1}]'.format(
                            f['offset'] + f['size'] - 1,
                            f['offset']) 
            
            topline = fielditem.inline('p')
            topline.text(f['name'] + ' ')
            topline.inline('span', {'class':'fielddef'}).text('{rng} {fmt}'.format(
                                                            rng = rng,
                                                            fmt = register_format(f)))
                                                            
            for d in f.getDescription():
                fieldlist.block('p').text(d)
                
            enums = tuple(f.findChildren(Enum))
            if enums:
                enumlist = fieldlist.block('dd').block('dl', {'class': 'enumlist'})
                for e in enums:
                    enumlist.block('dt').text('{0} - ({1})'.format(
                        e['name'],
                        e['value']
                    ))
                    for d in e.getDescription():
                        enumlist.block('dd').text(d)
                        
    return root
    
def generate_regarray(self, reg_name_fmt):
    """Generate prototypical registers for the register array."""
    
    root = xhtml.block('div', {'class' : 'regarray', 'id': "ARRAY_" + self['name']})
    
    root.block('h2').text(reg_name_fmt(self))
    root.block('p').text('Base of an array with {count} copies.'.format(count = self['count']))
            
    for d in self.getDescription():
        root.block('p').text(d)
        
    for obj in self.space.getObjects():
        root.append(obj.generate(reg_name_fmt))
        
    return root
    
Register.generate = generate_register
RegisterArray.generate = generate_regarray
   
#
# We need to generate all of the above for a component.
#
    
def generate_single_component(comp, instance = None):
    """Render down a component tree into an XHTML file.
    
    Keyword Arguments:
    comp - A Component generate HTML from.
    
    instance - An Instance object that is binding comp if called in
    the context of a memory map.  Skip this to generate only abstract
    information about Components instead.
    
    Returns an XHTML tree.
    """

    if instance:
        mmap = instance.findParent(MemoryMap)
        comp_name = instance['name']
        base_addr = instance['offset'] + mmap['base']
        
        if (comp_name == comp['name']):
            title = '{comp} Register Map'.format(comp = comp_name)
        else:
            title = '{inst} Register Map (Instance of {comp})'.format(
                        inst = comp_name,
                        comp = comp['name'])
                
        def reg_name_fmt(reg):
            return '{reg} (Byte Address 0x{loc:08X}) {access}'.format(
                reg = reg['name'],
                loc = (reg.findOffset() * reg.byteWidth()) + base_addr,
                access = register_format(reg, ' Read-Write'))
                
    else:
        comp_name = comp['name']
        base_addr = 0
        title = '{comp} Register Map'.format(comp = comp_name)

        def reg_name_fmt(reg):
            return '{reg} (Word Offset 0x{loc:03}) {access}'.format(
                reg = reg['name'],
                loc = reg.findOffset(),
                access = register_format(reg, ' Read-Write'))
                
    doc = xhtml.Document(title)
    doc.head().block(
        'link',
        {   'rel'  : 'stylesheet',
            'type' : 'text/css',
            'href' : '../style/reg.css'
        })
        
    body = doc.body()
    body.block('h1').text(title)
    if instance:
        breadcrumb = body.block('p', attributes={"hide_word" : "true"})
        breadcrumb.inline('a',
            {'href' : make_target_filename('', mmap.sourcefile)}
            ).text(mmap['name'])
        breadcrumb.text('->' + comp_name)
        desc = instance.getChildren(Description)
    else:
        desc = []
    desc.extend(comp.getDescription())
    for d in desc:
        body.block('p').text(d)
    body.block('hr')

    # Now go through and handle all of the registers.
    for reg in comp.space.getObjects():
        body.append(reg.generate(reg_name_fmt))
        
    # Put a footer at the bottom of the page
    body.block('hr')
    body.block('p', attributes={"hide_word" : "true"}).text("Generated automatically from {source} on {date}.".format(
            source = os.path.basename(comp.sourcefile),
            date = datetime.datetime.now().ctime()))
                    
    return doc

Component.generate = generate_single_component
    
########################################################################
# Routines for outputting MemoryMaps
########################################################################

def generate_instance(self):
    """
    Generate a Component's HTML file for a given instance.
    
    Return a tuple containing:
        An HTML table row for this instance
          Peripheral, Base Address, Description
          
        The filename that the component was written to
    """
    
    mmap = self.findParent(MemoryMap)
    basename = mmap['name'] + "_" + self['name'] + '.html'    
    filename = make_target_filename(output_dir, basename)
    comp = self.binding
    baseaddr = self['offset'] + mmap['base']
    
    with open(filename, 'w') as target:
        print >>codec(target), str(comp.generate(instance = self))
        
    def link():
        return xhtml.inline(
                        tag = 'a',
                        attributes = {
                            'href' : basename
                        })
        
    row = xhtml.block('tr', {'class' : 'peripheral'})
    
    row.inline(
        tag = 'td',
        attributes = {'class' : 'peripheral'},
        children = [ link().text(self['name']) ]
    )
    row.inline(
        tag = 'td',
        attributes = {'class' : 'address'},
        children = [ link().text('0x{0:08X}'.format(baseaddr)) ]
    )
    
    desc = row.block(
        tag = 'td',
        attributes = {'class' : 'desc'}
    )
    desc.block('p', {'class' : 'type'}).text(comp['name'])
        
    extra_description = self.getDescription()
    if not extra_description:
        extra_description = comp.getDescription()
        
    if extra_description:
        desc.block('p').text(extra_description[0])
        
    return (row, filename)
    
def generate_instancearray(self):
    """
    Generate an instance array's HTML files.
    
    Return a tuple containing the HTML table row for this array,
    and a space seperated list of file names.
    """
    
    cell = xhtml.block('tr').block('td', {'colspan' : '3', 'class' : 'array'}) 
    subtable = cell.block('table')
    
    filelist = []
    
    for c in self.getChildren():
        (row, fn) = c.generate()
        subtable.append(row)
        filelist.append(fn)
        
    return (cell, ' '.join(filelist))

Instance.generate       = generate_instance
InstanceArray.generate  = generate_instancearray

def generate_memory_map(mmap):
    """Render down a memory map tree into multiple HTML files.
    
    Keyword Arguments:
    mmap - A MemoryMap instance to generate HTML from.
    """
    
    basename = make_target_filename(output_dir, mmap.sourcefile)
    
    doc = xhtml.Document(mmap['name'])
    doc.head().block(
        'link',
        {   'rel'  : 'stylesheet',
            'type' : 'text/css',
            'href' : '../style/map.css'
        })
        
    body = doc.body()
    
    body.block('h1').text(mmap['name'] + " Peripheral Map")
    for d in mmap.getDescription():
        body.block('p').text(d)
    body.block('hr')
    
    # Time to put all of the instances down    
    table = body.block('table', {'class' : 'component_list'})
    row = table.block('tr')
    row.block('th').text('Peripheral')
    row.block('th').text('Base Address')
    row.block('th').text('Description')
    
    filelist = [basename]
    for inst in mmap.space.getObjects():
        (row, fn) = inst.generate()
        table.append(row)
        filelist.append(fn)
        
    # Put a footer at the bottom of the page
    body.block('hr')
    body.block('p', attributes={"hide_word" : "true"}).text("Generated automatically from {source} on {date}.".format(
            source = os.path.basename(mmap.sourcefile),
            date = datetime.datetime.now().ctime()
        ))
    
    with open(basename, 'w') as output:
        print >>output, doc
        
    # Write out the dependency file so that Make can build PDFs
    # from the HTML.
    
    with open("html.d", 'w') as output:
        htmlfiles = ' '.join(filelist)
        print >>output, "HTMLFILES :=", htmlfiles
        
MemoryMap.generate = generate_memory_map
        
########################################################################
# Main code
########################################################################

def make_target_filename(output_dir, sourcefile):
    """The name of a header file generated by a given source file."""
    basename = os.path.basename(sourcefile)
    (root, ext) = os.path.splitext(basename)
    basename = root + ".html"
    
    if output_dir:
        return os.path.join(output_dir, basename)
    else:
        return basename

def output_select(output_dir, sourcefile):
    """If output_dir is non-null, produce a context manager for
    an output file, with the name derived from output_dir and sourcefile.

    Otherwise, produce a context manager that simply wraps
    the standard output stream.

    """
    class StdoutWrapper:
        def __enter__(self):
            return sys.stdout

        def __exit__(self, type, value, traceback):
            return

    if output_dir:
        return open(make_target_filename(output_dir, sourcefile), 'w')

    else:
        return StdoutWrapper()

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
    
    # Because whole memory maps require linkages, just ignore them
    # if we don't have a directory target.
    if maps and output_dir and args.mmap:
        cmap = MemoryMap.build_component_map(components)
        for mmap in maps:
            mmap.finish(cmap)
            mmap.generate()
            
    else:
        for comp in components:
            with output_select(output_dir, comp.sourcefile) as target:
                print >>codec(target), str(comp.generate(instance = None))

if __name__ == "__main__":
    sys.exit(main())
