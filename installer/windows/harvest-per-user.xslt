<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:w="http://schemas.microsoft.com/wix/2006/wi">
  <xsl:output method="xml" indent="yes" />
  <xsl:template match="@*|node()">
    <xsl:copy><xsl:apply-templates select="@*|node()" /></xsl:copy>
  </xsl:template>
  <!-- Per-user MSI components need HKCU key paths and folder cleanup. -->
  <xsl:template match="w:Component">
    <xsl:variable name="componentId" select="@Id" />
    <xsl:copy>
      <xsl:apply-templates select="@*|node()" />
      <w:RegistryValue Root="HKCU" Key="Software\still-standing88\Photon Snapshot\Components"
                       Name="{@Id}" Type="integer" Value="1" KeyPath="yes" />
      <w:RemoveFolder Id="remove_{@Id}" Directory="{../@Id}" On="uninstall" />
      <xsl:for-each select="ancestor::w:Directory[@Id != current()/../@Id]">
        <w:RemoveFolder Id="ancestor_{position()}_{$componentId}" Directory="{@Id}" On="uninstall" />
      </xsl:for-each>
    </xsl:copy>
  </xsl:template>
  <xsl:template match="w:File/@KeyPath">
    <xsl:attribute name="KeyPath">no</xsl:attribute>
  </xsl:template>
</xsl:stylesheet>
