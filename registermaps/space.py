"""
Represents a Space that can be filled.

A Space is a one-dimensional structure such as a tape, a memory
region, or a disk.  It contains non-overlapping, objects that have
positions and sizes.  These objects are not necessarily stored
consecutively; the Space may also contain gaps between objects or
on the ends of the Space.

Objects can be placed into the Space either at defined positions
or just wherever they'll fit.  For an object to fit at any given
position, that next object in the space must be no closer than
the object's size to the position.  If for instance you have a
Space of size 10

    0123456789
    ..........
    
And place an object A into at position 4 with size 3, you'll have

    0123456789
    ....AAA...
    
This space now still has room for an object of size <= 4 and an object
of size <= 3, but cannot hold a larger object anymore.  If you then
place an object B of size 4 with no guidelines on where to fit it, it
will fill the first available gap.

    0123456789
    BBB.AAA...

Spaces are derived from FiniteSpace, a Space of a finite overall
size.  Presently there is no ability to remove items from a Space.
"""

def clp2(x):
    """Find the lowest number which is a whole power of 2 that is >= x."""
    if (x < 1):
        return 0
    
    y = 1
    while (y < x):
        y = y * 2
        
    return y

class PlacedObject:
    """
    Represents an object as placed in the Space.
    
    Also iterable as obj, pos, size for tuple unpacking.
    
    Gaps are False, real objects are True.
    
    Members:
    obj -   The stored object.  If this object is None, the PlacedObject
            represents a gap rather than an object.
    pos -   The starting location in the Space.
    size -  The amount of the Space occupied by the object.
    """
    
    def __init__(self, obj, pos, size):
        self.obj = obj
        self.pos = pos
        self.size = size
        
    def __bool__(self):
        return self.obj
        
    @property
    def start(self):
        """Start position."""
        return self.pos
        
    @property
    def end(self):
        """Position 1 past the end."""
        return self.pos + self.size
    
    def __getitem__(self, idx):
        attr = ['obj', 'pos', 'size'][idx]
        return getattr(self, attr)

class NoResizer:
    """A null resizer; prevents resizing a Space."""
    
    @staticmethod
    def resize(spc, need):
        """Resize a Space.  Returns a PlacedObject for the gap at the end.
        
        spc - The space to be resized.
        need - The amount of space needed in the resize.
        """
        raise NotImplementedError("Resizing this space not allowed.")
    
class LinearResizer(NoResizer):
    """Adds only as much space as needed."""

    @staticmethod
    def resize(spc, need):
        for g in spc:
            last = g
        if not last:
            # The Space currently ends with a gap, we can use it.
            spc.size += need - last.size
            return PlacedObject(None, last.start, need)
        else:
            # The Space currently ends with an object
            spc.size += need
            return PlacedObject(None, last.end, need)
    resize.__doc__ = NoResize.resize.__doc__
            
class BinaryResizer(NoResizer):
    """Adds enough space to keep a Space.size a power of 2."""
    
    @staticmethod
    def resize(spc, need):
        oldsize = spc.size
        newsize = spc.size + need
        spc.size = 2**((newsize-1).bit_length())
        return PlacedObject(None, oldsize, spc.size-oldsize)
    resize.__doc__ = NoResize.resize.__doc__

class NoPlacer:
    """A null Placer, prevents adding objects to a Space."""
    @staticmethod
    def place(obj, size, gap):
        """Try to place an object into a given gap.
        
        Returns a new PlacedObject or None if it won't fit.
        """
        raise NotImplementedError("Not allowed to place in this Space.")
        
class LinearPlacer:
    """Place an object in the first place it will fit."""
    
    @staticmethod
    def place(obj, size, gap):
        if gap.size > size:
            return PlacedObject(obj, gap.start, size)
        return None
    place.__doc__ = NoPlacer.place.__doc__
        
class BinaryPlacer:
    """Place an object on a power-of-2 boundary based on size."""
    
    @staticmethod
    def place(obj, size, gap):
        # Alignment is the next power of 2 greater than or
        # equal to size.
        alignment = 2**(size-1).bit_length()
        amask = alignment-1
        
        # Find the first alignment boundary using bit-twiddling tricks.
        start = (gap.start + amask) & ~amask
        end = aligned_start + size
        if end <= gap.end:
            return PlacedObject(obj, start, size)
        return None            
    place.__doc__ = NoPlacer.place.__doc__

class Space:
    def __init__(self, size=None, resizer=NoResizer, placer=NoPlacer):
        self.size = 1 if size is None else size
        self._resizer = resizer
        self._placer = placer
        self._items = []
    
    def _enumerated_iter(self):
        """Generate (idx, po) pairs of index and PlacedObject. 
        
        index preceeds the next true object if po is a gap.
        """
        
        prev = PlacedObject(None, -1, 1)
        for n, i in enumerate(self.items):
            if i.start > prev.end:
                yield (n, PlacedObject(None, prev.end, i.start))
            yield (n, i)
            prev = i
        if i.end < self.size:
            yield (n+1, PlacedObject(None, i.end, self.size))
    
    def __iter__(self):
        """Iterate over everything, items and gaps, in the space."""
        return (x[1] for x in self._enumerated_iter())
    
    def gaps(self):
        """Iterate over all the gaps in the space."""
        return (x for x in self if not x)
        
    def items(self):
        """Iterate over all the actual items in the space."""
        return (x for x in self if x)
        
    def add(self, obj, size, start=None):
        """Add an object into the Space.
        
        Returns a PlacedObject, though this can usually be
        ignored.  Raises IndexError if the object cannot be placed.
        
        start, if given, provides a fixed start location.
        """
        
        for n, po in self._enumerated_iter():
            # Only interested in gaps
            if po:
                continue
                
            if (start is not None):                
                # With a fixed start location, we're only even interested
                # in a particular gap.
                if not (g.start <= start < end):
                    continue
                    
                # Then see if we can place here.  We need a valid
                # placement with the correct start.
                placement = self._placer.place(obj, size, po)
                if (placement is None) or (placement.start != start):
                    raise IndexError("Could not place at fixed start {}".format(start))
                    
            else:
                # With an unassigned start location, we try all the
                # gaps until we get one we like.
                placement = self._placer.place(obj, size, po)
                if placement is None:
                    continue
                
            # Alright, the placement is valid.  Store the item and
            # call it a day.
            self._items.insert(n, placement)
            return placement
            
        # None of our gaps fit the criteria.  Try to resize for the
        # new object and give it one more try.
        try:
            newgap = self._resizer.resize(self, size)
            placement = self._placer.place(obj, size, newgap)
            if (placement is not None) and (start is None or placement.start == start):
                return placement
        except NotImplementedError:
            pass
        raise IndexError('No room for object of size {}'format(size))
        
    def __str__(self):
        """A string respresentation for debugging."""
        items = ('{}({})'.format(obj, size) for obj, pos, size in self)
        return ','.join(items)

class FiniteSpace:
    """
    Represents a finite space fillable with objects of finite size, such
    as a Component filled with Registers, or a CD filled with songs.
    
    Spaces hold abstract objects, which can be anything, along with
    their sizes and positions.  Sizes and positions are integers
    that are >= 0.
    
    >>> sp = FiniteSpace(32)
    >>> sp.add('Hello', 4, 4)
    >>> sp.add('world', 6)
    >>> sp.add('Say', 2)
    >>> for s in sp:
    ...     if s: print '{0} @ {1}'.format(s.obj, s.pos)
    ...
    Say @ 0
    Hello @ 4
    world @ 8
    >>> sp.size()
    32
    >>> sp.last_open_space()
    14
    
    Internal members:
    _obj    -   A list of the contained objects, end first.  The last element is always EmptySpace.
                None elements are used to signify gaps.
                
    _pos    -   An aligned list of the positions of the _objs.  The last element is always
                the total size of the Space, and the numbers are always sorted ascending.
                
    These lists always fill the space; there are no gaps.
    """
    
    class EmptySpace:
        """Represents a zero length space, used as a placeholder for the end of the list."""
        pass

    def __init__(self, size):
        """Initialize a new FiniteSpace."""
        self._obj = [None, self.EmptySpace()]
        self._pos = [0, size]

    def __iter__(self):
        """
        Return all of the objects in the space as PlacedObjects.
        Gaps will be included, returned as PlacedObjects where .obj=None
        """
        
        for (i, obj) in enumerate(self._obj[:-1]):
            pos = self._pos[i]
            nextpos = self._pos[i+1]
            yield PlacedObject(self._obj[i], pos, nextpos - pos)
            
    def __getitem__(self, idx):
        """Return the object with a given index in the space as a
        PlacedObject.  Gaps will be included, returned as PlacedObjects
        where .obj=None
        """
        pos = self._pos[idx]
        nextpos = self._pos[idx+1]
        obj = self._obj[idx]
        return PlacedObject(obj, pos, nextpos - pos)
    
    def __len__(self):
        """
        Return the number of objects in the space, including gaps.
        """
        return len(self._obj) - 1
    
    def getObjects(self):
        """
        Return all of the actual objects in order.
        Don't return gaps.
        """
        for obj in self._obj[:-1]:
            if obj is not None:
                yield obj
    
    def size(self):
        """Return the current size of the space."""
        return self._pos[-1]
    
    def last_open_space(self):
        """
        Return the position of the last open spot in the space.
        Equal to size() if there is no open space.
        """
        for i in reversed(range(len(self._obj))):
            if self._obj[i] is None:
                return self._pos[i]
        return self._pos[-1]
    
    def resize(self, newsize):
        """Resize the space."""
        if self.last_open_space() > newsize:
            raise InsufficientSpaceError("Can't shrink to {0}".format(newsize))
        else:
            # If the last space wasn't an open space, add one in
            # of zero size.  It'll get enlarged in a second.
            if self._obj[-2] is not None:
                self._pos.insert(-1, self._pos[-1])
                self._obj.insert(-1, None)
                
            self._pos[-1] = newsize
    
    def align(self, position, size):
        """Apply any alignment rules that would increment this position
        based on the size."""
        return position
    
    def add(self, obj, size, position=None):
        """
        Add an element into the Space.
        
        Keyword Arguments:
        obj - The object to be placed.
        size - The amount of the Space taken up by obj.
        position - Where (in size relative terms) to place the
        new object.  If None, the object will be placed at the
        first location it fits.
        """
        
        # Figure out where to stick our new object
        if position is not None:
            attempt = PlacedObject(obj, size, position)
        
            if (position < 0) or (position >= self.size()):
                raise OutOfBoundsError(
                    "Position ({0}) is outside finite space 0 <= pos < {1}".format(position, self.size()),
                    attempt = attempt)
                
            # Get the index of the gap we want to fit into
            afteridx = bisect.bisect_right(self._pos, position) 
            newidx = afteridx - 1
            
            # Take a quick look at the object we'll be replacing
            if self._obj[newidx]:
                raise BlockedSpaceError(
                    "Position {0} already occupied.".format(position),
                    attempt = attempt,
                    blocking = self[newidx])
            
            nextgap = position + size
            if nextgap > self._pos[afteridx]:
                if isinstance(self._obj[afteridx], self.EmptySpace):
                    raise OutOfBoundsError(
                        "Object hangs over end of space.",
                        attempt = attempt)
                        
                else:
                    raise BlockedSpaceError(
                        "Blocked by object at position {0}.".format(self._pos[afteridx]),
                        attempt = attempt,
                        blocking = self[afteridx])
                
        else:
            # Find the first position we can slot into.
            found = False
            for (idx, target) in enumerate(self._obj[:-1]):
                if target is None:
                    position = self.align(self._pos[idx], size)
                    if (self._pos[idx + 1] >= position + size):
                        # Position the element in the beginning of the gap
                        found = True
                        nextgap = position + size
                        newidx = idx
                        afteridx = idx + 1
                        break
                    
            if not found:
               raise InsufficientSpaceError("Insufficient space anywhere.", obj)
                
        # Insert the new object
        newobjs = [obj]
        newpos  = [position]
        
        if (position != self._pos[newidx]):
            newobjs.insert(0, None)
            newpos.insert(0, self._pos[newidx])
            
        if (nextgap != self._pos[afteridx]):
            newobjs.append(None)
            newpos.append(nextgap)
            
        self._obj[newidx:afteridx] = newobjs
        self._pos[newidx:afteridx] = newpos
        
    def compress(self):
        """Collapse adjoining None objects into one."""
        
        for idx in reversed(range(len(self._pos) - 1)):
            if (self._obj[idx] is None) and (self._obj[idx + 1]) is None:
                del self._obj[idx]
                del self._pos[idx]
                
    def pretty(self):
        """
        Print a pretty list of what's in the space.
        
        This is primarily useful for debugging.
        """
        
        for (i, obj) in enumerate(self._obj):
            print "{n},\t{s}".format(
                n = self._pos[i],
                s = repr(obj))
                
class P2Space(FiniteSpace):
    """A space that will enlarge to the next power of 2 as necessary to
    allow for all all elements to be added.  Also will align elements
    to internal power of two boundaries.
    
    >>> sp = P2Space()
    >>> sp.add('Hello', 6)
    >>> sp.add('world', 6)
    >>> sp.add('Say', 2)
    >>> for s in sp:
    ...     if s: print '{0} @ {1}'.format(s.obj, s.pos)
    ...
    Hello @ 0
    Say @ 6
    world @ 8
    >>> sp.size()
    16
    >>> sp.last_open_space()
    14
    
    """
    
    def __init__(self, size=1):
        FiniteSpace.__init__(self, size)
    
    def align(self, position, size):
        """Align to the power of two that matches the size."""
        alignment = clp2(size)
        
        roundoff = (position % alignment)
        if roundoff:
            return position + alignment - roundoff
        else:
            return position
        
    def add(self, obj, size, position=None):
        try:
            FiniteSpace.add(self, obj, size, position)
            
        except OutOfBoundsError:
            # We had a fixed position to go to.  Resize and try again.
            end = position + size
            top = clp2(end)
            self.resize(top)
            FiniteSpace.add(self, obj, size, position)
            
        except InsufficientSpaceError:
            # There just wasn't room.  Resize and try again.
            end = self.align(self.last_open_space(), size) + size
            top = clp2(end)
            self.resize(top)
            FiniteSpace.add(self, obj, size, position)
            
