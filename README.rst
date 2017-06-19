=============
register-maps
=============

Use XML files to describe register maps; auto-generate C, VHDL, Python, and HTML.

Execution
=========

After installing the package, the main executable is a program called
registermap.

For instance, given source XML files in ./data/src you would run::

    registermap data/src --format vhdl
    registermap data/src --format html
    
That would generate VHDL functions in the output/vhdl directory, and
HTML documentation of everything in the output/html directory.

See the docs folder for more information, as well as README.rst files in each
of the registermaps/resource/* output format folders.
