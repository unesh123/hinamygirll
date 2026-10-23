"""Collect read-only ingress and regression evidence; never reads secret values."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/evidence'


def probe(url):
    result = {'url': url, 'checkedUtc': datetime.now(timezone.utc).isoformat()}
    try:
        with urlopen(url, timeout=15) as response:
            result.update(status=response.status, contentType=response.headers.get_content_type())
    except HTTPError as error:
        result.update(status=error.code, contentType=error.headers.get_content_type())
    except (URLError, TimeoutError):
        result.update(status=None, error='unreachable')
    return result


def main():
    deployed = json.loads((EVIDENCE / 'runtime-vercel-2026-10-20.json').read_text(encoding='utf-8-sig'))
    backend = {'state': 'RUNNING'}
    xml = EVIDENCE / 'runtime-backend-2026-10-20.xml'
    if xml.exists():
        suites = list(ElementTree.parse(xml).getroot().iter('testsuite'))
        total = sum(int(s.get('tests', '0')) for s in suites)
        failed = sum(int(s.get('failures', '0')) for s in suites)
        errors = sum(int(s.get('errors', '0')) for s in suites)
        skipped = sum(int(s.get('skipped', '0')) for s in suites)
        backend = {'state': 'COMPLETE', 'total': total, 'passed': total-failed-errors-skipped,
                   'failed': failed, 'errors': errors, 'skipped': skipped,
                   'todo': 0, 'failures': [c.get('classname', '') + '::' + c.get('name', '')
                     for c in ElementTree.parse(xml).getroot().iter('testcase')
                     if c.find('failure') is not None or c.find('error') is not None]}
        log_bytes = (EVIDENCE / 'runtime-backend-2026-10-20.log').read_bytes()
        try:
            log = log_bytes.decode('utf-8-sig')
        except UnicodeDecodeError:
            log = log_bytes.decode('utf-16', errors='replace')
        if '\x00' in log:
            log = log_bytes.decode('utf-16', errors='replace')
        summary = re.findall(r'^.*\d+ passed.*$', log, re.M)
        backend['summary'] = summary[-1].strip() if summary else None
    web_log = (EVIDENCE / 'runtime-frontend-2026-10-20.log').read_text(encoding='utf-8-sig', errors='replace')
    build_log = (EVIDENCE / 'runtime-build-2026-10-20.log').read_text(encoding='utf-8-sig', errors='replace')
    result = {
        'collectedUtc': datetime.now(timezone.utc).isoformat(),
        'deploymentId': deployed['id'], 'deploymentState': deployed['readyState'],
        'deployedRewrites': deployed['builds'][0]['config']['vercelConfig']['rewrites'],
        'commands': {
            'liveDocument': 'apps/api/.venv/Scripts/python.exe scripts/verify_restarted_runtime.py',
            'backend': 'apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests -o addopts= -q --junitxml=docs/evidence/runtime-backend-2026-10-20.xml',
            'frontend': 'pnpm --dir apps/web test', 'build': 'pnpm --dir apps/web build',
            'deploymentInspection': 'node tools/deploy/node_modules/vercel/dist/index.js inspect https://hinaa-workspace.vercel.app --json'},
        'backendTests': backend,
        'frontendTestSummary': [line.strip() for line in web_log.splitlines() if re.search(r'Test Files|Tests\s+\d+|Duration', line)],
        'frontendBuildPassed': bool(re.search(r'built in', build_log)),
        'routes': [probe(url) for url in [
            'http://127.0.0.1:8000/health/live',
            'http://127.0.0.1:5173/api/v1/capabilities',
            'https://hinaa-workspace.vercel.app/',
            'https://hinaa-workspace.vercel.app/health/live',
            'https://hinaa-workspace.vercel.app/api/v1/capabilities',
            'https://leisure-inter-town-possess.trycloudflare.com/health/live']],
        'localRuntime': json.loads((EVIDENCE / 'restarted-runtime-2026-10-20.json').read_text()),
        'connector': json.loads((EVIDENCE / 'runtime-connector-2026-10-20.json').read_text(encoding='utf-8-sig')),
        'browser': {'state': 'BLOCKED', 'mocked': False, 'reason': 'Public API ingress is unavailable; authenticated production document journey not attempted.'},
        'publicDocumentExecution': 'BLOCKED', 'publicDocumentDownload': 'BLOCKED',
        'blockers': ['Existing named connector authenticates but has no ingress rules and no approved public hostname was configured.',
                     'Production rewrites still point to the dead ephemeral hostname. No configuration, DNS or deployment mutation performed.']}
    (EVIDENCE / 'runtime-validation-summary-2026-10-20.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'backendTests': backend, 'routes': result['routes'], 'browser': result['browser']}, indent=2))


if __name__ == '__main__':
    main()
