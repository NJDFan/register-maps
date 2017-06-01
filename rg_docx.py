import lxml.etree as ET
from lxml.builder import ElementMaker

nsmap = {'w' : 'http://purl.oclc.org/ooxml/wordprocessingml/m'}
E = ElementMaker(namespace = nsmap['w'], nsmap = nsmap)

class Block(object):
	"""Create a slightly smarter tag factory."""
	def __init__(self, tag):
		self.tag = tag
		
	def __call__(self, *args, **kwargs):
		for k, v in kwargs.items():
			if not isinstance(v, basestring):
				kwargs[k] = str(v)

		args = [x for x in args if x is not None]
		return E(self.tag, *args, **kwargs)

class Props(object):
	"""Create a properties tag factory."""
	def __init__(self, tag):
		self.tag = tag

	def __call__(self, *args, **kwargs):
		a = [Block(a)() for a in args]
		a.extend(Block(k)(v) for k, v in kwargs.items())
		return E(self.tag, *a)
		
Paragraph = Block('p')
ParProps = Props('pPr')
Run = Block('r')
RunProps = Props('rPr')
Text = Block('t')

"""

Run = ml('r')

runprops = Run.properties(
	i = None,
	kern = {'val' : 22}
)

yields

<w:rPr>
	<w:i />
	<w:kern val="22" />
</w:rPr>

"""

print ET.tostring(
	E.p(
		E.pPr(
			E.jc(val = 'center')
		),
		E.r(
			E.rPr(
				E.i,
				E.kern(val = '22')
			),
			E.t('Help me')
		)
	)
, pretty_print = True)

print ET.tostring(
	Paragraph(
		ParProps(jc = {'val' : 'center'}),
		Run(
			RunProps('i', kern = {'val' : 22}),
			Text('Help me')
		)
	)
)
