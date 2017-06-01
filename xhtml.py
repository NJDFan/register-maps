#!/usr/bin/env python
"""XHTML builder/writer module.
"""

import sys

def escape(text):
    """Escape special characters that have special meaning to XHTML parsers."""
    html_escape_table = {
        "&": "&amp;",
        '"': "&quot;",
        "'": "&apos;",
        ">": "&gt;",
        "<": "&lt;",
    }
    return "".join(html_escape_table.get(c,c) for c in str(text))

class _BaseElement(list):
    """Abstract base class representing an XHTML element.
    
    This class is meant to be subclassed, and as such does not
    define self._tagend.  This means that the __str__ method
    will fail.
    
    Usage:
    x = DerivedElement('table', attributes = {'class' : 'css_table'})
    row = x.sub('tr')
    for i in range(0, 9):
        row.sub('td').text(str(i))
        
    print x
    
    Because _BaseElement subclasses list, XHTML trees can also be
    built up by using the append() and extend() methods, as well
    as being iterated in the normal fashion.
    
    Elements contained inside of each _BaseElement are stored in
    list order. 
    """
    
    def __init__(self, tag, attributes=None, children=None):
        if children is None:
            children = []
        if attributes is None:
            attributes = {}
            
        list.__init__(self, children)
        self.tag = tag
        self.attributes = attributes
        
    def _getAttributeString(self):
        if self.attributes:
            return ' '.join()
        else:        
            return ''
           
    def text(self, text):
        """Add a plain text element inside of this element.
        
        Text is escaped for HTML safeness.
        Returns the base element.
        """
        self.append(escape(text).encode('utf-8'))
        return self
            
            
    def block(self, tag, attributes = None, children = None):
        """Create a nested BlockElement inside of this element.
        
        Returns the new nested element.
        """
        n = BlockElement(tag, attributes, children)
        self.append(n)
        return n
        
    def inline(self, tag, attributes = None, children = None):
        """Create a nested InlineElement inside of this element.
        
        Returns the new nested element.
        """
        n = InlineElement(tag, attributes, children)
        self.append(n)
        return n
        
    def _internal_tag(self):
        """Return the stuff inside the start tag for this section."""
        attributes = ['{0} = "{1}"'.format(escape(k), escape(v))
                        for (k, v) in self.attributes.items()]
                        
        attributes.insert(0, self.tag)
        return ' '.join(attributes)
        
    def _only_tag(self):
        """Return a tag for this section with no contents."""
        return '<' + self._internal_tag() + '/>'
        
    def _start_tag(self):
        """Return an opening tag for this section."""
        return '<' + self._internal_tag() + '>'
        
    def _end_tag(self):
        """Return a closing tag for this section."""
        return '</' + self.tag + '>'
        
    def __str__(self):
        raise NotImplementedError("No rule to turn base class into str.")
        
    def __repr__(self):
        try:
            return self.tag + list.__repr__(self)
        except TypeError:
            return "BAD"
    
class BlockElement(_BaseElement):
    """An XHTML element that formats itself with newlines after tags."""
    
    def __str__(self):
        if self:
            # Indent all the contents
            contents = ''.join(str(c) for c in self).rstrip().replace("\n", "\n\t")
            return self._start_tag() + "\n\t" + contents + "\n" + self._end_tag() + "\n"
            
        else:
            # No contents
            return self._only_tag() + "\n"
    
class InlineElement(_BaseElement):
    """An XHTML element that formats itself with no newlines."""
    
    def __str__(self):
        if self:
            contents = ''.join(str(c) for c in self)
            return self._start_tag() + contents + self._end_tag()
            
        else:
            # No contents
            return self._only_tag()
    
class Document(BlockElement):
    """Represents an entire XHTML document."""
    
    def __init__(self, title):
        """Create a new XHTML document."""
        
        self.doctype = '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">'
        
        head = BlockElement('head')
        head.block('title').text(title)
        body = BlockElement('body')
        
        BlockElement.__init__(self, 'html', {}, [head, body])
        
    def __str__(self):
        return self.doctype + "\n" + BlockElement.__str__(self) + "\n"
        
    def head(self):
        """Return the header element of a new document."""
        return [x for x in self if x.tag=='head'][0]
        
    def body(self):
        """Return the body element of a new document."""
        return [x for x in self if x.tag=='body'][0]

def block(tag, attributes = None, children = None):
    """Create a BlockElement."""
    return BlockElement(tag, attributes, children)
    
def inline(tag, attributes = None, children = None):
    """Create an InlineElement."""
    return InlineElement(tag, attributes, children)
        
def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    doc = Document('Example')
    body = doc.body()
    
    body.block("h1").text("This is a header 1.")
    
    paragraph = body.block("p")
    paragraph.extend([
        "This is a block of text that ",
        InlineElement('b').text('contains a bold'),
        """ section.  It probably goes on far longer
        than is strictly necessary, but we'll see
        how it goes."""
        ])
        
    print doc


if __name__ == "__main__":
    sys.exit(main())
