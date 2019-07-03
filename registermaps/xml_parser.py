"""
Data types for working with SoC register maps.

The HTI Reg XML concept is that a given peripheral on an SoC bus
can be described using XML.  That XML file can then be used to
cogenerate C header files, VHDL, documentation, etc.

There are two different types of XML files, those describing
components, and those describing memory maps.

A memory map file has a MemoryMap element as its root object.  This
memory map is then filled with Instances or Arrays of Instances.
Instances have an extern attribute, in which a Component is named.

A component file has a Component as its root object.  This component
is filled with Registers (or Arrays of Registers), which correspond
to memory locations in the component.  Each Register can be made up
of multiple Fields (or Arrays of Fields) representing bitfields in
the register.  Each Field can be made up of Enums, which provide
named enumeration constants for non-numeric fields.

The name of the Component is then named in the extern attribute of
an Instance, which binds one or more copies of the Component onto
the MemoryMap.

Most of these elements have elements called "offset" and "size".
These are what determine how large the element is, and where it is
located.  For instance, in a Field, these refer to bit positions:
a Field with a size of 4 and an offset of 4 is a field that is one
nibble large, located at the second least significant nibble of the
word.  For a Register, these discuss word addresses.  And for an
Instance, these discuss bytes in memory.

Once the XML files are written, the XmlReader class is used to turn
each file into a memory representation, with all of the above classes
derived from the HtiElement class.

The reading process will also create sourcefile and sourceline members
for all contained classes.  This is useful both for generating outputs
and for debugging.

Rob Gaddi, Highland Technology.
May 31, 2011
"""

import re
import os.path
import glob
from lxml import etree
from collections import ChainMap
from . import space

def ceildiv(a, b):
    """Returns ceil(a / b)."""
    return (a+b-1)//b

_tfmap = {
    'YES' : True,
    'NO' : False,
    'TRUE' : True,
    'FALSE' : False,
    '1' : True,
    '0' : False
}
def tf(text):
    """Convert common string representations of true and false to bool."""
    try:
        return _tfmap[text.upper()]
    except KeyError:
        raise ValueError('no boolean interpretation for ' + text)
    except TypeError:
        if isinstance(text, bool):
            return text
        elif isinstance(text, int):
            return bool(text)
        else:
            raise
            
def _formatvalidator(text):
    """Confirms that text is a valid field format."""
    if text not in ('bits', 'signed', 'unsigned'):
        raise ValueError('illegal format ' + text)
    return text

def toint(text):
    """str to int that accepts either decimal or "0x..." hex strings"""
    return int(text, base=0)

def inherit(fieldname):
    """Create a function that returns *fieldname* from the parent object.
    
    Example:
    
        >>> defaults = {
        ...    'readOnly' : inherit('readOnly')
        ... }
    
    """
    def inheritor(self):
        return getattr(self.parent, fieldname, None)
    return inheritor

########################################################################
# XML Elements
########################################################################

class XmlError(Exception):
    """Documents an error while parsing the XML.
    
    Attributes:
        msg (str): The error message.
        sourcefile (str): The filename where the error occured.
        element (lxml.etree._Element): The XML element where the error occured.
    """
    
    
    def __init__(self, msg, element, sourcefile='unknown file'):
        self.msg = msg
        self.element = element
        self.sourcefile = sourcefile
        
    def __str__(self):
        return "XML error in {} element at {}:{}: {}".format(
            self.element.tag,
            self.sourcefile, self.element.sourceline,
            self.msg
        )

class HtiElement():
    """Abstract base class for all elements.
    
    In addition to the attributes below provided for all classes, all 
    attributes provided by the XML (or through the default mechanisms) are 
    available through the standard Python attribute syntax.
    
    :attr:`required` and :attr:`optional` are both dicts that map attribute names to
    **typefn** functions, i.e. functions that turn a single str input into
    values of the correct type.  :func:`str` is an example of this, as are
    :func:`int` and :func:`bool`, though the locally provided functions
    :func:`toint` and :func:`tf` are more suitable for getting these values
    in this context.
    
    Attributes:
        parent (HtiElement): The parent object for this element.
        space (:class:`~registermaps.space.Space`): A space filled with the children of this object
        description (list of str): A list of description text, one paragraph
            per element.
        required (dict): Set in subclasses to map required attribute names to
            typefns. All subclasses require 'name' by default.  To avoid this,
            put ``'name' : None`` in required.
        optional (dict): Set in subclases to map optional attribute names to
            typefns.
        defaults (dict): Default values for attributes.  Attributes must be
            present in either `required` or `optional`.  Value can also be a 
            function of one argument, which is *self*, in which case the 
            function is called and the attribute given the value returned.
            
            :func:`inherit`, is a factory for default functions that retrieve
            a given attribute value from the element's parent.
            
            When using defaults, they will not be passed through the
            typefn from optional.
        space_size (int):
            Initialization argument for :attr:`space`
        space_placer (class):
            Initialization argument for :attr:`space`
        space_resizer (class):
            Initialization argument for :attr:`space`
        textasdesc (bool): If True (default), bare text inside of the element will        
            become a child <description> element.
        
    """
    
    _required = {
        'name' : str
    }
    _optional = {
        'offset' : toint,
        'size' : toint,
        'readOnly' : tf,
        'writeOnly' : tf,
    }
    _defaults = {
        'readOnly' : inherit('readOnly'),
        'writeOnly' : inherit('writeOnly'),
    }
    
    # Overload these to manage the attributes
    required = {}
    optional = {}
    defaults = {}
    
    # Overload these to manange the space
    space_size = None
    space_placer = space.NoPlacer
    space_resizer = space.NoResizer
    
    # Overload as needed
    textasdesc = True
    ischild = True
    isarray = False
    
    def __init__(self, xml_element, parent=None, sourcefile='unknown file'):
        """Derive an HtiElement from an XML element.
        
        May raise all manner of things, such as:
            KeyError - An attribute is present but not appropriate
            ValueError - An attribute cannot be converted to the right type
            AttributeError - A required attribute is missing
            
        In any of these cases, it will be wrapped in an XmlError.
        """
        
        self.parent = parent
        self.sourcefile = sourcefile
        self.sourceline = xml_element.sourceline
        
        try:
            self._processattributes(xml_element)
            self._processchildren(xml_element)
        except (KeyError, ValueError, AttributeError, IndexError) as e:
            #import traceback
            #traceback.print_exc()
            raise XmlError(str(e), xml_element, self.sourcefile) from e
    
    def _processattributes(self, xmlelement):
        """Attribute processing portion of initialization.""" 
        
        cm = ChainMap(self.required, self.optional, self._required, self._optional)
        self._attrib = attrib = {}
        
        # Read in all of the attributes present.
        for k, v in xmlelement.items():
            try:
                targettype = cm[k]
                attrib[k] = targettype(v)
            except KeyError:
                raise KeyError("attribute {} not supported on element {}".format(
                    k, xmlelement.tag
                ))
            except ValueError:
                raise ValueError("cannot make {}='{}' into {}".format(
                    k, v, targettype.__name__
                ))
            
        # Make sure we got all of the required attributes.
        requiremap = ChainMap(self.required, self._required)
        for k in requiremap:
            if k not in attrib and requiremap[k] is not None:
                raise AttributeError('required attribute {} not present'.format(k))
                
        # Make sure we got all of the optional attributes, pulling in
        # defaults (and callable defaults) as needed.
        defaultmap = ChainMap(self.defaults, self._defaults)
        for k in ChainMap(self.optional, self._optional):
            if k not in attrib:
                try:
                    d = defaultmap.get(k, None)
                    d = d(self)
                except TypeError:
                    pass
                attrib[k] = d
        
        # Check for any invalid values on the common ones
        try:
            if attrib['readOnly'] and attrib['writeOnly']:
                raise ValueError('Cannot have both readOnly and writeOnly set true.')
        except KeyError:
            pass
                
        try:
            if attrib.get('format', 'bits') not in ('signed', 'unsigned', 'bits'):
                raise ValueError('Illegal format, must be signed, unsigned, or bits.')
        except KeyError:
            pass
        
    def _processchildren(self, xml_element):
        """Child element processing portion of initialization."""
        
        self.beforechildren()
        self.space = space.Space(
            self.space_size, self.space_resizer, self.space_placer
        )
        self._description = []
        self._textdesc(xml_element.text)
               
        unplaced_children = []
        for xmlchild in xml_element:
            self._textdesc(xmlchild.tail)
            
            # Create a new child element
            kls = _classlookup(xmlchild.tag)
            htichild = kls(xmlchild, parent=self, sourcefile=self.sourcefile)
            if htichild.ischild:
                # We want to place everything with an explicitly specified
                # offset first, then let the unplaced things fill in the
                # remaining spaces.
                if htichild.offset is None:
                    unplaced_children.append(htichild)
                else:
                    po = self.space.add(htichild, htichild.size, htichild.offset)
                    htichild.place(po)
        
        for htichild in unplaced_children:
            # Pick up the ones that didn't have explicit placement.
            po = self.space.add(htichild, htichild.size, htichild.offset)
            htichild.place(po)
        
        self.afterchildren()
        if self.size is None:
            self._attrib['size'] = self.space.size
        if (self.readOnly is None) and self.space.itemcount:
            self._attrib['readOnly'] = all(obj.readOnly for obj, _, _ in self.space.items())
        if (self.writeOnly is None) and self.space.itemcount:
            self._attrib['writeOnly'] = all(obj.writeOnly for obj, _, _ in self.space.items())
        
    def _adddesc(self, text):
        """Append a description element, cleaning whitespace."""
        if text:
            text = text.strip()
            text = re.sub('\s+', ' ', text)
            self._description.append(text)
        
    def _textdesc(self, text):
        """Append descriptive text, cleaning whitespace.
        
        Raises
        ------
        ValueError: textasdesc is False.
        """
        if text:
            if self.textasdesc:
                self._adddesc(text)
            else:
                raise ValueError('unexpected free text')
        
    def beforechildren(self):
        """Hook to modify the object before the Space is created and filled."""
        pass
        
    def afterchildren(self):
        """Hook to modify the object after the Space is created and filled.
        
        If size is (still) None at the end of this, will be auto-set to space.size 
        If readOnly is (still) None at the end of this, it will try to learn from
        its children.
        """
        pass
        
    def place(self, po):
        """Hook to notify a object it has been placed in its parent.
        
        po is a PlacedObject where obj is self.
        """
        assert(po.size == self.size)
        if self._attrib['offset'] is None:
            self._attrib['offset'] = po.start
    
    def __getattr__(self, attr):
        try:
            return self._attrib[attr]
        except KeyError:
            raise AttributeError(attr)
            
    def attributes(self):
        """Return a dict of attributes."""
        return self._attrib
    
    @property    
    def description(self):
        """Iterable of description lines.
        
        Yields:
            One line at a time of description.  There is no length limit, but
            no line will contain a newline character.
        """
        
        for elem in self._description:
            text = str(elem)
            for line in text.splitlines():
                yield line
        
class Description:
    """Defines a Description element, which is a child of practically
    any HtiElement.
    
    Upon its creation, a Description will insert itself into the
    description list of its parent.
    """
    
    # Description is entirely different than an HtiElement, and as
    # such doesn't even inherit from HtiElement; it just duck types
    # an __init__ with the same prototype and the ischild element.
    
    ischild = False
    
    def __init__(self, xml_element, parent, sourcefile='unknown file'):
        if len(xml_element):
            raise ValueError('description element cannot have children')
        parent._adddesc(xml_element.text.strip())
        
class RstDescription:
    """Defines an rstdesc element (reStructuredText), which is a child of
    practically any HtiElement.
    
    Upon its creation, an RstDescription will insert itself into the
    description list of its parent.
    
    TODO: Extracting these will take more work.
    """
    
    # Description is entirely different than an HtiElement, and as
    # such doesn't even inherit from HtiElement; it just duck types
    # an __init__ with the same prototype and the ischild element.
    
    ischild = False
    
    def __init__(self, xml_element, parent, sourcefile='unknown file'):
        if len(xml_element):
            raise ValueError('description element cannot have children')
        
        # Strip leading blank lines and trailing whitespace.    
        text = re.sub(r'^(\s*\n)+', '', xml_element.text)
        text = text.rstrip()
        self._text = text
        parent._description.append(self)
        
    def __str__(self):
        return self._text
        
class MemoryMap(HtiElement):
    """A MemoryMap contains several Instances.
    
    When creating one, rather than a parent (which it will never have)
    it must be given a dict associating Components with their names.
    """
    
    optional = {
        'base' : toint,
        'spacing' : toint,
        'readOnly' : tf,
        'writeOnly' : tf,
        '{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation' : str
    }
    defaults = {
        'base' : 0x80000000,
        'spacing' : 1,
        'readOnly' : False,
        'writeOnly' : False,
    }
    space_placer = space.BinaryPlacer
    
    def __init__(self, xml_element, components, sourcefile='unknown file'):
        self._components = components
        super().__init__(xml_element, parent=None, sourcefile=sourcefile)
        
    def beforechildren(self):
        if self.size is None:
            self.space_resizer = space.BinaryResizer
        else:
            self.space_size = self.size

class Instance(HtiElement):
    """
    Instances bind Components to a MemoryMap.
    
    They must be created after the corresponding Components if no
    explicit size is given.  Size is in bytes, whereas Component size was in
    words.
    """
    
    def minimumSize(self):
        """Round up the instance size to the MemoryMap spacing."""
        spacing = self.parent.spacing
        size = self.binding.size * (self.binding.width // 8)
        n_spaces = (size + spacing - 1) // spacing
        return n_spaces * spacing
    
    optional = {
        'offset' : toint,
        'size'   : toint,
        'extern' : str
    }
    defaults = {
        'extern' : lambda self: self.name,
        'size' : minimumSize
    }
    
    @property
    def binding(self):
        """Return the Component that this is an Instance of."""
        name = self._attrib.get('extern', self.name)
        return self._components[name]
        
    @property
    def _components(self):
        return self.parent._components
        
class Component(HtiElement):
    """
    Components represent entire logic blocks of several Registers.
    They can be tied to a MemoryMap by using Instances.
    """
    
    required = {
        'width' : toint
    }
    optional = {
        'readOnly' : tf,
        'writeOnly' : tf,
        '{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation' : str
    }
    defaults = {
        'readOnly' : None,
        'writeOnly' : None
    }
    
    space_placer = space.BinaryPlacer
    
    def beforechildren(self):
        if self.size is None:
            self.space_resizer = space.BinaryResizer
        else:
            self.space_size = self.size
    
class Register(HtiElement):
    """
    Registers are contained within components.
    """
    
    optional = {
        'reset' : toint,
        'width' : toint,
        'format' : _formatvalidator
    }
    defaults = {
        'reset' : 0,
        'width' : inherit('width'),
        'size'  : 1,
        'format' : 'bits'
    }
    space_placer = space.LinearPlacer
    
    def beforechildren(self):
        # The space needs to be sized in bits rather than words.
        self.space_size = self.width * self.size
        
    def afterchildren(self):
        """Propagate field reset values up, just for fun."""
        
        if self.space:
            self._attrib['reset'] = sum(
                (obj.reset << start) for obj, start, size in self.space.items()
            )
        
class Field(HtiElement):
    """Fields represent bit fields and contained within Registers.
    
    They may hold enumeration values in a Space.
    """

    optional = {
        'reset'  : str,
        'format' : _formatvalidator
    }
    defaults = {
        'format' : 'bits'
    }
    
    space_placer = space.LinearPlacer
    
    def beforechildren(self):
        """Allow the enumeration space to operate on possible value
        of a field of our length."""
        if self.size is None:
            self.space_size = None
            self.space_resizer = space.LinearResizer
        else:
            self.space_size = 2**self.size
            
    def afterchildren(self):
        """Take size from the children if necessary."""
        if self.size is None:
            if self.space.size <= 1:
                self._attrib['size'] = 1
            else:
                self._attrib['size'] = (self.space.size - 1).bit_length()
                
        # Evaluate the reset value.
        if self.reset is None:
            self._attrib['reset'] = 0
        else:
            # Is this the name of an enumeration?
            for obj, _, _ in self.space.items():
                if self.reset == obj.name:
                    self._attrib['reset'] = obj.value
                    break
            else:
                # If it's not an enumeration it better be an integer.
                self._attrib['reset'] = toint(self.reset)
            
    @property
    def width(self):
        """Alias for size."""
        return self.size
            
class Enum(HtiElement):
    """Enums can be used to better define fields."""
    
    # Enums behave differently than anything else, so we have to 
    # override the default _optional.  We'll make value and offset
    # into aliases for one another.
    
    _optional = {}
    optional = {
        'value' : toint,
        'offset' : toint,
    }
    defaults = {
        'value' : lambda self: getattr(self, 'offset', None),
        'offset' : lambda self: getattr(self, 'value', None)
    }
    
    size = 1
    space_size = 0
    
    def place(self, po):
        if self.value is None:
            self.offset = self.value = po.start
        assert(self.value == po.start)
        assert(self.size == po.size)
    
    readOnly = writeOnly = False
    
class _Array(HtiElement):
    """Arrays represent repeated entities.
    
    Any element can be repeated.  So, for instance, a MemoryMap
    may contain an InstanceArray, a Component a RegisterArray, or
    a Register a FieldArray.
    """
    
    # There is actually NOT a required name.
    _required = {}
    required = {
        'count' : toint
    }
    optional = {
        'name' : str,
        'framesize' : toint,
        'readOnly' : tf,
        'writeOnly' : tf
    }
    
    isarray = True
    
    def afterchildren(self):
        if self.framesize is None:
            self._attrib['framesize'] = self.space.size
            
        if self.name is None:
            children = list(self.space.items())
            if len(children) == 1:
                self._attrib['name'] = children[0].obj.name
            else:
                raise ValueError('Array with more than one contained element needs a name.')
                
        self._attrib['size'] = self.framesize * self.count
        
class RegisterArray(_Array):
    space_placer = space.LinearPlacer
    space_resizer = space.BinaryResizer
    
    @property
    def width(self):
        return self.parent.width

# Build a dict crossreferencing XML tags to HtiElement subclasses.
_classes_by_name = { c.__name__.lower() : c for c in HtiElement.__subclasses__() }
_classes_by_name.update((c.__name__.lower(), c) for c in _Array.__subclasses__())
_classes_by_name['desc'] = Description
_classes_by_name['rstdesc'] = RstDescription
_classes_by_name['description'] = Description
def _classlookup(name):
    return _classes_by_name[name]

########################################################################
# XML File Parser
########################################################################

class XmlParser:
    """Used to parse one or more source files or directories into
    a collection of Components and MemoryMaps.
    """
    
    def __init__(self):
        self.components = {}
        self.memorymaps = {}
        self.componentxml = []
        self.mmxml = []
            
    def _readXml(self, filename):
        """Retreive an ElementTree from a filename."""
        parser = etree.XMLParser(remove_comments=True, remove_pis=True)
        return etree.parse(filename, parser)
        
    def analyzeDirectory(self, path):
        """Parse all .xml file in a directory.
        
        Appends to the componentxml and mmxml fields.
        
        Any XML files not rooted in a component or memorymap will throw
        an error.
        
        path supports the ``**/`` syntax, meaning "this directory and all
        subdirectories."
        """
        
        # Figure out which files code components and which code
        # memorymaps.
        #
        files = (
            os.path.join(p, f)
                for p, s, files in os.walk(path)
                for f in files
                if f.casefold().endswith('.xml')
        )
        treesorter = {
            'component' : self.componentxml,
            'memorymap' : self.mmxml
        }
        for fn in files:
            try:
                t = self._readXml(fn)
                tag = t.getroot().tag
                treesorter[tag].append((fn, t))
            except KeyError:
                raise XmlError('document root must be component or memorymap', t, fn)
    
    def elaborate(self):
        """Translates XML into HtiElements.
        
        .componentxml will be turned into .components (and cleared)
        .mmxml will be turned into .memorymaps (and cleared)
        """
        
        # Translate the components
        for fn, c in self.componentxml:
            comp = Component(c.getroot(), parent=None, sourcefile=fn)
            if comp.name in self.components:
                raise ValueError(
                    'Multiple definitions for component {}, {} and {}'.format(
                        comp.name,
                        self.components[comp.name].sourcefile,
                        comp.sourcefile
                    ))
            self.components[comp.name] = comp
        
        # Translate the memorymaps
        for fn, m in self.mmxml:
            mm = MemoryMap(m.getroot(), components=self.components, sourcefile=fn)
            if mm.name in self.memorymaps:
                raise ValueError(
                    'Multiple definitions for memorymap {}, {} and {}'.format(
                        mm.name,
                        self.memorymaps[mm.name].sourcefile,
                        mm.sourcefile
                    ))
            self.memorymaps[mm.name] = mm
        
        self.componentxml.clear()
        self.mmxml.clear()
        
    def processDirectory(self, path):
        """Parses all .xml files in a directory and turns then into HtiElements.
        
        This combines analyzeDirectory and elaborate into one call for the
        common case where all sources are in the same directory.
        """
        self.analyzeDirectory(path)
        self.elaborate()
