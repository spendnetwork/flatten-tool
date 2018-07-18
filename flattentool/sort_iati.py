"""
Sorts an IATI XML file according to the schema. This is most useful for 2.0x
where that ordering is required.

Instructions for Ubuntu:
sudo apt-get install python3-lxml
git clone https://github.com/IATI/IATI-Schemas.git
python3 sort_iati.py input_file.xml output_file.xml

Copyright (c) 2013-2014 Ben Webb
Copyright (c) 2016 Open Data Services Co-operative Limited

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
from collections import OrderedDict
from warnings import warn
try:
    import lxml.etree as ET
    # Note that lxml is now "required" - it's listed as a requirement in
    # setup.py and is needed for the tests to pass.
    # However, stdlib etree still exists as an unsupported feature.
except ImportError:
    import xml.etree.ElementTree as ET
    warn('Using stdlib etree may work, but is not supported. Please install lxml.')
import sys

# Namespaces necessary for opening schema files
namespaces = {
    'xsd': 'http://www.w3.org/2001/XMLSchema'
}


class IATISchemaWalker(object):
    """
    Class for converting an IATI XML schema to documentation in the
    reStructuredText format.
    
    Based on the Schema2Doc class in https://github.com/IATI/IATI-Standard-SSOT/blob/version-2.02/gen.py
    """
    def __init__(self, schemas):
        """
        schema -- the filename of the schema to use, e.g.
                  'iati-activities-schema.xsd'
        """
        self.trees = [ET.parse(schema) for schema in schemas]

    def get_schema_element(self, tag_name, name_attribute):
        """
        Return the specified element from the schema.

        tag_name -- the name of the tag in the schema, e.g. 'complexType'
        name_attribute -- the value of the 'name' attribute in the schema, ie.
                          the name of the element/type etc. being described,
                          e.g. iati-activities
        """
        for tree in self.trees:
            schema_element = tree.find("xsd:{0}[@name='{1}']".format(tag_name, name_attribute), namespaces=namespaces)
            if schema_element is not None:
                return schema_element
        return schema_element

    def element_loop(self, element, path):
        """
        Return information about the children of the supplied element.
        """
        a = element.attrib
        type_elements = []
        if 'type' in a:
            complexType = self.get_schema_element('complexType', a['type'])
            if complexType is not None:
                type_elements = ( complexType.findall('xsd:choice/xsd:element', namespaces=namespaces) +
                    complexType.findall('xsd:sequence/xsd:element', namespaces=namespaces) )

        children = ( element.findall('xsd:complexType/xsd:choice/xsd:element', namespaces=namespaces)
            + element.findall('xsd:complexType/xsd:sequence/xsd:element', namespaces=namespaces)
            + element.findall("xsd:complexType/xsd:all/xsd:element", namespaces=namespaces)
            + type_elements)
        child_tuples = []
        for child in children:
            a = child.attrib
            if 'name' in a:
                child_tuples.append((a['name'], child, None, a.get('minOccurs'), a.get('maxOccurs')))
            else:
                child_tuples.append((a['ref'], None, child, a.get('minOccurs'), a.get('maxOccurs')))
        return child_tuples

    def create_schema_dict(self, parent_name, parent_element=None):
        """
        Created a nested OrderedDict representing the sturucture (and order!) of
        element in the IATI schema.
        """
        if parent_element is None:
            parent_element = self.get_schema_element('element', parent_name)

        return OrderedDict([(name, self.create_schema_dict(name, element)) for name, element, _, _, _ in self.element_loop(parent_element, '')])


def sort_iati_element(element, schema_subdict):
    """
    Sort the given elements children according to the order of schema_subdict.
    """
    children = list(element)
    for child in children:
        element.remove(child)
    keys = list(schema_subdict.keys())

    def index_key(x):
        if x.tag in keys:
            return keys.index(x.tag)
        else:
            return len(keys) + 1

    for child in sorted(children, key=index_key):
        element.append(child)
        sort_iati_element(child, schema_subdict.get(child.tag, {}))


def sort_iati_xml_file(input_file, output_file, schemas):
    """
    Sort an IATI XML file according to the schema.
    """
    schema_dict = IATISchemaWalker(schemas).create_schema_dict('iati-activity')
    tree = ET.parse(input_file)
    root = tree.getroot()

    for element in root:
        sort_iati_element(element, schema_dict)

    with open(output_file, 'wb') as fp:
        tree.write(fp, encoding='utf-8')


if __name__ == '__main__':
    if len(sys.argv) <= 3:
        print('Usage: python3 sort_iati.py input_file.xml output_file.xml schema.xsd')
    else:
        sort_iati_xml_file(sys.argv[1], sys.argv[2], sys.argv[3:])
