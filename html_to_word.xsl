<?xml version="1.0" encoding="iso-8859-1"?>
<xsl:stylesheet version="1.0"
xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
xmlns:w="http://schemas.microsoft.com/office/word/2003/wordml">

<!-- Stylesheet parameters -->
<xsl:output method="xml" />
<xsl:strip-space elements="*" />
	
<!-- Root node processing -->
<xsl:template match="/">
	<xsl:processing-instruction name="mso-application">progid="Word.Document"</xsl:processing-instruction>
	<w:wordDocument xmlns:w="http://schemas.microsoft.com/office/word/2003/wordml">
		<w:docPr>
			<w:linkStyles val="on" />
		</w:docPr>
		<w:body>
			<xsl:apply-templates select="html/body" />
		</w:body>
	</w:wordDocument>
</xsl:template>

<!-- Interpret headings and top-level paragraphs as styles -->
<xsl:template match="body/h1 | div/h1">
	<w:p>
		<w:pPr><w:pStyle w:val="Heading1" /></w:pPr>
		<w:r><w:t>
			<xsl:value-of select="." />
		</w:t></w:r>
	</w:p>
</xsl:template>

<xsl:template match="body/h2 | div/h2">
	<w:p>
		<w:pPr><w:pStyle w:val="Heading2" /></w:pPr>
		<w:r><w:t>
			<xsl:value-of select="." />
		</w:t></w:r>
	</w:p>
</xsl:template>

<xsl:template match="body/h3 | div/h3">
	<w:p>
		<w:pPr><w:pStyle w:val="Heading3" /></w:pPr>
		<w:r><w:t>
			<xsl:value-of select="." />
		</w:t></w:r>
	</w:p>
</xsl:template>

<xsl:template match="body/p | div/p">
	<w:p>
		<w:pPr><w:pStyle w:val="BodyText" /></w:pPr>
		<w:r><w:t>
			<xsl:value-of select="." />
		</w:t></w:r>
	</w:p>
</xsl:template>

<!-- Building memory map tables is easy -->

<xsl:template match="table[@class='component_list']">
	<w:tbl>
		<w:tblPr>
			<w:tblStyle w:val="CodingTable" />
			<w:tblLook w:val="000001E0" />
		</w:tblPr>
		<w:tblGrid>
			<w:gridCol /><w:gridCol /><w:gridCol />
		</w:tblGrid>
		
		<!-- Header row -->
		<w:tr>
			<w:trPr>
				<w:tblHeader val="on" />
			</w:trPr>
			<xsl:for-each select="tr/th">
				<w:tc>
					<w:p><w:r><w:t><xsl:value-of select="." />
					</w:t></w:r></w:p>
				</w:tc>
			</xsl:for-each>
		</w:tr>
		
		<!-- Data rows -->
		<xsl:for-each select="tr[td]">
			<w:tr>
				<w:trPr>
					<w:tblHeader val="off" />
				</w:trPr>
				<xsl:for-each select="td">
					<w:tc>
						<w:p><w:r><w:t><xsl:value-of select="." />
						</w:t></w:r></w:p>
					</w:tc>
				</xsl:for-each>
			</w:tr>
		</xsl:for-each>
	</w:tbl>
</xsl:template>

<!-- Building bitfield tables is a bit more work -->

<xsl:template match="table[@class='bitfield']">
	<w:tbl>
		<w:tblPr>
			<w:tblStyle w:val="Bitfield" />
			<w:tblLook w:val="000001E0" />
		</w:tblPr>
		<w:tblGrid>
			<!-- Bitfield has 16 columns -->
			<w:gridCol /><w:gridCol /><w:gridCol /><w:gridCol />
			<w:gridCol /><w:gridCol /><w:gridCol /><w:gridCol />
			<w:gridCol /><w:gridCol /><w:gridCol /><w:gridCol />
			<w:gridCol /><w:gridCol /><w:gridCol /><w:gridCol />
		</w:tblGrid>
		
		<!-- Create the rows -->
		<xsl:apply-templates mode="bitfield" />
		
	</w:tbl>

</xsl:template>

<xsl:template match="tr[@class = 'bit_numbers']" mode="bitfield">
	<w:tr>
		<xsl:for-each select="td">
			<w:tc><w:p><w:r><w:t><xsl:value-of select="." /></w:t></w:r></w:p></w:tc>
		</xsl:for-each>
	</w:tr>
</xsl:template>

<xsl:template match="tr[@class = 'fields']" mode="bitfield">
	<w:tr>
		<xsl:for-each select="td">
			<w:tc>
				<w:tcPr>
					<xsl:if test="@colspan">
						<w:gridSpan>
							<xsl:attribute name="w:val">
								<xsl:value-of select="@colspan" />
							</xsl:attribute>
						</w:gridSpan>
					</xsl:if>
				</w:tcPr>
				<w:p><w:r><w:t><xsl:value-of select="." /></w:t></w:r></w:p>
			</w:tc>
		</xsl:for-each>
	</w:tr>
</xsl:template>

<!--
<xsl:template match="td[@colspan]" mode="bitfield_fields">
	<w:tc>
		<w:tcPr>
			<w:hmerge val="restart"/>
		</w:tcPr>
		<w:p><w:r><w:t><xsl:value-of select="." /></w:t></w:r></w:p>
	</w:tc>
	<xsl:call-template name="hmerged_cells">
		<xsl:with-param name="count" select="@colspan - 1" />
	</xsl:call-template>
</xsl:template>

<xsl:template match="td[not(@colspan)]" mode="bitfield_fields">
	<w:tc>
		<w:p><w:r><w:t><xsl:value-of select="." /></w:t></w:r></w:p>
	</w:tc>
</xsl:template>

<xsl:template name="hmerged_cells">
	<xsl:param name="count" />

	<xsl:if test="$count &gt; 0">
		<w:tc><w:tcPr><w:hmerge /></w:tcPr><w:p /></w:tc><xsl:comment>Count = <xsl:value-of select="$count" /></xsl:comment>
		<xsl:call-template name="hmerged_cells">
			<xsl:with-param name="count" select="$count - 1"/>
		</xsl:call-template>
	</xsl:if>
</xsl:template>

-->

<!-- Supress anything we're explicitly asked to with a HUGE priority -->
<xsl:template match="*[boolean(@hide_word)]" priority="10" />

<!-- Suppress all text nodes by default -->
<xsl:template match="text()" />

</xsl:stylesheet>
