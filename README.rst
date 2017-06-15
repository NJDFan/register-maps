=============
register-maps
=============

Use XML files to describe register maps; auto-generate C, VHDL, Python, and HTML.

Execution
=========

After installing the package, the main executable is a program called
registermap.

Given source XML files in ./data/src you would run::

    registermap vhdl.basic data/src --output output/vhdl
    registermap html.basic data/src --output output/html
    
And so on.

See the docs folder for more information, as well as README.rst files in each
of the registermaps/resource/* output format folders.
