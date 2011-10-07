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
from oerpub.rhaptoslabs import sword2cnx
from rhaptos.cnxmlutils import odt2cnxml
from lxml import etree

TEST = True
TEST_TYPE = "Office" # "Office", "CNXML"
TEST_OFFICE_FILE = "../../../test/test.odt"

# Get the user's credentials
if TEST:
    username = 'user1'
    password = 'user1'
else:
    username = raw_input("Enter Connexions username: ")
    password = raw_input("Enter Connexions password: ")

# Retrieve service document
serviceDocumentUrl = "http://50.57.120.10:8080/rhaptos/sword/servicedocument"
if not TEST:
    response = raw_input('Service document URL [%s]: '%serviceDocumentUrl).strip()
    if response != '':
        serviceDocumentUrl = response

print 'Retrieving service document...'
conn = sword2cnx.Connection(serviceDocumentUrl,
                            user_name = username,
                            user_pass = password,
                            error_response_raises_exceptions=False)

# Choose a work area (personal or shared workspace)
swordCollections = sword2cnx.get_workspaces(conn)
print 'Deposit location:'
for i in range(len(swordCollections)):
    print ' %i. %s (%s)'%(i+1, swordCollections[i].title,
                          swordCollections[i].href)
if TEST:
    collectionSelect = None
    for i in range(len(swordCollections)):
        if swordCollections[i].title.lower() == 'personal workspace':
            collectionSelect = i
            break
    if collectionSelect is None:
        raise ValueError, "Personal workspace not found"
else:
    collectionSelect = int(raw_input().strip())-1

# Collect metadata about the new module
if TEST:
    metadata = {
        'dcterms:title': 'Test %s upload'%TEST_TYPE,
        'dcterms:abstract': 'Test upload module summary',
        'dcterms:language': 'en',
        'oerdc:oer-subject': ['Arts', 'Humanities'],
        'dcterms:subject': ['keyword 1','keyword 2','keyword 3'],
        'oerdc:analyticsCode': '',
        'oerdc:descriptionOfChanges': 'Uploaded from external document importer.',
    }

    # Role metadata is treated slightly differently in that the user
    # id for each role is provided in the oerdc:id attribute rather
    # than the text of the tag.
    roleMetadata = {
        'dcterms:creator': username,
        'oerdc:maintainer': 'admin',
        'dcterms:rightsHolder': username,
        'oerdc:translator': username,
        'oerdc:editor': [username, 'admin'],
    }
else:
    print "New document metadata:"
    metadata = {}
    # Title
    default = "Uploaded module"
    metadata['dcterms:title'] = raw_input("  Title [%s]: "%default).strip()
    if metadata['dcterms:title'] == '':
        metadata['dcterms:title'] = default
    # Summary
    metadata['dcterms:abstract'] = raw_input("  Summary: ").strip()
    # Language
    metadata['dcterms:language'] = raw_input("  Language code [en]: ").strip()
    # Subjects
    subjects = ["Arts",	"Business", "Humanities", "Mathematics and Statistics", "Science and Technology", "Social Sciences"]
    print "  Add subjects from this list:"
    for i in range(len(subjects)):
        print "   %i. %s"%(i+1, subjects[i])
    metadata['oerdc:oer-subject'] = set([])
    while True:
        index = raw_input("  ").strip()
        if index == '':
            break
        index = [int(_.strip())-1 for _ in index.split(',')]
        metadata['oerdc:oer-subject'].update(index)
    metadata['oerdc:oer-subject'] = [subjects[i] for i in metadata['oerdc:oer-subject']]
    # Keywords
    metadata['dcterms:subject'] = []
    while True:
        keyword = raw_input("  Add a keyword: ").strip()
        if keyword == '':
            break
        metadata['dcterms:subject'].append(keyword)
    # Google Analytics code
    metadata['oerdc:analyticsCode'] = raw_input("  Google Analytics code: ").strip()

    roleMetadata = {
        'dcterms:creator': username,
        'dcterms:rightsHolder': username,
        'oerdc:maintainer': username,
    }
    print 'TODO: ask for additional account ids for contributors (authors, licensors, maintainers, translators, editors)'
    #  o ask for additional account ids for contributors (authors,
    #    licensors, maintainers, translators, editors)

    metadata['oerdc:descriptionOfChanges'] = 'Uploaded from external document importer.'

# Build metadata entry object
keys = metadata.keys()
for key in keys:
    if metadata[key] == '':
        del metadata[key]
metadataEntry = sword2cnx.MetaData(metadata)

# Add role tags
for key, value in roleMetadata.iteritems():
    if not isinstance(value, list):
        value = [value]
    for v in value:
        v = v.strip()
        if v != '':
            metadataEntry.add_field(key, '', {'oerdc:id': v})

print "Type of file to upload:"
print " 1. Office document"
print " 2. CNXML file"
print " 3. Zip package"
if TEST:
    if TEST_TYPE == "CNXML":
        uploadType = 2
        uploadFilename = "../../../test/test.cnxml"
    elif TEST_TYPE == "Office":
        uploadType = 1
        uploadFilename = TEST_OFFICE_FILE
else:
    uploadType = int(raw_input("").strip())
    uploadFilename = raw_input("Path to the %s file: "%(["Office", "CNXML", "Zip"][uploadType-1]))

def escape_system(string):
    return '"' + string.replace('\\', '\\\\').replace('"', '\\"') + '"'

def office_to_cnxml(pathToOfficeFile, verbose=True):
    import os

    # Get absolute path to file
    inputFilename = os.path.abspath(pathToOfficeFile)

    # Convert to ODT if necessary
    if inputFilename[inputFilename.rfind('.'):].lower() != '.odt':
        odtFilename = '/tmp/temp.odt'
        command = '/usr/bin/soffice "macro:///Standard.Module1.SaveAsOOO(' + escape_system(inputFilename)[1:-1] + ',' + odtFilename + ')"'
        os.system(command)
        inputFilename = odtFilename

    # Convert to CNXML
    xml, files, errors = odt2cnxml.transform(inputFilename)
    return etree.tostring(xml), files


if uploadType in [1, 2]:
    if uploadType == 1:
        # Convert the author's Word processing document (.doc, .odt) to CNXML
        print 'Converting Office document to CNXML...'
        uploadCnxml, uploadFiles = office_to_cnxml(uploadFilename)
    else:
        with open(uploadFilename, 'rt') as fp:
            uploadCnxml = fp.read().decode('latin-1')
        uploadFiles = {}

    # Package index.cnxml and other files into zip
    import zipfile
    from StringIO import StringIO
    zipFile = StringIO('')
    zipArchive = zipfile.ZipFile(zipFile, "w")
    zipArchive.writestr('index.cnxml', uploadCnxml.encode('utf8'))
    for filename, content in uploadFiles.iteritems():
        zipArchive.writestr(filename, content)
    zipArchive.close()
    zipFile.seek(0)
elif uploadType == 3:
    zipFile = open(uploadFilename, "rb")
else:
    raise ValueError, "Unknown upload type"

# Preview the module
if TEST:
    preview = False
else:
    preview = raw_input("Would you like to preview the module in your browser? [n] ").strip().lower()
    preview = (preview == 'y')

if preview:
    print "TODO: preview the module"

# Upload module through SWORD2 API
print 'Uploading...'
# POST a Multipart Deposit with Header In-Progress="true" (since the
# license hasn't been signed) and an Atom Entry and an attached Zip
# Document to Col-IRI. Set the Package to SimpleZip.
depositReceipt = conn.create(
    col_iri = swordCollections[collectionSelect].href,
    metadata_entry = metadataEntry,
    payload = zipFile,
    filename = 'upload.zip',
    mimetype = 'application/zip',
    packaging = 'http://purl.org/net/sword/package/SimpleZip',
    in_progress = True)

"""
# Alternative non-multipart deposit.
depositReceipt = conn.create(
    col_iri = swordCollections[collectionSelect].href,
    metadata_entry = metadataEntry,
    in_progress = True)
conn.update_files_for_resource(
    payload = zipFile,
    filename = 'upload.zip',
    mimetype = 'application/zip',
    packaging = 'http://purl.org/net/sword/package/SimpleZip',
    in_progress = True,
    dr = depositReceipt)
"""

zipFile.close()

# Show the author the sword:treatment element from the Deposit Receipt
# so that they can click on the preview and click on and sign the
# license.
print depositReceipt.treatment

# Show the author a link to edit the module on Connexions in case
# their are any changes they want to make at Connexions. Get this from
# the derivedResource, URL to edit on Connexions.
print "If you need to edit on Connexions before publishing, click here:"
links = depositReceipt.links['http://purl.org/net/sword/terms/derivedResource']
links.sort(lambda a,b: cmp(len(a['href']), len(b['href'])))
shortestLink = links[0]
print ' ', shortestLink['href']

raw_input("WAITING...")

# Trigger a publish of the module. POST to the SE-IRI with
# "In-Progress" set to false.
publishedDepositReceipt = conn.complete_deposit(dr = depositReceipt)

print 'Done!'
