from __future__ import print_function
from __future__ import unicode_literals
import sys
from decimal import Decimal, InvalidOperation
import os
from collections import OrderedDict
import openpyxl
from six import text_type
from warnings import warn
import traceback
import datetime
import pytz

# The "pylint: disable" lines exist to ignore warnings about the imports we expect not to work not working

if sys.version > '3':
    from csv import DictReader
else:
    from unicodecsv import DictReader  # pylint: disable=F0401

try:
    from collections import UserDict  # pylint: disable=E0611
except ImportError:
    from UserDict import UserDict  # pylint: disable=F0401


class SpreadsheetInput(object):
    def convert_dict_titles(self, dicts, titles):
        titles = titles or {}
        for d in dicts:
            yield { (titles[k] if k in titles else (k if '/' in k else k.replace(':','/'))):v for k,v in d.items() }

    def __init__(self, input_name='', main_sheet_name='', timezone_name='UTC', root_id='ocid', convert_titles=False):
        self.input_name = input_name
        self.main_sheet_name = main_sheet_name
        self.sub_sheet_names = []
        self.timezone = pytz.timezone(timezone_name)
        self.root_id = root_id
        self.convert_titles = convert_titles

    def get_main_sheet_lines(self):
        if self.convert_titles:
            return self.convert_dict_titles(self.get_sheet_lines(self.main_sheet_name), self.parser.main_sheet.titles)
        else:
            return self.get_sheet_lines(self.main_sheet_name)

    def get_sub_sheets_lines(self):
        for sub_sheet_name in self.sub_sheet_names:
            if self.convert_titles:
                yield sub_sheet_name, self.convert_dict_titles(self.get_sheet_lines(sub_sheet_name), self.parser.sub_sheets[sub_sheet_name].titles if sub_sheet_name in self.parser.sub_sheets else None)
            else:
                yield sub_sheet_name, self.get_sheet_lines(sub_sheet_name)

    def get_sheet_lines(self, sheet_name):
        raise NotImplementedError

    def read_sheets(self):
        raise NotImplementedError

    def convert_type(self, type_string, value):
        if value == '' or value is None:
            return None
        if type_string == 'number':
            try:
                return Decimal(value)
            except (TypeError, ValueError, InvalidOperation):
                warn('Non-numeric value "{}" found in number column, returning as string instead.'.format(value))
                return text_type(value)
        elif type_string == 'integer':
            try:
                return int(value)
            except (TypeError, ValueError):
                warn('Non-integer value "{}" found in integer column, returning as string instead.'.format(value))
                return text_type(value)
        elif type_string == 'boolean':
            value = text_type(value)
            if value.lower() in ['true', '1']:
                return True
            elif value.lower() in ['false', '0']:
                return False
            else:
                warn('Unrecognised value for boolean: "{}", returning as string instead'.format(value))
                return text_type(value)
        elif type_string == 'array':
            value = text_type(value)
            if ',' in value:
                return [x.split(',') for x in value.split(';')]
            else:
                return value.split(';')
        elif type_string == 'string':
            if type(value) == datetime.datetime:
                return self.timezone.localize(value).isoformat()
            return text_type(value)
        elif type_string == '':
            if type(value) == datetime.datetime:
                return self.timezone.localize(value).isoformat()
            return value if type(value) in [int] else text_type(value)
        else:
            raise ValueError('Unrecognised type: "{}"'.format(type_string))


    def convert_types(self, in_dict):
        out_dict = OrderedDict()
        for key, value in in_dict.items():
            parts = key.split(':')
            if len(parts) > 1:
                out_dict[parts[0]] = self.convert_type(parts[1], value)
            else:
                out_dict[parts[0]] = self.convert_type('', value)
        return out_dict


    def unflatten(self):
        main_sheet_by_ocid = OrderedDict()
        for line in self.get_main_sheet_lines():
            if all(x == '' for x in line.values()):
                continue
            root_id_or_none = line[self.root_id] if self.root_id else None
            if root_id_or_none not in main_sheet_by_ocid:
                main_sheet_by_ocid[root_id_or_none] = TemporaryDict('id')
            main_sheet_by_ocid[root_id_or_none].append(unflatten_line(self.convert_types(line)))

        for sheet_name, lines in self.get_sub_sheets_lines():
            for i, line in enumerate(lines):
                line_number = i+2
                try:
                    if all(x == '' for x in line.values()):
                        continue
                    id_fields = {k: v for k, v in line.items() if
                                 k.split(':')[0].endswith('/id') and
                                 k.startswith(self.main_sheet_name)}
                    line_without_id_fields = OrderedDict(
                        (k, v) for k, v in line.items()
                        if k not in id_fields and (not k or k != self.root_id))
                    raw_id_fields_with_values = {k.split(':')[0]: v for k, v in id_fields.items() if v}
                    if not raw_id_fields_with_values:
                        warn('Line {} of sheet {} has no parent id fields populated,'
                             'skipping.'.format(line_number, sheet_name))
                        continue
                    sheet_context_names = {k.split(':')[0]: k.split(':')[1] if len(k.split(':')) > 1 else None
                                           for k, v in id_fields.items() if v}

                    try:
                        id_field = find_deepest_id_field(raw_id_fields_with_values)
                    except ConflictingIDFieldsError:
                        warn('Multiple conflicting ID fields have been filled in on line {} of sheet {},'
                             'skipping that line.'.format(line_number, sheet_name))
                        continue

                    try:
                        context = path_search(
                            {self.main_sheet_name: main_sheet_by_ocid[line[self.root_id] if self.root_id else None]},
                            id_field.split('/')[:-1],
                            id_fields=raw_id_fields_with_values,
                            top=True
                        )
                    except IDFieldMissing as e:
                        warn('The parent id field "{}" was expected, but not present on line {} of sheet {}.'.format(
                            e.args[0], line_number, sheet_name))
                        continue

                    sheet_context_name = sheet_context_names[id_field] or sheet_name
                    # Added the following line to support the usecase in test_nested_sub_sheet
                    context = path_search(context, sheet_context_name.split('/')[:-1])
                    unflattened = unflatten_line(self.convert_types(line_without_id_fields))
                    sheet_context_base_name = sheet_context_name.split('/')[-1]
                    if sheet_context_base_name not in context:
                        context[sheet_context_base_name] = TemporaryDict(keyfield='id')
                    elif context[sheet_context_base_name].top_sheet:
                        # Overwirte any rolled up data from the main sheet
                        print(context[sheet_context_base_name].data, unflattened)
                        if context[sheet_context_base_name].data.get(None) != unflattened:
                            warn('Conflict between main sheet and sub sheet {}, using values from sub sheet'.format(sheet_context_base_name))
                        context[sheet_context_base_name] = TemporaryDict(keyfield='id')
                    context[sheet_context_base_name].append(unflattened)
                except Exception as e:  # pylint: disable=W0703
                    # Deliberately catch all exceptions for a line, so that
                    # all lines without exceptions will still be processed.
                    print('An error occured whilst parsing line {} of sheet {}"'.format(line_number, sheet_name))
                    traceback.print_exc()
                    sys.exit()

        temporarydicts_to_lists(main_sheet_by_ocid)

        return sum(main_sheet_by_ocid.values(), [])


class CSVInput(SpreadsheetInput):
    encoding = 'utf-8'

    def read_sheets(self):
        sheet_file_names = os.listdir(self.input_name)
        if self.main_sheet_name+'.csv' not in sheet_file_names:
            raise ValueError('Main sheet "{}.csv" not found.'.format(self.main_sheet_name))
        sheet_file_names.remove(self.main_sheet_name+'.csv')

        self.sub_sheet_names = sorted([fname[:-4] for fname in sheet_file_names if fname.endswith('.csv')])

    def get_sheet_lines(self, sheet_name):
        if sys.version > '3':  # If Python 3 or greater
            # Pass the encoding to the open function
            with open(os.path.join(self.input_name, sheet_name+'.csv'), encoding=self.encoding) as main_sheet_file:
                dictreader = DictReader(main_sheet_file)
                for line in dictreader:
                    yield OrderedDict((fieldname, line[fieldname]) for fieldname in dictreader.fieldnames)
        else:  # If Python 2
            # Pass the encoding to DictReader
            with open(os.path.join(self.input_name, sheet_name+'.csv')) as main_sheet_file:
                dictreader = DictReader(main_sheet_file, encoding=self.encoding)
                for line in dictreader:
                    yield OrderedDict((fieldname, line[fieldname]) for fieldname in dictreader.fieldnames)


class CSVInputStringIODict(SpreadsheetInput):
    encoding = 'utf-8'

    def read_sheets(self):
        sheet_file_names = self.input_name.keys()
        if self.main_sheet_name+'.csv' not in sheet_file_names:
            raise ValueError('Main sheet "{}.csv" not found.'.format(self.main_sheet_name))
        sheet_file_names.remove(self.main_sheet_name+'.csv')

        self.sub_sheet_names = sorted([fname[:-4] for fname in sheet_file_names if fname.endswith('.csv')])

    def get_sheet_lines(self, sheet_name):
        inputObject = self.input_name[sheet_name+'.csv']
        inputObject.seek(0)

        if sys.version > '3':  # If Python 3 or greater
            # Pass the encoding to the open function
                dictreader = DictReader(inputObject)
                for line in dictreader:
                    yield OrderedDict((fieldname, line[fieldname]) for fieldname in dictreader.fieldnames)
        else:  # If Python 2
            # Pass the encoding to DictReader
            dictreader = DictReader(inputObject, encoding=self.encoding)
            for line in dictreader:
                yield OrderedDict((fieldname, line[fieldname]) for fieldname in dictreader.fieldnames)


class XLSXInput(SpreadsheetInput):
    def read_sheets(self):
        self.workbook = openpyxl.load_workbook(self.input_name, data_only=True)
        sheet_names = self.workbook.get_sheet_names()
        if self.main_sheet_name not in sheet_names:
            raise ValueError('Main sheet "{}" not found in workbook.'.format(self.main_sheet_name))
        sheet_names.remove(self.main_sheet_name)
        self.sub_sheet_names = sheet_names

    def get_sheet_lines(self, sheet_name):
        worksheet = self.workbook[sheet_name]
        header_row = worksheet.rows[0]
        remaining_rows = worksheet.rows[1:]
        coli_to_header = ({i: x.value for i, x in enumerate(header_row) if x.value is not None})
        for row in remaining_rows:
            yield OrderedDict((coli_to_header[i], x.value) for i, x in enumerate(row) if i in coli_to_header)


FORMATS = {
    'xlsx': XLSXInput,
    'csv': CSVInput,
    'csvDict': CSVInputStringIODict,
}


def unflatten_line(line):
    unflattened = OrderedDict()
    for k, v in line.items():
        if v is None:
            continue
        fields = k.split('/')
        path_search(unflattened, fields[:-1], top_sheet=True)[fields[-1]] = v
    return unflattened


class IDFieldMissing(KeyError):
    pass


def path_search(nested_dict, path_list, id_fields=None, path=None, top=False, top_sheet=False):
    if not path_list:
        return nested_dict

    id_fields = id_fields or {}
    parent_field = path_list[0]
    path = parent_field if path is None else path+'/'+parent_field

    if parent_field.endswith('[]') or top:
        if parent_field.endswith('[]'):
            parent_field = parent_field[:-2]
        if parent_field not in nested_dict:
            nested_dict[parent_field] = TemporaryDict(keyfield='id', top_sheet=top_sheet)
        sub_sheet_id = id_fields.get(path+'/id')
        if sub_sheet_id not in nested_dict[parent_field]:
            nested_dict[parent_field][sub_sheet_id] = {}
        return path_search(nested_dict[parent_field][sub_sheet_id],
                           path_list[1:],
                           id_fields=id_fields,
                           path=path,
                           top_sheet=top_sheet)
    else:
        if parent_field not in nested_dict:
            nested_dict[parent_field] = OrderedDict()
        return path_search(nested_dict[parent_field],
                           path_list[1:],
                           id_fields=id_fields,
                           path=path,
                           top_sheet=top_sheet)


class TemporaryDict(UserDict):
    def __init__(self, keyfield, top_sheet=False):
        self.keyfield = keyfield
        self.items_no_keyfield = []
        self.data = OrderedDict()
        self.top_sheet = top_sheet

    def __repr__(self):
        return 'TemporaryDict(keyfield={}, items_no_keyfield={}, data={})'.format(repr(self.keyfield), repr(self.items_no_keyfield), repr(self.data))

    def append(self, item):
        if self.keyfield in item:
            key = item[self.keyfield]
            if key not in self.data:
                self.data[key] = item
            else:
                self.data[key].update(item)
        else:
            self.items_no_keyfield.append(item)

    def to_list(self):
        return list(self.data.values()) + self.items_no_keyfield


def temporarydicts_to_lists(nested_dict):
    """ Recrusively transforms TemporaryDicts to lists inplace. """
    for key, value in nested_dict.items():
        if hasattr(value, 'to_list'):
            temporarydicts_to_lists(value)
            if hasattr(value, 'items_no_keyfield'):
                for x in value.items_no_keyfield:
                    temporarydicts_to_lists(x)
            nested_dict[key] = value.to_list()
        elif hasattr(value, 'items'):
            temporarydicts_to_lists(value)


class ConflictingIDFieldsError(ValueError):
    pass


def find_deepest_id_field(id_fields):
    split_id_fields = [x.split('/') for x in id_fields]
    deepest_id_field = max(split_id_fields, key=len)
    for split_id_field in split_id_fields:
        if not all(deepest_id_field[i] == x for i, x in enumerate(split_id_field[:-1])):
            raise ConflictingIDFieldsError()
    return '/'.join(deepest_id_field)

