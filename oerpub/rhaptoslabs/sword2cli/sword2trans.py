# encoding: utf-8
"""
Author: Carl Scheffler
Copyright (C) 2011 Katherine Fletcher.

Funding was provided by The Shuttleworth Foundation as part of the OER
Roadmap Project.

If the license this software is distributed under is not suitable for
your purposes, you may contact the copyright holder through
oer-roadmap-discuss@googlegroups.com to discuss different licensing
terms.

This file is part of oerpub.rhaptoslabs.sword2cli

Sword2CLI is free software: you can redistribute it and/or modify it
under the terms of the GNU Lesser General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Sword2CLI is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with Sword1Cnx.  If not, see <http://www.gnu.org/licenses/>.
"""
from __future__ import division
import sys
import sword2cnx
from lxml import etree

# Get the user's credentials
username = 'user1'
password = 'user1'

# Retrieve service document
serviceDocumentUrl = "http://50.57.120.10:8080/rhaptos/sword/servicedocument"
conn = sword2cnx.Connection(serviceDocumentUrl,
                            user_name = username,
                            user_pass = password)

# Choose a work area (personal or shared workspace)
swordCollections = sword2cnx.get_workspaces(conn)
colId = None
for i in range(len(swordCollections)):
    if swordCollections[i].title == 'Personal Workspace':
        colId = i
        break
if colId is None:
    raise ValueError, "Personal workspace not found"

# Ask for the module id or url to translate
sourceDocumentUrlPrefix = "http://50.57.120.10:8080/rhaptos/content/"
sourceDocumentId = "m10107"
sourceDocumentUrl = sourceDocumentUrlPrefix + sourceDocumentId

# Ask for target language
targetLanguage = "af"

# Using the chosen work area, do a POST to instantiate the new
# editable version
metadataEntry = sword2cnx.MetaData({'dcterms:source': sourceDocumentUrl})
derivationDepositReceipt = conn.create(
    col_iri = swordCollections[colId].href,
    metadata_entry = metadataEntry,
    in_progress = True)
print "=== DEPOSIT RECEIPT ==="
print derivationDepositReceipt
print "=== /DEPOSIT RECEIPT ==="

# Do auto-translate of CNXML through Google Translate
import GoogleTranslate
sourceCnxml = GoogleTranslate.module_to_cnxml(sourceDocumentId, iUrlPrefix=sourceDocumentUrlPrefix)
version = GoogleTranslate.get_cnxml_version(sourceCnxml)
sourceLanguage = GoogleTranslate.get_cnxml_language(sourceCnxml)
url = sourceDocumentUrlPrefix + sourceDocumentId + '/' + version + '/module_export?format=plain'
print "Translating from %s to %s..."%(sourceLanguage, targetLanguage)
targetCnxml = GoogleTranslate.translate_cnxml(url, sourceLanguage, targetLanguage)
targetCnxml = GoogleTranslate.fix_cnxml_translation(sourceCnxml, targetCnxml)

with open('source.cnxml','wt') as fp:
    fp.write(sourceCnxml)
with open('target.cnxml','wt') as fp:
    fp.write(targetCnxml)

sourceCnxml = sourceCnxml.decode('latin-1')
targetCnxml = targetCnxml.decode('latin-1')

# TODO
# Present the sword:treatment to the user so they go and sign the
# license. Show the user what the authoring roles will look like and
# perhaps build in functionality to help them get this the way they
# want it. For instance, for translation sprints, it might be common
# to include the original authors on the module also.
print derivationDepositReceipt.treatment

# Ask for a Google Analytics code if the user has one.
googleAnalyticsCode = None

# Set metadata
metadataFields = [
    'dcterms:title',
    'dcterms:abstract',
    'dcterms:language',
    #'dcterms:subject',                           # Special case that cannot be
    #'dcterms:subject xsi:type="oerdc:Subjects"', # handled by the sword2 library
    'oerdc:descriptionOfChanges',
    'oerdc:analyticsCode',
    'oerdc:subject',
    #'dcterms:creator',       # Updating of roles
    #'oerdc:maintainer',      # through SWORD2
    #'dcterms:rightsHolder',  # is still broken
    #'oerdc:translator',
    #'oerdc:editor',
]
metadata = {}

# Setup defaults from deposit receipt of derivation
for entry in metadataFields:
    metadata[entry] = derivationDepositReceipt.metadata.get(entry.replace(':','_'), '').strip()
metadata['dcterms:language'] = targetLanguage

# Handle dcterms:subject special case by traversing the deposit
# receipt DOM
metadata['dcterms:subject'] = []
dcTermsSubjectOerPub = None

dom = derivationDepositReceipt.dom
prefix = sword2cnx.NS['dcterms'] % ""
oerPubAttrib = {sword2cnx.NS['xsi']%'type': 'oerdc:Subject'}
for e in dom.getchildren():
    if str(e.tag).startswith(prefix):
        _, tagname = e.tag.rsplit("}", 1)
        if tagname == "subject":
            if e.attrib == oerPubAttrib:
                dcTermsSubjectOerPub = e.text.strip()
            else:
                metadata['dcterms:subject'].append(e.text.strip())

# Find values for all translated metadata
keywordList = []
dom = etree.fromstring(targetCnxml)
for e in dom.getchildren():
    if e.tag == '{http://cnx.rice.edu/cnxml}metadata':
        for e in e.getchildren():
            if e.tag == '{http://cnx.rice.edu/mdml}title':
                metadata['dcterms:title'] = e.text.strip()
            elif e.tag == '{http://cnx.rice.edu/mdml}abstract':
                metadata['dcterms:abstract'] = e.text.strip()
            elif e.tag == '{http://cnx.rice.edu/mdml}keywordlist':
                for e in e.getchildren():
                    if e.tag == '{http://cnx.rice.edu/mdml}keyword':
                        keywordList.append(e.text.strip())
        break
if keywordList != '':
    metadata['dcterms:subject'] = keywordList

# Update metadata
keys = metadata.keys()
for key in keys:
    if metadata[key] == '':
        del metadata[key]
metadataEntry = sword2cnx.MetaData(metadata)
if dcTermsSubjectOerPub is not None:
    metadataEntry.add_field('dcterms_subject', dcTermsSubjectOerPub, oerPubAttrib)
    #metadataEntry.add_field('oerdc_subject', dcTermsSubjectOerPub)
print '=== METADATA ==='
print metadataEntry
print '=== /METADATA ==='
metadataDepositReceipt = conn.update_metadata_for_resource(
    metadataEntry,
    dr = derivationDepositReceipt,
    in_progress = True)

# Update the contents using a multipart PUT that has both an Atom
# Entry to fix up the metadata and the new translated CNXML attached.
import zipfile
from StringIO import StringIO

zipFile = StringIO('')
zipArchive = zipfile.ZipFile(zipFile, "w")
zipArchive.writestr('index.cnxml', targetCnxml.encode('utf8'))
zipArchive.close()
zipFile.seek(0)

updateDepositReceipt = conn.update_files_for_resource(
    payload = zipFile,
    filename = 'update.zip',
    mimetype = 'application/zip',
    packaging = 'http://purl.org/net/sword/package/SimpleZip',
    in_progress = True,
    dr = derivationDepositReceipt,
    additional_headers = {'Update-Semantics': 'http://purl.org/oerpub/semantics/Merge'})

print 'Done!'
