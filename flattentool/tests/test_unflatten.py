import os
import json
import pytest

from flattentool import unflatten

def test_360_main_sheetname_insensitive(tmpdir):
    input_name = 'flattentool/tests/fixtures/xlsx/fundingproviders-grants_2_grants.xlsx'
    unflatten(
        input_name=input_name,
        output_name=tmpdir.join('output_grant.json').strpath,
        input_format='xlsx',
        schema='flattentool/tests/fixtures/360-giving-schema.json',
        main_sheet_name='grants',
        root_list_path='grants',
        root_id='',
        convert_titles=True)
    output_json_grants = json.load(tmpdir.join('output_grant.json'))

    input_name = 'flattentool/tests/fixtures/xlsx/fundingproviders-grants_2_grants_sheet_title_case.xlsx'
    unflatten(
        input_name=input_name,
        output_name=tmpdir.join('output_grant_sheet_title_case.json').strpath,
        input_format='xlsx',
        schema='flattentool/tests/fixtures/360-giving-schema.json',
        main_sheet_name='grants',
        root_list_path='grants',
        root_id='',
        convert_titles=True)
    output_json_Grants = json.load(tmpdir.join('output_grant_sheet_title_case.json'))

    assert output_json_grants == output_json_Grants

def test_360_fields_case_insensitive(tmpdir):
    input_name = 'flattentool/tests/fixtures/xlsx/fundingproviders-grants_2_grants.xlsx'
    unflatten(
        input_name=input_name,
        output_name=tmpdir.join('output_grant.json').strpath,
        input_format='xlsx',
        schema='flattentool/tests/fixtures/360-giving-schema.json',
        main_sheet_name='grants',
        root_list_path='grants',
        root_id='',
        convert_titles=True)
    output_json_grants = json.load(tmpdir.join('output_grant.json'))

    input_name = 'flattentool/tests/fixtures/xlsx/fundingproviders-grants_2_grants_title_space_case.xlsx'
    unflatten(
        input_name=input_name,
        output_name=tmpdir.join('output_space_case.json').strpath,
        input_format='xlsx',
        schema='flattentool/tests/fixtures/360-giving-schema.json',
        main_sheet_name='grants',
        root_list_path='grants',
        root_id='',
        convert_titles=True)
    output_json_space_case = json.load(tmpdir.join('output_space_case.json'))

    assert output_json_grants == output_json_space_case


@pytest.mark.parametrize('dirname', ['examples/iati', 'examples/iati_multilang'])
def test_unflatten_xml(tmpdir, dirname):
    unflatten(
        input_name=dirname,
        output_name=tmpdir.join('output.xml').strpath,
        input_format='csv',
        root_list_path='iati-activity',
        id_name='iati-identifier',
        xml=True)
    assert open(os.path.join(dirname, 'expected.xml')).read() == tmpdir.join('output.xml').read()


def test_unflatten_org_xml(tmpdir):
    unflatten(
        input_name='flattentool/tests/fixtures/xlsx/iati-org.xlsx',
        output_name=tmpdir.join('output.xml').strpath,
        input_format='xlsx',
        id_name='organisation-identifier',
        xml=True,
        metatab_name='Meta'
        )
    assert open('flattentool/tests/fixtures/iati-org.xml').read() == tmpdir.join('output.xml').read()
