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

class Instantiator:
    """Descriptor that returns a common instance when called on a class or
    the current instance when called on an instance.
    
    This only works if the class requires no arguments to __init__.
    
    This is just to avoid creating a zillion instances of these little classes.
    """
    
    def __init__(self):
        self.instances = {}
    
    def __get__(self, obj, objtype=None):
        if obj is not None:
            return obj
        try:
            x = self.instances[objtype]
            return x
        except KeyError:
            x = objtype()
            self.instances[objtype] = x
            return x

class Resizer:
    """Abstract base class for a Resizer."""
    
    def resize(self, spc, minsize):
        """Resize a Space to at least minsize.
        
        spc - The space to be resized.
        minsize - The minimum new size of the space.
        """
        # Make sure this is legal. IndexError means the array is empty.
        try:
            lastitem = spc._items[-1]
            if lastitem.end > minsize:
                minsize = lastitem
        except IndexError:
            pass
        
        return self.doresize(spc, minsize)
        
    def doresize(self, spc, minsize):
        raise NotImplementedError('resize')
        
    instance = Instantiator()
        
class NoResizer(Resizer):
    """A null resizer; prevents resizing a Space."""
    
    def doresize(self, spc, minsize):
        raise ValueError("Resizing this space not allowed.")
    
class LinearResizer(Resizer):
    """Adds only as much space as needed."""

    def doresize(self, spc, minsize):
        spc.size = minsize
    
class BinaryResizer(Resizer):
    """Adds enough space to keep a Space.size a power of 2."""
    
    def doresize(self, spc, minsize):
        spc.size = (1 << (minsize-1).bit_length())
        
class Placer:
    """Abstract base class for a Resizer."""
    
    def place(self, obj, size, gap):
        """Try to place an object into a given gap.
        
        Returns a new PlacedObject or None if it won't fit.
        """
        
        possible = self.placeInfinite(obj, size, gap.start)
        if possible.end <= gap.end:
            return possible
        else:
            return None
        
    def validate(self, po):
        """Is this PlacedObject legal by these placer rules?"""
        wouldplace = self.placeInfinite(po.obj, po.size, po.start)
        return wouldplace.start == po.start
        
    def placeInfinite(self, obj, size, minstart):
        """Make a PlacedObject in an infinite gap starting at minstart."""
        raise NotImplementedError('placeInfinite')
        
    instance = Instantiator()
        
class NoPlacer(Placer):
    """A null Placer, prevents adding objects to a Space."""
    
    def placeInfinite(self, obj, size, minstart):
        raise ValueError("Not allowed to place in this Space.")
        
class LinearPlacer(Placer):
    """Place an object in the first place it will fit."""
    
    def placeInfinite(self, obj, size, minstart):
        return PlacedObject(obj, minstart, size)
        
class BinaryPlacer(Placer):
    """Place an object on a power-of-2 boundary based on size."""
    
    def placeInfinite(self, obj, size, minstart):
        alignment = (1 << (size-1).bit_length())
        amask = alignment-1
        
        # Find the first alignment boundary using bit-twiddling tricks.
        start = (minstart + amask) & ~amask
        return PlacedObject(obj, start, size)
        
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
        self.size = 0 if size is None else size
        
        # Allow passing classes rather than an object for the placer and
        # resizer.
        
        self._resizer = resizer.instance
        self._placer = placer.instance
        self._items = []
    
    def __bool__(self):
        """True if there are any true items in the space."""
        return bool(self._items)
    
    @property
    def itemcount(self):
        """Number of true items in the space."""
        return len(self._items)
    
    @property
    def gapcount(self):
        """Number of gaps in the space."""
        return sum(1 for _ in self.gaps())
    
    def __len__(self):
        return sum(1 for _ in self._enumerated_iter())
    
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
            placement = self._placer.placeInfinite(obj, size, self.lastgap().start)
            idx = len(self._items)
            self._resizer.resize(self, placement.end)
        
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
            
            try:
                self._resizer.resize(self, newpo.end)
                assert(self.size >= newpo.end)
                assert(self.lastgap().start <= newpo.start)
                self._items.append(newpo)
            except ValueError as e:
                raise ValueError("Unable to resize from {1} for object ({0.size}@{0.start})".format(newpo, self.size))
        
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
                    break
            else:
                raise RuntimeError('No exit from space loop.')
                    
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
            
    def lastgap(self):
        """Returns a PlacedObject (possibly of zero size) representing the
        last gap"""
        
        gap = self.last()
        if gap:
            return PlacedObject(None, self.size, 0)
        else:
            return gap
            
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
