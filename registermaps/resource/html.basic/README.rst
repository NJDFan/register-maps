=================
Basic HTML Output
=================

HTML is used to generate documentiation.  The primary output is html.basic,
which generates HTML files for Components and MemoryMaps.

In the selected output directory, the following files will be created:

   - An HTML file for each Component, represent the unbound Component with a
     base address of 0.
     
   - An HTML file for each MemoryMap, with a table of Instances, their offsets
     and sizes.
     
   - A subdirectory for each MemoryMap, with a Component style HTML file for
     each Instance reprenting the bound Component with a start address
     determined by the MemoryMap.

   - CSS styles for all of the HTML
   
In this way, the directory serves as a package of documentation for the
register map source.  It can be moved as one big atomic thing.

All HTML files have table of contents sidebars to help navigation.
