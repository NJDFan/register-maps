"""Manage XML output formats."""

from os import makedirs
import os.path
import datetime
import textwrap
from lxml.builder import E
from lxml.etree import tostring, Comment

from ..visitor import Visitor
from ..util import Outputs

wrapper = textwrap.TextWrapper()

@Outputs.register
class HtiXml(Visitor):
    """Generate XML output usable as XML input.
    
    This transform is not as pointless as it seems, because it locks down as
    explicit attributes all of the ones that were allowed to be
    automatically determined, inherited, or otherwise defaulted by the
    analysis system.   This provides a means of fixing locations that are
    customer facing, where it would be poor form to move it anymore.
    """
    
    outputname = 'htixml'
    extension = '.xml'
    binary = True
    
    def begin(self, startnode):
        self.header = Comment(
            "Generated automatically from {source} at {time:%d %b %Y %H:%M}.".format(
                source = startnode.sourcefile,
                time = datetime.datetime.now()
        ))
    
    def defaultvisit(self, node):
        xmlnode = E(
            type(node).__name__.lower(),
        )
        xmlnode.attrib.update(
            (k, str(v))
                for k, v in node._attrib.items()
                if v is not None
        )
        xmlnode.extend(
            E.description(
                wrapper.fill(d)
            ) for d in node.description
        )
        xmlnode.extend(self.visitchildren(node))
        return xmlnode
        
    def finish(self, tree):
        tree.insert(0, self.header)
        self.write(
            tostring(
                tree,
                xml_declaration=True, pretty_print=True,
                encoding = 'UTF-8'
        ))
