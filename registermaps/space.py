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

Presently there is no ability to remove items from a Space.
"""

class PlacedObject:
    """
    Represents an object as placed in the Space.
    
    Also iterable as obj, start, size for tuple unpacking.
    
    Gaps are False, real objects are True.
    
    Members:
    obj -   The stored object.  If this object is None, the PlacedObject
            represents a gap rather than an object.
    start - The starting location in the Space.
    size -  The amount of the Space occupied by the object.
    """
    
    def __init__(self, obj, start, size):
        self.obj = obj
        self.start = start
        self.size = size
        
    def __bool__(self):
        return self.obj is not None
        
    @property
    def end(self):
        """Position 1 past the end."""
        return self.start + self.size
    
    def __getitem__(self, idx):
        attr = ['obj', 'start', 'size'][idx]
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
    resize.__doc__ = NoResizer.resize.__doc__
            
class BinaryResizer(NoResizer):
    """Adds enough space to keep a Space.size a power of 2."""
    
    @staticmethod
    def resize(spc, need):
        oldsize = spc.size
        newsize = spc.size + need
        spc.size = 2**((newsize-1).bit_length())
        return PlacedObject(None, oldsize, spc.size-oldsize)
    resize.__doc__ = NoResizer.resize.__doc__

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
        if gap.size >= size:
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
        end = start + size
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
        
        # While we're empty it's a special case.
        if not self._items:
            yield (0, PlacedObject(None, 0, self.size))
            
        else:
            prev = PlacedObject(None, -1, 1)
            for n, i in enumerate(self._items):
                if i.start > prev.end:
                    yield (n, PlacedObject(None, prev.end, i.start-prev.end))
                yield (n, i)
                prev = i
            if i.end < self.size:
                yield (n+1, PlacedObject(None, i.end, self.size-i.end))
    
    def __iter__(self):
        """Iterate over everything, items and gaps, in the space."""
        return (x[1] for x in self._enumerated_iter())
    
    def gaps(self):
        """Iterate over all the gaps in the space."""
        return (x for x in self if not x)
        
    def items(self):
        """Iterate over all the actual items in the space."""
        return (x for x in self if x)
        
    def _add_intl(self, obj, size, start, gap):
        """Try to add this object into this gap."""
        
        if (start is not None):                
            # With a fixed start location, we're only even interested
            # in a particular gap.
            if not (gap.start <= start < gap.end):
                return None
                
            # Now resize this gap to start at the correct place.
            newgap = PlacedObject(None, start, gap.end-start)
                
            # Then see if we can place here.  We need a valid
            # placement with the correct start.
            return self._placer.place(obj, size, newgap)
            
        else:
            # With an unassigned start location, we try all the
            # gaps until we get one we like.
            return self._placer.place(obj, size, gap)
        
    def add(self, obj, size, start=None):
        """Add an object into the Space.
        
        Returns a PlacedObject, though this can usually be
        ignored.  Raises IndexError if the object cannot be placed.
        
        start, if given, provides a fixed start location.
        """
        
        # We may need to resize the space to even have a chance.
        if start is not None:
            end = start + size
            need = end - self.size
            if need > 0:
                self._resizer.resize(self, need)
        
        for n, po in self._enumerated_iter():
            # Only interested in gaps
            if po:
                continue
            placement = self._add_intl(obj, size, start, po)
            if placement is not None:
                break
            
        else:
            # None of our gaps fit the criteria.  Try to resize for the
            # new object and give it one more try.
            try:
                newgap = self._resizer.resize(self, size)
                n = len(self._items)
                placement = self._add_intl(obj, size, start, newgap)
            except NotImplementedError:
                raise IndexError('No room for object of size {}'.format(size))
            
        assert(placement is not None)
        if (start is not None) and (placement.start != start):
            raise IndexError("Could not place at fixed start {}".format(start))
            
        # Alright, the placement is valid.  Store the item and
        # call it a day.
        self._items.insert(n, placement)
        return placement
        
    def __str__(self):
        """A string respresentation for debugging."""
        items = ('{}({})'.format(obj, size) for obj, _, size in self)
        return ','.join(items)

    def last(self):
        """Returns a PlacedObject for the end of the space, either a
        gap or true object."""
        
        try:
            last_item = self._items[-1]
            if last_item.end == self.size:
                return last_item
            else:
                return PlacedObject(None, last_item.end, self.size-last_item.end)
        except IndexError:
            return PlacedObject(None, 0, self.size)
