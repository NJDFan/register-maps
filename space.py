#!/usr/bin/env python
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

import bisect

def clp2(x):
    """Find the lowest number which is a whole power of 2 that is >= x."""
    if (x < 1):
        return 0
    
    y = 1
    while (y < x):
        y = y * 2
        
    return y
    
class _Error(Exception):
    def __init__(self, text):
        self.text = text
    def __str__(self):
        return self.text

class InsufficientSpaceError(_Error):
    """Raised to indicate that no space could be found for an object
    with no defined position.
    """
    
    def __init__(self, text, attempt):
        self.attempt = attempt
        super(InsufficientSpaceError, self).__init__(text)
       
class OutOfBoundsError(_Error):
    """Raised to indicate that the fixed location requested for the
    object was outside the range of the space, or that the fixed
    location plus the size would be outside the range of the space.
    
    Contains the field attempt, a PlacedObject representing the object
    that was trying to be placed.
    """
    
    def __init__(self, text, attempt):
        self.attempt = attempt
        super(OutOfBoundsError, self).__init__(text)
    
class BlockedSpaceError(_Error):
    """
    Raised to indicate that one object could not be placed at a fixed
    location in the space because another was already there.
    
    Contains two fields, attempt and blocking.  Both are PlacedObjects
    representing respectively the object that was trying to be placed
    and the object that prevented it.
    """
    
    def __init__(self, text, attempt, blocking):
        self.attempt = attempt
        self.blocking = blocking
        super(BlockedSpaceError, self).__init__(text)
        
class PlacedObject:
    """
    Represents an object as placed in the Space.
    
    PlacedObjects are seed only when iterating over the Space.
    
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
        
    def __nonzero__(self):
        return bool(self.obj)

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
            
