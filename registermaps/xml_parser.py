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

Having completed reading all of the XML files, the finish() method of
each root object should be called.  This will recursively cause all
of the objects under each root to be completed.  For most classes, the
offset and size fields can be automatically determined during this
process as well.

The reading process will also create sourcefile and sourceline members
for all contained classes.  This is useful both for generating outputs
and for debugging.

Rob Gaddi, Highland Technology.
May 31, 2011
"""

import lxml
from . import space

########################################################################
# XML Elements
########################################################################

class HtiElement():
    """Abstract base class for all elements."""
    
    def getsubclass(self, name):
        return globals()[name]
    
    def __init__(self, xml_element):
        """Derive an HtiElement from an XML element."""
    
        attrset = set(attributes)
        
        # Remap any attributes defined as not strings.
        for a in (self.numeric_attributes & attrset):
            attributes[a] = int(attributes[a], 0)
                
        for a in (self.boolean_attributes & attrset):
            attributes[a] = self._boolean(attributes[a])
        
        # Check for any missing attributes.
        missing = self.required_attributes - attrset
        if missing:
            raise InvalidStructureError('Missing required attribute ' + ', '.join(missing))
                
        # Check for any invalid values on the common ones
        if attributes.get('readOnly', False) and attributes.get('writeOnly', False):
            raise InvalidValueError('Cannot have both readOnly and writeOnly set true.')
                
        if attributes.get('format', 'bits') not in ('signed', 'unsigned', 'bits'):
            raise InvalidValueError('Illegal format, must be signed, unsigned, or bits.')
                
        # Record tagname and attributes dictionary
        dict.__init__(self, attributes)
        
        # Initialize the element's cdata and children to empty
        self.cdata = ''
        self.children = []
        self.desc = []
    
    def __hash__(self):
        return hash(self['name'])
    
    @staticmethod
    def _boolean(value):
        """Decode a Boolean value from XML into a real Boolean."""
        if isinstance(value, basestring):
            val = value.upper()
            if val in ('0', 'FALSE', 'NO'):
                return False
            elif val in ('1', 'TRUE', 'YES'):
                return True
            else:
                raise InvalidValue(val + " not a valid Boolean value.")
        else:
            return bool(value)
    
    @_prettyError    
    def _add_to_space(self, list):
        """
        Add all of the elements in the list into the space.
        
        Elements with fixed positions are placed first, then
        elements with variable positions.
        """
        
        def has_offset(x):
            return 'offset' in x
            
        for c in itertools.ifilter(has_offset, list):
            self.space.add(c, c['size'], c['offset'])
            
        for c in itertools.ifilterfalse(has_offset, list):
            self.space.add(c, c['size'])
            
        for ptr in self.space:
            if ptr: ptr.obj['offset'] = ptr.pos
    
    @_prettyError    
    def addChild(self, element):
        """Add a child while parsing the XML tree."""
        
        if isinstance(element, Description):
            self.desc.append(element)
        else:
            self.children.append(element)
        
    def getData(self):
        return self.cdata
        
    def getDescription(self):
        """Return an array of description paragraphs."""
        return [d.getData() for d in self.desc]
        
    def getChildren(self, target=None):
        """
        Return the non-description children of an HtiElement node.
        target, if provided, should be a class derived from HtiElement
        or a tuple of such classes, listing those children that should
        be returned.
        """
        if target:
            return [c for c in self.children if isinstance(c, target)]
        else:
            return self.children
    
    @_prettyError        
    def printTree(self, indent = '', target=sys.stdout):
        """A dummy output formatter, useful for debugging."""
        target.write("{0}{1} {2} @ {3}\n".format(
                indent,
                self.__class__.__name__,
                self['name'],
                self['offset']
            ))
        subindent = indent + "    "
                
        for c in self.desc:
            c.printTree(indent = subindent, target = target)
            
        for c in self.children:
            c.printTree(indent = subindent, target = target)
            
    def __repr__(self):
        return "{0}({1})".format(self.__class__.__name__, dict.__repr__(self))
    
    @_prettyError
    def finish(self):
        """
        Given that the element is now complete, fill in any missing data.
        
        This includes providing default attributes, generating FiniteSpaces
        and allocating addresses to children, etc.
        """
        
        self._pre_finish()
        for c in self.children:
            c.finish()
        self._post_finish()
            
    def _pre_finish(self):
        pass
        
    def _post_finish(self):
        pass
         
    @_prettyError
    def findParent(self, classname):
        """
        Search back through the hierarchy until a parent of the
        specified class can be found.  Return None if no parent
        of that class.
        """
        try:
            p = self.parent()
            if isinstance(p, classname):
                return p
            else:
                return p.findParent()
        except AttributeError:
            return None
    
    @_prettyError        
    def findChildren(self, classname):
        """
        Return a iterator for all children (recursively) that are an
        instance of a given class.
        """
        
        for c in self.children:
            for d in c.findChildren(classname):
                yield d
            if isinstance(c, classname):
                yield c
    
    @_prettyError            
    def byteWidth(self):
        """Return the width of the HtiElement in bytes."""
        
        return self['width'] / 8
    
    @_prettyError    
    def findOffset(self):
        """Return the total offset of the HtiElement, traced all the way to the root."""
        
        local_offset = self.get('offset', 0)
        parent = self.parent
        if parent:
            return parent().findOffset() + local_offset
        else:
            # No parent, we've hit the top of the tree.
            return local_offset
            
           
class MemoryMap(HtiElement):
    """A MemoryMap contains several Instances."""
    numeric_attributes = set(['base'])
    required_attributes = set(['name', 'base'])
    
    @staticmethod
    def build_component_map(components):
        """
        Turns a list of Components into a component map for
        the finish method.
        
        A component map is a dict full of Components.  The
        key is the component name.  The value is an ElementInfo
        structure representing the component.
        
        Keyword Arguments:
        components - A list of Components. 
        
        Returns a component map of all the components.
        """
        
        return dict([(c['name'], c) for c in components])
        
    def finish(self, component_map):
        """
        Locates and binds all Instances on the memory map.
        
        Instances need to be bound to Components, which is done by
        passing in a component_map argument. (see build_component_map).
        This causes each instance to be bound to the Component named
        in the extern attribute.
        
        Following this, a P2Space is created, and all the Instances
        are located in that space.
        """
        
        # First, deal with binding the Instances
        errors = []
        
        for inst in self.children:
            try:
                compname = inst['extern']
                inst.binding = component_map[compname]
            except KeyError:
                msg = "Unable to find component {c} to bind instance {i}.".format(
                    c = compname, i = inst['name']
                )
                errors.append(MissingComponentError(msg))
            else:
                inst.finish()
                    
        if len(errors) > 1:
            raise _Error(errors)
        elif len(errors) == 1:
            raise errors[0]
            
        # Use a space to reallocate all the instances.  In order to achieve
        # the best packing, we'll sort the children in descending size order,
        # ensuring that the largest peripherals get the first dibs on the largest
        # holes in the space.
        
        self.children.sort(key = lambda c: (-c['size'], c['name']))
        self.space = space.P2Space()
        try:
            self._add_to_space(self.children)
        except space.BlockedSpaceError as e:
            errstring = detab("""
                Placement conflict in memory map.
                Victim {v.obj[name]}:
                    Attempted Location: {v.pos}
                    Attempted Size:     {v.size}
                Aggressor {a.obj[name]}:
                    In Location: {a.pos}
                    Of Size:     {a.size}
                """)
            raise _Error(str(e) + errstring.format(
                v = e.attempt,
                a = e.blocking))
            
            
class Instance(HtiElement):
    """
    Instances bind Components to a MemoryMap.
    
    The special member binding points to a Component that this
    Instance represents a specific instantiation of.
    """
    
    numeric_attributes = set(['offset'])
    required_attributes = set(['name', 'extern'])
    
    def __init__(self, attributes):
        HtiElement.__init__(self, attributes)
        self.binding = None
    
    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            if not self.binding: raise
            return self.binding[key]
            
    def _pre_finish(self):
        """The size of an Instance should be in bytes."""
        self['size'] = self.binding['size'] * self.binding['width'] / 8;
    
class Component(HtiElement):
    """
    Components represent entire logic blocks of several Registers.
    They can be tied to a MemoryMap by using Instances.
    
    >>> comp = Component({'name' : 'BOB', 'width' : 32})
    
    After calling comp.finish(), a Component will add the
    member comp.space, a FiniteSpace which enumerates
    all of the registers in comp.

    """
    numeric_attributes = set(['width', 'size'])
    required_attributes = set(['name', 'width'])
    
    def _pre_finish(self):
        if not 'readOnly' in self:
            self['readOnly'] = False
            
        if not 'writeOnly' in self:
            self['writeOnly'] = False
            
    def _post_finish(self):
        # Use a space to reallocate all the registers
        if 'size' in self:
            self.space = space.FiniteSpace(self['size'])
        else:
            self.space = space.P2Space()
        
        self._add_to_space(self.children)
        self['size'] = self.space.size()
        
    def printTree(self, indent='', target=sys.stdout):
        self['offset'] = 'ROOT'
        HtiElement.printTree(self, indent, target)
 
class Register(HtiElement):
    """
    Registers are contained within components.
    
    >>> reg = Register({'name' : 'BOB'})
    
    After calling reg.finish(), a Register will add the
    member reg.space, a FiniteSpace which enumerates
    all of the fields in reg.
    """
    numeric_attributes = set(['offset', 'size', 'width'])
    
    def _pre_finish(self):
        """Inherit necessary attributes."""
        for attr in ['width', 'readOnly', 'writeOnly']:
            if attr not in self:
                self[attr] = self.parent()[attr]
                
        if 'size' not in self:
            self['size'] = 1
            
        if 'format' not in self:
            self['format'] = 'bits'
                
    def _post_finish(self):
        """
        Create the space member, and use it to place any
        remaining fields.  Also, create the has_fields
        member.
        """
        regsize = self.parent()['width'] * self['size']
        
        self.has_fields = bool(self.children)
        if self.has_fields:
            children = self.children
        elif (self['width'] < regsize):
            fake_field = Field({
                            'name'      : self['name'],
                            'readOnly'  : self['readOnly'],
                            'writeOnly' : self['writeOnly'],
                            'format'    : self['format']
                            })
                            
            fake_field['offset'] = 0
            fake_field['size'] = self['width']
            fake_field.parent = weakref.ref(self)
            fake_field.desc = self.desc
            fake_field.finish()
            children = [fake_field]
            
            # Having created the fake field, there's no reason to
            # keep having a width that's, from the bus point of view,
            # not true.
            self['width'] = regsize
            
        else:
            children = None
        
        if children:
            self.space = space.FiniteSpace(regsize)
            self._add_to_space(children)
        else:
            self.space = None
            
            
class Field(HtiElement):
    """
    Fields represent bit fields and contained within Registers.
    
    >>> fld = Field({'name' : 'BOB'})
    
    After calling fld.finish(), a Field will add the
    member fld.space, a FiniteSpace which covers all
    the enumeration values in the field.  fld.space is
    None for an unenumerated field.
    """
    
    numeric_attributes = set(['offset', 'size'])
    
    def _pre_finish(self):
        """Inherit necessary attributes."""
        for attr in ['width', 'readOnly', 'writeOnly']:
            if attr not in self:
                self[attr] = self.parent()[attr]
                
        if 'size' not in self:
            self['size'] = 1
            
        if 'format' not in self:
            self['format'] = 'bits'
            
    def _post_finish(self):
        """Bind values to unvalued enumerations."""
        if self.children:
            self.space = space.FiniteSpace(2 ** self['size'])
            
            def has_value(c):
                return 'value' in c
                
            for e in itertools.ifilter(has_value, self.children):
                self.space.add(e, 1, e['value'])
            for e in itertools.ifilterfalse(has_value, self.children):
                self.space.add(e, 1, e['value'])
                
            for e in self.space:
                if e: e.obj['value'] = e.pos
                
        else:
            self.space = None
                
            
class Enum(HtiElement):
    """Enums can be used to better define fields."""
    numeric_attributes = set(['value'])
    
    def printTree(self, indent = '', target=sys.stdout):
        target.write("{0}{1} {2} = {3}\n".format(
                indent,
                self.__class__.__name__,
                self['name'],
                self['value']
            ))
    
class Description(HtiElement):
    """Descriptive text for any element."""
    
    required_attributes = set()
    whitespace_normalizer = re.compile(r'\s+')
    tw = textwrap.TextWrapper()
    
    def getData(self):
        """Return CDATA with whitespace normalized."""
        return self.whitespace_normalizer.sub(' ', self.cdata.strip())
        
    def printTree(self, indent = '', target=sys.stdout):
        self.tw.initial_indent = indent
        self.tw.subsequent_indent = indent
        
        target.write(self.tw.fill('"' + self.getData() + '"'))
        target.write("\n")
    
class Array(HtiElement):
    """Arrays represent repeated entities.
    
    Any element can be repeated.  So, for instance, a MemoryMap
    may contain an InstanceArray, a Component a RegisterArray, or
    a Register a FieldArray.
    """
    numeric_attributes = set(['offset', 'count', 'framesize'])
    required_attributes = set(['count'])
    
    def _post_finish(self):
        """Form a space from the contained elements and get the
        framesize and size attributes."""
        
        if ('framesize' not in self):
            # Count up all the sizes of the children.
            self['framesize'] = sum([c['size'] for c in self.children])
            
        self.space = space.FiniteSpace(self['framesize'])
        self._add_to_space(self.children)
        
        self['size'] = self.space.size() * self['count']
        
        if ('name' not in self):
            if len(self.children) == 1:
                self['name'] = self.children[0]['name']
            else:
                raise MissingRequiredAttributeError('Array with more than one contained element needs a name.')
                
class RegisterArray(Array):
    def _pre_finish(self):
        """Inherit necessary attributes."""
        for attr in ['width', 'readOnly', 'writeOnly']:
            if attr not in self:
                self[attr] = self.parent()[attr]
                
class InstanceArray(Array):
    pass

########################################################################
# XML File Parser
########################################################################

class XmlReader:
    """XML parser for register map files."""
    elements = (    Component, Register, Description, Field, Enum,
                    MemoryMap, Instance,
                    RegisterArray, InstanceArray
                )
    element_map = dict( [(c.__name__.lower(), c) for c in elements] + [('desc', Description)])
    
    def __init__(self):
        self.root = None
        self.nodeStack = []
        
    def startElement(self, name, attributes):
        'Expat start element event handler'
        
        # Determine the element type and instantiate it
        ET = self.element_map[name]
        
        # Instantiate an HtiElement object
        element = ET(attributes)
        element.sourcefile = self.filename
        element.sourceline = self.parser.CurrentLineNumber
        
        # Push element onto the stack and make it a child of parent
        if self.nodeStack:
            parent = self.nodeStack[-1]
            parent.addChild(element)
            element.parent = weakref.ref(parent)
        else:
            self.root = element
        self.nodeStack.append(element)
        
    def endElement(self, name):
        'Expat end element event handler'
        self.nodeStack.pop()
        
    def characterData(self, data):
        'Expat character data event handler'
        if data.strip():
            data = data
            element = self.nodeStack[-1]
            element.cdata += data
            
    def Parse(self, filename):
        self.filename = filename
        
        # Create an Expat parser
        self.parser = expat.ParserCreate()
        # Set the Expat event handlers to our methods
        self.parser.StartElementHandler = self.startElement
        self.parser.EndElementHandler = self.endElement
        self.parser.CharacterDataHandler = self.characterData
        
        # Parse the XML File
        try:
            ParserStatus = self.parser.Parse(open(filename).read(), 1)
            
        except _Error as e:
            error = e.args[0] + '\nAt line {0} of {1}'.format(self.parser.CurrentLineNumber, filename)
            raise e.__class__(error)
                        
        return self.root
        
def _tree_printer(argv=None):
    if argv is None:
        argv = sys.argv
    
    parser = XmlReader()
    root_element = parser.Parse(argv[1])
    root_element.finish()
    root_element.printTree()
    return 0
    
if __name__ == "__main__":
    sys.exit(_tree_printer())
