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
        
    def __repr__(self):
        return "{0}({1!r}, start={2}, size={3})".format(
            type(self).__name__, self.obj, self.start, self.size
        )

class NoResizer:
    """A null resizer; prevents resizing a Space."""
    
    @staticmethod
    def resize(spc, need):
        """Resize a Space.  Returns a PlacedObject for the gap at the end.
        
        spc - The space to be resized.
        need - The amount of space needed in the resize.
        """
        raise ValueError("Resizing this space not allowed.")
    
class LinearResizer(NoResizer):
    """Adds only as much space as needed."""

    @staticmethod
    def resize(spc, need):
        last = spc.last()
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
        newsize = spc.size + need
        spc.size = 2**((newsize-1).bit_length())
        return spc.last()
    resize.__doc__ = NoResizer.resize.__doc__

class NoPlacer:
    """A null Placer, prevents adding objects to a Space."""
    @staticmethod
    def place(obj, size, gap):
        """Try to place an object into a given gap.
        
        Returns a new PlacedObject or None if it won't fit.
        """
        raise ValueError("Not allowed to place in this Space.")
       
    @staticmethod
    def validate(po):
        """Is a PlacedObject legal by these placer rules?"""
        raise ValueError("Not allowed to place in this Space.")
        
class LinearPlacer:
    """Place an object in the first place it will fit."""
    
    @staticmethod
    def place(obj, size, gap):
        if gap.size >= size:
            return PlacedObject(obj, gap.start, size)
        return None
        
    @staticmethod
    def validate(po):
        return True
        
    place.__doc__ = NoPlacer.place.__doc__
    validate.__doc__ = NoPlacer.validate.__doc__
        
class BinaryPlacer:
    """Place an object on a power-of-2 boundary based on size."""
    
    @staticmethod
    def _alignment(size):
        """Return the next power of 2 greater than or equal to size."""
        return (1 << (size-1).bit_length())
    
    @staticmethod
    def place(obj, size, gap):
        alignment = BinaryPlacer._alignment(size)
        amask = alignment-1
        
        # Find the first alignment boundary using bit-twiddling tricks.
        start = (gap.start + amask) & ~amask
        end = start + size
        if end <= gap.end:
            return PlacedObject(obj, start, size)
        return None
        
    @staticmethod
    def validate(po):
        alignment = BinaryPlacer._alignment(po.size)
        amask = alignment-1
        return (po.start & amask == 0)
    
    place.__doc__ = NoPlacer.place.__doc__
    validate.__doc__ = NoPlacer.validate.__doc__

class Space:
    """A Space that can be filled.
    
    Optional arguments are an initial size, a Resizer class, and a
    Placer class.  Without providing a Resizer, the initial size is
    the size the Space will always be.  Without providing a Placer
    no objects can be placed in the Space, making it pretty useless.
    
    In boolean context, Space is True if there are any items stored in 
    it, or False if the space is completely empty.
    
    The data member enforce_rules_on_fixed determines whether when calling the
    .add method with a fixed start position the placer rules are used to
    determine whether that placement is legal.  The default value of
    False allows explicit placement regardless of placer rules.
    """
    
    enforce_rules_on_fixed = False
    
    def __init__(self, size=None, resizer=NoResizer, placer=NoPlacer):
        self.size = 1 if size is None else size
        self._resizer = resizer
        self._placer = placer
        self._items = []
    
    def __bool__(self):
        """"""
        return bool(self._items)
    
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
    
    def addfloating(self, obj, size):
        """Try to find a place for this object and place it there."""
        
        # First try all the existing gaps.  If we can't find one then
        # resize the space and place it in the new gap at the end.
        for idx, po in self._enumerated_iter():
            # Only interested in gaps
            if po:
                continue
            placement = self._placer.place(obj, size, po)
            if placement is not None:
                break
                
        else:
            idx = len(self._items)
            newgap = self._resizer.resize(self, need=size)
            placement = self._placer.place(obj, size, newgap)
        
        # One or the other should have always suceeded.
        assert(placement)
        self._items.insert(idx, placement)
        return placement
            
    def addfixed(self, obj, size, start):
        """Add the object at a fixed location or raise a ValueError."""
        
        # Create a PlacedObject here and see if there's a gap for it.
        newpo = PlacedObject(obj, start, size)
        if self.enforce_rules_on_fixed and not self._placer.validate(newpo):
            raise ValueError("Object of size {} at location {} violates placement rules.".format(size, start))
        
        if newpo.end > self.size:            
            # We need to resize to fit this, in which case we know that the
            # placement goes at the end.  Still, we need to check the last
            # item to make sure we're good.
            try:
                last_item = self._items[-1]
                if last_item.end > newpo.start:
                    raise ValueError(
                        "New object ({0.size}@{0.start}) blocked by exiting ({1.size}@{1.start})".format(
                        newpo, last_item
                    ))
            except IndexError:
                # No items in list yet; nothing to collide with
                pass
            
            newgap = self._resizer.resize(self, need=size)
            assert(newgap.end >= newpo.end)
            assert(newgap.start <= newpo.start)
            self._items.append(newpo)
        
        else:
            # Check to find a place to put it.  The first area we find where the
            # end is past our end is the only possible place to put it.
            end = newpo.end
            for idx, po in self._enumerated_iter():
                if po.end >= end:
                    if po:
                        raise ValueError(
                            "New object ({0.size}@{0.start}) blocked by existing ({1.size}@{1.start})".format(
                            newpo, po
                        ))
                    if po.start > newpo.start:
                        prev_item = self._items[idx-1]
                        raise ValueError(
                            "New object ({0.size}@{0.start}) blocked by existing ({1.size}@{1.start})".format(
                            newpo, prev_item
                        ))
                    self._items.insert(idx, newpo)
                    
        return newpo
        
    def add(self, obj, size, start=None):
        """Add an object into the Space.
        
        Returns a PlacedObject, though this can usually be
        ignored.  Raises ValueError if the object cannot be placed.
        
        start, if given, provides a fixed start location.
        """
        
        #import pdb
        #pdb.set_trace()
        if start is None:
            return self.addfloating(obj, size)
        else:
            return self.addfixed(obj, size, start)
        
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
            
    def at(self, index):
        """Returns the PlacedObject that encompasses index.
        
        Can also be called as space[index] where index is an int.
        
        It will be true that for PlacedObject obj,
        obj.start <= index < obj.end
        """
        
        if index < 0:
            index += self.size
        
        for po in self:
            if po.start <= index < po.end:
                return index
        raise IndexError(index)
        
    def takeslice(self, slc):
        """Returns a list of PlacedObjects spanning the slice slc.  The 
        start and end object may be truncated such that the start will 
        start at the slice start and the end ends at the slice end.
        
        Can also be called as space[slc] where slc is a slice.
        """
        
        # First, reframe the slice.
        start, stop, stride = slc.indices(self.size)
        if stride != 1:
            raise ValueError('slice stride not supported')
        
        ret = []
        for po in self:
            start = max(po.start, start)
            end = min(po.end, stop)
            if start < end:
                ret.append(PlacedObject(po.obj, start, end-start))
                    
        return ret
        
    def __getitem__(self, idx):
        """Shorthand for space.at(idx) or space.takeslice(idx) based
        on idx.
        """
        
        if isinstance(idx, int):
            return self.at(idx)
        elif isinstance(idx, slice):
            return self.takeslice(idx)
        else:
            raise ValueError("can't index {} with {}".format(
                type(self).__name__, type(idx).__name__
            ))
