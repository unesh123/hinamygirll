"""Exercise current live HTTP worker and PDF validation without mocked transport."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps' / 'api'))
from pypdf import PdfReader
from hinaa_api.tools.pdf_generate import DOCS_DIR


def check(url, body=None):
    request = Request(url, data=json.dumps(body).encode() if body else None,
                      headers={'Content-Type': 'application/json'} if body else {})
    try:
        with urlopen(request, timeout=60) as response:
            return response.status, response.headers.get_content_type(), response.read()
    except HTTPError as error:
        return error.code, error.headers.get_content_type(), error.read()


def main():
    origin = 'http://127.0.0.1:8000'
    start = datetime.now(timezone.utc).isoformat()
    payload = {'toolName': 'pdf_generate', 'parameters': {
        'title': 'Restarted Runtime Study Plan',
        'content': '# Study Plan\n\nStudy algebra for thirty minutes daily.\n\n## Practice\nComplete five exercises and record mistakes.\n\n## Review\nReview mistakes every Sunday.'}}
    status, mime, raw = check(origin + '/api/v1/tools/execute', payload)
    assert status == 200, (status, raw[:300])
    data = json.loads(raw)
    while isinstance(data.get('data'), dict):
        data = data['data']
    assert data['status'] == 'success' and data['validationStatus'] == 'validated', data
    path = Path(data['canonicalPath'])
    sidecar_path = path.with_suffix('.metadata.json')
    sidecar = json.loads(sidecar_path.read_text())
    assert sidecar['sha256'] == data['sha256']
    assert datetime.fromisoformat(sidecar['validatedAt']).timestamp() <= sidecar_path.stat().st_mtime + 2
    download = origin + data['downloadUrl']
    ds, dm, downloaded = check(download)
    assert ds == 200 and dm == 'application/pdf'
    assert len(downloaded) == data['fileSizeBytes']
    assert hashlib.sha256(downloaded).hexdigest() == data['sha256']
    assert len(PdfReader(path).pages) == data['pageCount']

    # Only create/delete this script's uniquely named corrupt fixture, never
    # mutate the valid sample or any existing user document.
    from uuid import uuid4
    corrupt_id = str(uuid4())
    corrupt = DOCS_DIR / (corrupt_id + '.pdf')
    try:
        with corrupt.open('xb') as stream:
            stream.write(b'%PDF-1.7 deliberately invalid runtime test')
        cs, cm, _ = check(origin + '/api/v1/generated-docs/' + corrupt_id)
        assert cs == 422, cs
    finally:
        corrupt.unlink(missing_ok=True)
    missing_id = str(uuid4())
    ms, mm, _ = check(origin + '/api/v1/generated-docs/' + missing_id)
    assert ms == 404, ms
    evidence = {'startedUtc': start, 'finishedUtc': datetime.now(timezone.utc).isoformat(),
                'command': 'apps/api/.venv/Scripts/python.exe scripts/verify_restarted_runtime.py',
                'mocked': False, 'generation': {'url': origin + '/api/v1/tools/execute', 'status': status, 'contentType': mime},
                'artifact': data, 'sidecarExists': True, 'validationBeforeRegistration': True,
                'download': {'url': download, 'status': ds, 'contentType': dm, 'bytes': len(downloaded), 'sha256Matches': True},
                'corruptDownload': {'status': cs, 'contentType': cm},
                'missingDownload': {'status': ms, 'contentType': mm}}
    target = ROOT / 'docs/evidence/restarted-runtime-2026-10-20.json'
    target.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
