import json
import pytest
from fastapi.testclient import TestClient
from hinaa_api.tools.intent_gate import sanction_tools
from hinaa_api.tools.request_contract import interpret_request
from hinaa_api.tools import pdf_generate
from hinaa_api.artifacts.document_validation import validate_pdf


@pytest.mark.parametrize('text,expected', [
    ('Explain PDF generation.', set()),
    ('Can you create a PDF about my study plan?', {'pdf_generate'}),
    ('Explain the layout, then create the PDF.', {'pdf_generate'}),
    ('Do not generate an image; create a PDF report.', {'pdf_generate'}),
    ('Create a report with an illustration.', {'pdf_generate', 'image_generate'}),
    ('Create a folder named generate-images.', {'computer_operator'}),
    ('You said "create a PDF" yesterday.', set()),
    ('"Create a PDF; generate an image of a mountain"', set()),
    ('You said "create a PDF; generate an image of a mountain" yesterday.', set()),
    ('Do not create a PDF; generate an image of a mountain.', {'image_generate'}),
    ('Cancel PDF generation.', set()),
    ('Create an image of a mountain; create a PDF report.', {'image_generate', 'pdf_generate'}),
])
def test_clause_authority(text, expected):
    actual = sanction_tools(text).allowed
    assert expected <= actual
    assert ('image_generate' in actual) == ('image_generate' in expected)
    assert ('pdf_generate' in actual) == ('pdf_generate' in expected)


def test_mixed_contract_preserves_discussion():
    contract = interpret_request('Explain the layout, then create the PDF.')
    assert [c.mode for c in contract.clauses] == ['discuss', 'execute']


def test_mixed_deliverables_survive_final_tool_gate():
    from hinaa_api.models import ToolRequest
    from hinaa_api.tools.intent_gate import gate_tool_requests
    text = 'Explain the layout, then create a report with an illustration.'
    kept, _, sanction = gate_tool_requests(text, [
        ToolRequest(toolName='pdf_generate', parameters={'content': 'Supplied report body'}),
        ToolRequest(toolName='image_generate', parameters={'prompt': 'An illustration'}),
    ])
    assert {r.toolName for r in kept} == {'pdf_generate', 'image_generate'}
    assert sanction.request_contract['clauses'][0]['mode'] == 'discuss'


def test_pdf_and_docx_are_separate_deliverables():
    from hinaa_api.models import ToolRequest
    from hinaa_api.tools.intent_gate import gate_tool_requests
    kept, _, _ = gate_tool_requests('Create a PDF and create a DOCX report.', [
        ToolRequest(toolName='pdf_generate', parameters={'content': 'Supplied report body'})])
    assert len(kept) == 2
    assert kept[1].toolName == 'document_generate'
    assert kept[1].parameters['format'] == 'docx'
    assert kept[1].parameters['content'] == 'Supplied report body'


@pytest.mark.parametrize('text', ['Stop generating images', 'Cancel PDF generation', 'Do not create a PDF'])
def test_cancel_and_negation_remove_invented_generation(text):
    from hinaa_api.models import ToolRequest
    from hinaa_api.tools.intent_gate import gate_tool_requests
    kept, _, _ = gate_tool_requests(text, [ToolRequest(toolName='pdf_generate', parameters={}), ToolRequest(toolName='image_generate', parameters={})])
    assert kept == []


@pytest.mark.asyncio
async def test_real_pdf_worker_registration_and_download(tmp_path, monkeypatch):
    from hinaa_api.artifacts import inventory
    from hinaa_api.main import create_app
    from hinaa_api.config import Settings
    monkeypatch.setattr(pdf_generate, 'DOCS_DIR', tmp_path)
    monkeypatch.setattr(inventory, 'document_roots', lambda: [tmp_path])
    request = 'Can you create a PDF about my study plan?'
    assert 'pdf_generate' in sanction_tools(request).allowed
    result = await pdf_generate.pdf_generate_handler(pdf_generate.GeneratePDFParams(
        title='Verified Study Plan', content='# Study plan\n\nStudy algebra for 30 minutes daily.\n\n## Review\nComplete five exercises and review mistakes.', userId='milestone'))
    assert result['status'] == 'success'
    path = next(tmp_path.glob('*.pdf'))
    assert validate_pdf(path)['sha256'] == result['sha256']
    sidecar = json.loads(path.with_suffix('.metadata.json').read_text())
    assert sidecar['artifactId'] == result['docId']
    app = create_app(Settings(_env_file=None, HINAA_AUTH_MODE='dev', HINAA_PROVIDER_MODE='mock', HINAA_DATABASE_URL='sqlite+pysqlite:///:memory:'))
    with TestClient(app) as client:
        execution = client.post('/api/v1/tools/execute', json={
            'toolName': 'pdf_generate', 'parameters': {
                'title': 'HTTP Worker Study Plan', 'content': '# Study plan\n\nStudy algebra daily and review five exercises.'}})
        assert execution.status_code == 200, execution.text
        executed = execution.json()['data']['data']
        assert executed['validationStatus'] == 'validated'
        assert client.get(executed['downloadUrl']).status_code == 200
        response = client.get(result['downloadUrl'])
        assert response.status_code == 200
        assert response.headers['content-type'] == 'application/pdf'
        assert response.content == path.read_bytes()
        path.unlink()
        assert client.get(result['downloadUrl']).status_code == 404
        path.write_bytes(b'not a PDF')
        assert client.get(result['downloadUrl']).status_code == 422


@pytest.mark.parametrize('failure', ['worker', 'missing', 'invalid'])
@pytest.mark.asyncio
async def test_pdf_failure_never_registers_success(failure, tmp_path, monkeypatch):
    def broken(**kwargs):
        path = tmp_path / 'broken.pdf'
        if failure == 'worker':
            raise RuntimeError('worker failed')
        if failure == 'invalid':
            path.write_bytes(b'%PDF-1.7 not parseable')
        return path, 1
    monkeypatch.setattr(pdf_generate, '_generate_reportlab_pdf', broken)
    result = await pdf_generate.pdf_generate_handler({'title': 'Failure test', 'content': 'Actual source text.'})
    assert result['status'] == 'error'
    assert 'downloadUrl' not in result
    assert not list(tmp_path.glob('*.metadata.json'))
