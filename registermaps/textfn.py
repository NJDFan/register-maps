import textwrap

######################################################################
# Text processing utility functions

sampletext = """
SCENE II. Lawn before the Duke's palace.


    Enter CELIA
    and ROSALIND
    
CELIA:
I pray thee, Rosalind, sweet my coz, be merry.

ROSALIND:
Dear Celia, I show more mirth than I am mistress of;
and would you yet I were merrier? Unless you could
teach me to forget a banished father, you must not
learn me how to remember any extraordinary pleasure.

CELIA:
Herein I see thou lovest me not with the full weight
that I love thee. If my uncle, thy banished father,
had banished thy uncle, the duke my father, so thou
hadst been still with me, I could have taught my
love to take thy father for mine: so wouldst thou,
if the truth of thy love to me were so righteously
tempered as mine is to thee.
""".strip()

def deflow(text, whitespace=None):
    """Unwordwrap text.
    
    Consecutive lines with the same amount of leading whitespace will be
    concatenated into a single paragraph.  In a very Python fashion, leading
    whitespace is treated as an indicator of grouping.
    
    Single blank lines are considered to be paragraph breaks, longer runs of
    blank lines lose one line.
    
    Args:
        text: The (probably multiline) text to be deflowed.
        whitespace: If given and not None, a list of characters to be
            considered as leading whitespace.
    
    Yields:
        (ws, text) pairs, where ws is the leading whitespace the paragraph was 
        encountered with and text is one paragraph (which may be blank), 
        without leading whitespace or a trailing newline.
        
    Example:
    
    >>> for ws, graf in deflow(sampletext):
    ...     print(ws, graf[:70], sep='')
    SCENE II. Lawn before the Duke's palace.
    <BLANKLINE>
        Enter CELIA and ROSALIND
    CELIA: I pray thee, Rosalind, sweet my coz, be merry.
    ROSALIND: Dear Celia, I show more mirth than I am mistress of; and wou
    CELIA: Herein I see thou lovest me not with the full weight that I lov
    """
    
    stack = []
    leading = ''
        
    for line in text.splitlines():
        # Always consider blank lines to have no leading whitespace.
        stripped = line.lstrip(whitespace)
        ws = line[:-len(stripped)] if stripped else line
        
        # The line is a continuation if the whitespace levels match and this
        # line is not blank.  Otherwise we should be emitting the previous data.
        if stripped and ws == leading:
            stack.append(stripped)
        else:
            if stack:
                yield (leading, ' '.join(stack))
                
            if stripped:
                # New paragraph at a new indentation level.
                stack = [stripped]
            elif stack:
                # Blank line at the end of a paragraph doesn't count.
                stack.clear()
            else:
                # Consecutive blank lines do count.
                yield(leading, '')
            leading = ws
    
    # Emit the last one.
    if stack:
        yield (leading, ' '.join(stack))

def reflow(text, width=70, whitespace=None, indent=None, intergraf='\n', **kwargs):
    """Reflow a text block, keeping paragraph alignments.
    
    Args:
        text: The (probably multiline) text to be deflowed.
        
        width: The total width of each line
        
        indent: The text, if any, to add to the front of each line.
            Indent is a shorthand for passing the same argument to initial_indent
            and subsequent_indent; if either is provided indent may not be.
            
        whitespace: If given and not None, a list of characters to be
            considered as leading whitespace by break-apart code.
            
        intergraf: The string to use between paragraphs.
        
        **kwargs: As in textwrap.TextWrapper
        
    Example:
        >>> ig = '\\n-\\n'
        >>> print(reflow(sampletext, width=72, indent='+ ', intergraf=ig))
        + SCENE II. Lawn before the Duke's palace.
        -
        + 
        -
        +     Enter CELIA and ROSALIND
        -
        + CELIA: I pray thee, Rosalind, sweet my coz, be merry.
        -
        + ROSALIND: Dear Celia, I show more mirth than I am mistress of; and
        + would you yet I were merrier? Unless you could teach me to forget a
        + banished father, you must not learn me how to remember any
        + extraordinary pleasure.
        -
        + CELIA: Herein I see thou lovest me not with the full weight that I
        + love thee. If my uncle, thy banished father, had banished thy uncle,
        + the duke my father, so thou hadst been still with me, I could have
        + taught my love to take thy father for mine: so wouldst thou, if the
        + truth of thy love to me were so righteously tempered as mine is to
        + thee.


        >>> print(reflow(sampletext, width=72, initial_indent='+ ', subsequent_indent='- '))
        + SCENE II. Lawn before the Duke's palace.
        + 
        +     Enter CELIA and ROSALIND
        + CELIA: I pray thee, Rosalind, sweet my coz, be merry.
        + ROSALIND: Dear Celia, I show more mirth than I am mistress of; and
        - would you yet I were merrier? Unless you could teach me to forget a
        - banished father, you must not learn me how to remember any
        - extraordinary pleasure.
        + CELIA: Herein I see thou lovest me not with the full weight that I
        - love thee. If my uncle, thy banished father, had banished thy uncle,
        - the duke my father, so thou hadst been still with me, I could have
        - taught my love to take thy father for mine: so wouldst thou, if the
        - truth of thy love to me were so righteously tempered as mine is to
        - thee.

    """
    if indent is not None:
        if any(a in kwargs for a in ('initial_indent', 'subsequent_indent')):
            raise ValueError('indent cannot be given with kwargs indent parameters.')
        initial_indent = subsequent_indent = indent
    else:
        initial_indent = kwargs.pop('initial_indent', '')
        subsequent_indent = kwargs.pop('subsequent_indent', '')
    
    #args = {
    #    'expand_tabs' : False,
    #    'replace_whitespace' : False,
    #    'drop_whitespace' : False
    #}
    args = {}
    args.update(kwargs)
    wrapper = textwrap.TextWrapper(width=width, **args)
    
    paragraphs = []
    for ws, graf in deflow(text, whitespace):
        if graf:
            wrapper.initial_indent = initial_indent + ws
            wrapper.subsequent_indent = subsequent_indent + ws
            paragraphs.append(wrapper.fill(graf))
        else:
            paragraphs.append(initial_indent + ws)
    return intergraf.join(paragraphs)

