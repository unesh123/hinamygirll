"""Verify a real PDF through an existing local API; no provider or deployment calls."""
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps' / 'api'))
from hinaa_api.tools.intent_gate import sanction_tools
from hinaa_api.tools.pdf_generate import pdf_generate_handler
from hinaa_api.artifacts.document_validation import validate_pdf


async def main():
    request = 'Can you create a PDF about my study plan?'
    route = sanction_tools(request)
    assert 'pdf_generate' in route.allowed
    result = await pdf_generate_handler({
        'title': 'HINAA Verified Study Plan', 'userId': 'local-milestone',
        'content': '# Weekly Study Plan\n\nStudy algebra for 30 minutes each weekday.\n\n## Practice\nComplete five exercises, check answers, and record mistakes.\n\n## Review\nReview difficult problems every Sunday and plan the following week.'})
    assert result['status'] == 'success', result
    path = Path(result['canonicalPath'])
    validate_pdf(path)
    with urlopen('http://127.0.0.1:8000' + result['downloadUrl'], timeout=15) as response:
        downloaded = response.read()
        assert response.status == 200
        assert response.headers.get_content_type() == 'application/pdf'
    assert hashlib.sha256(downloaded).hexdigest() == result['sha256']
    assert downloaded == path.read_bytes()
    evidence = {'request': request, 'allowedTools': sorted(route.allowed), **result,
                'downloadStatus': 200, 'downloadBytes': len(downloaded), 'downloadHashMatches': True,
                'mocked': False, 'providerCalls': 0}
    target = ROOT / 'docs' / 'evidence' / 'document-milestone-2026-10-20.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
