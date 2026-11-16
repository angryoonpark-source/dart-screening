"""Local OpenDART disclosure lookup."""
import getpass
import io
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = 'https://opendart.fss.or.kr/api/'
PDF_FILES = {}
PDF_LOCK = threading.Lock()
PDF_LIFETIME = 15 * 60
PDF_LIMIT = 12
STATIC_REPORTS = {'한국자산신탁', '한국금거래소', '토스뱅크', '한빛산업'}


class LookupError(Exception):
    pass


def api_key():
    key = os.getenv('OPENDART_API_KEY', '').strip()
    if not key and (ROOT / '.env').is_file():
        for line in (ROOT / '.env').read_text().splitlines():
            name, _, value = line.partition('=')
            if name.strip() == 'OPENDART_API_KEY':
                key = value.strip()
                break
    if not re.fullmatch(r'[A-Za-z0-9]{40}', key):
        raise LookupError('Mac 터미널에서 python3 server.py --setup-key를 실행해 인증키를 등록해 주세요.')
    return key


def fetch(endpoint, key, **params):
    url = API + endpoint + '?' + urllib.parse.urlencode(dict(params, crtfc_key=key))
    try:
        with urllib.request.urlopen(url, timeout=25) as response:
            return response.read()
    except (OSError, urllib.error.URLError):
        raise LookupError('OpenDART에 접속하지 못했습니다. 잠시 후 다시 시도해 주세요.') from None


def normalize(name):
    return re.sub(r'\s+', '', name).casefold()


@lru_cache(maxsize=1)
def corporations(key, today):
    raw = fetch('corpCode.xml', key)
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            root = ET.fromstring(archive.read('CORPCODE.xml'))
    except (zipfile.BadZipFile, KeyError, ET.ParseError):
        try:
            check_status({'status': ET.fromstring(raw).findtext('status')})
        except ET.ParseError:
            pass
        raise LookupError('DART 기업 목록을 읽지 못했습니다.') from None
    return [
        (row.findtext('corp_name', '').strip(), row.findtext('stock_code', '').strip(),
         row.findtext('corp_code', '').strip())
        for row in root.findall('list')
    ]


def check_status(payload):
    code = payload.get('status')
    if code not in ('000', '013'):
        messages = {
            '010': 'OpenDART 인증키를 확인해 주세요.',
            '011': 'OpenDART에서 이 인증키의 사용이 중지됐습니다.',
            '012': 'OpenDART에서 현재 접속 IP를 허용하지 않습니다.',
            '020': 'OpenDART API 호출 한도에 도달했습니다.',
        }
        raise LookupError(messages.get(code, 'OpenDART에서 조회를 처리하지 못했습니다.'))


def lookup(company, today):
    key = api_key()
    matches = [row for row in corporations(key, today) if normalize(company) in
               (normalize(row[0]), row[1], row[2])]
    if not matches:
        raise LookupError('회사명을 찾지 못했습니다. DART에 등록된 정확한 이름이나 종목코드를 입력해 주세요.')
    if len(matches) > 1:
        raise LookupError('같은 이름의 기업이 있습니다. 종목코드 또는 DART 고유번호를 입력해 주세요. '
                          + ', '.join(code for _, _, code in matches))
    name, _, code = matches[0]
    try:
        start = today.replace(year=today.year - 3)
    except ValueError:
        start = today.replace(year=today.year - 3, day=28)
    filings = []
    page = 1
    while True:
        payload = json.loads(fetch('list.json', key, corp_code=code,
                                   bgn_de=start.strftime('%Y%m%d'), end_de=today.strftime('%Y%m%d'),
                                   last_reprt_at='N', page_no=page, page_count=100))
        check_status(payload)
        if payload['status'] == '013':
            break
        for filing in payload['list']:
            receipt = filing['rcept_no']
            if not re.fullmatch(r'\d{14}', receipt):
                raise LookupError('공시 접수번호를 읽지 못했습니다.')
            filings.append({'date': filing['rcept_dt'], 'title': filing['report_nm'],
                            'url': 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=' + receipt})
        if page >= payload['total_page']:
            break
        page += 1
    return {'company': name, 'code': code, 'start': start.isoformat(), 'end': today.isoformat(), 'filings': filings}


FINANCIAL_ACCOUNTS = {
    'balance': [
        ('자산총계', 'BS', ('자산총계', '자산총액')),
        ('부채총계', 'BS', ('부채총계', '부채총액')),
        ('자본총계', 'BS', ('자본총계', '자본총액')),
        ('현금및현금성자산', 'BS', ('현금및현금성자산',)),
    ],
    'income': [
        ('매출액·영업수익', 'IS', ('매출액', '매출', '영업수익', '수익(매출액)')),
        ('영업이익', 'IS', ('영업이익', '영업이익(손실)', '영업손익')),
        ('당기순이익', 'IS', ('당기순이익', '당기순이익(손실)', '당기순손익', '연결당기순이익')),
    ],
    'cash': [
        ('영업활동 현금흐름', 'CF', ('영업활동현금흐름', '영업활동순현금흐름', '영업활동으로인한현금흐름')),
        ('투자활동 현금흐름', 'CF', ('투자활동현금흐름', '투자활동순현금흐름', '투자활동으로인한현금흐름')),
        ('재무활동 현금흐름', 'CF', ('재무활동현금흐름', '재무활동순현금흐름', '재무활동으로인한현금흐름')),
    ],
}


def annual_figures(key, code, year, basis):
    data = json.loads(fetch('fnlttSinglAcntAll.json', key, corp_code=code,
                            bsns_year=year, reprt_code='11011', fs_div=basis))
    check_status(data)
    values = {}
    for row in data.get('list', []):
        account = (row['sj_div'], normalize(row['account_nm']))
        amount = (row.get('thstrm_amount') or '').replace(',', '')
        if re.fullmatch(r'-?\d+', amount):
            values.setdefault(account, int(amount))
    return values


def build_report(company, today):
    result = lookup(company, today)
    filings, code = result['filings'], result['code']
    key = api_key()
    profile = json.loads(fetch('company.json', key, corp_code=code))
    check_status(profile)

    annual = {}
    for filing in filings:
        period = re.search(r'사업보고서\s*\((\d{4})\.\d{2}\)', filing['title'])
        if period:
            annual.setdefault(period[1], filing)
    years = sorted(annual)[-3:]
    basis = 'CFS'
    figures = {}
    if years:
        latest = annual_figures(key, code, years[-1], basis)
        if not latest:
            basis = 'OFS'
            latest = annual_figures(key, code, years[-1], basis)
        if latest:
            figures = {year: annual_figures(key, code, year, basis) for year in years[:-1]}
            figures[years[-1]] = latest

    def value(accounts, item):
        _, section, names = item
        sections = ('IS', 'CIS') if section == 'IS' else (section,)
        return next((accounts[(group, name)] for group in sections for name in names
                     if (group, name) in accounts), None)

    def table(section, display_years):
        rows = []
        for item in FINANCIAL_ACCOUNTS[section]:
            amounts = [value(figures.get(year, {}), item) for year in display_years]
            rows.append([item[0], *['' if amount is None else f'{amount / 100_000_000:,.1f}' for amount in amounts]])
        return rows

    highlights = []
    if len(years) >= 2:
        previous, current = years[-2:]
        for item in [*FINANCIAL_ACCOUNTS['income'], FINANCIAL_ACCOUNTS['cash'][0]]:
            before = value(figures.get(previous, {}), item)
            after = value(figures.get(current, {}), item)
            if before is not None and after is not None and after < before:
                highlights.append(f'{item[0]}이(가) 전년보다 {(before-after)/100_000_000:,.1f}억 원 감소했습니다.')
    material = [f for f in filings if re.search(r'소송|판결|감사보고서|유상증자|감자결정|합병|회생|영업정지|공급계약', f['title'])][:8]
    refs = [(f['title'].strip(), f['url'][-14:]) for f in [*(annual[y] for y in reversed(years)), *material]]
    litigation = [[f['title'].strip(), f['date'], '', '', ''] for f in material if '소송' in f['title'] or '판결' in f['title']]
    compared = years[-2:]
    report = {
        'scope': f'{years[-1]}년 사업보고서 · {"연결" if basis == "CFS" else "별도"}' if figures else 'DART 공시 목록 기준',
        'opinion': ' '.join(highlights) if highlights else (
            '자동 비교에서 감소가 확인된 주요 손익·영업현금흐름 지표가 없습니다.' if figures and len(years) >= 2
            else '비교 가능한 재무정보가 부족합니다. 원문 재무제표와 감사보고서를 확인해 주세요.'),
        'overview': ' · '.join(str(profile[k]) for k in ('corp_name', 'ceo_nm', 'adres') if profile.get(k)),
        'business': '',
        'audit': '',
        'years': [f'{y}년' for y in compared],
        'trendYears': [f'{y}년' for y in years],
        'balance': table('balance', compared) if figures else [],
        'income': table('income', compared) if figures else [],
        'cash': table('cash', compared) if figures else [],
        'trend': table('income', years) if figures else [],
        'risks': [[f['title'].strip(), f['date'], '원문에서 발생 조건과 회사에 미칠 영향을 확인합니다.'] for f in material],
        'riskHeading': '주요 공시 · 원문 검토 대상',
        'litigation': litigation,
        'followup': '사업 내용, 감사의견, 우발채무와 소송의 구체적인 내용은 공시 원문을 추가 검토합니다.',
        'sources': list(dict.fromkeys(refs)),
    }
    return {'company': result['company'], 'code': code, 'report': report}


def render_pdf(company, agenda, automatic=None):
    browser = os.getenv('PDF_BROWSER') or shutil.which('chromium') or shutil.which('google-chrome')
    if not browser:
        browser = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
    with tempfile.TemporaryDirectory(prefix='dart-report-') as work:
        folder = Path(work)
        report = folder / 'index.html'
        output = folder / 'report.pdf'
        data = json.dumps({'company': company, 'agenda': agenda, 'automatic': automatic}).replace('<', '\\u003c')
        html = (ROOT / 'dist/index.html').read_text(encoding='utf-8')
        report.write_text(html.replace('</head>', f'<script id="pdf-render-data" type="application/json">{data}</script></head>', 1), encoding='utf-8')
        for name in ('app.js', 'company-reports.js', 'style.css'):
            shutil.copyfile(ROOT / 'dist' / name, folder / name)
        subprocess.run([
            browser, '--headless', '--disable-background-networking', '--no-first-run',
            '--no-pdf-header-footer', f'--user-data-dir={folder / "browser-profile"}',
            f'--print-to-pdf={output}', report.as_uri(),
        ], check=True, timeout=25, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output.read_bytes()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'dist'), **kwargs)

    def do_GET(self):
        target = urllib.parse.urlsplit(self.path)
        match = re.fullmatch(r'/api/report-files/([a-f0-9]{32})', target.path)
        if match:
            with PDF_LOCK:
                record = PDF_FILES.get(match[1])
            if not record or record[0] <= time.monotonic():
                self.send_error(404, 'PDF expired or unavailable')
                return
            _, company, pdf = record
            download = urllib.parse.parse_qs(target.query).get('download') == ['1']
            self.send_pdf(company, pdf, download)
            return
        if target.path not in ('/api/disclosures', '/api/report'):
            return super().do_GET()
        company = urllib.parse.parse_qs(target.query).get('company', [''])[0].strip()
        try:
            if not company or len(company) > 80:
                raise LookupError('기업명을 입력해 주세요.')
            today = datetime.now(timezone(timedelta(hours=9))).date()
            handler = build_report if target.path == '/api/report' else lookup
            payload = handler(company, today)
            status = 200
        except LookupError as exc:
            payload, status = {'error': str(exc)}, 400
        except (ValueError, TypeError, KeyError, OSError):
            payload, status = {'error': 'OpenDART 응답을 읽지 못했습니다.'}, 502
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != '/api/report.pdf':
            self.send_error(404)
            return
        if (self.headers.get_content_type() != 'application/x-www-form-urlencoded'
                or self.headers.get('Sec-Fetch-Site') == 'cross-site'):
            self.send_error(415)
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 16384:
                raise ValueError
            data = urllib.parse.parse_qs(self.rfile.read(size).decode('ascii'), keep_blank_values=True, max_num_fields=2)
            company, agenda = data['company'][0], data['agenda'][0]
            if not company.strip() or len(company) > 80 or len(agenda) > 1000:
                raise ValueError
        except (ValueError, TypeError, KeyError):
            self.send_error(400)
            return
        try:
            automatic = None
            if company not in STATIC_REPORTS:
                automatic = build_report(company, datetime.now(timezone(timedelta(hours=9))).date())
                company = automatic['company']
            pdf = render_pdf(company, agenda, automatic)
        except LookupError:
            self.send_error(400)
            return
        except (OSError, subprocess.SubprocessError):
            self.send_error(500)
            return
        if self.headers.get('Accept') == 'application/json':
            token = secrets.token_hex(16)
            now = time.monotonic()
            with PDF_LOCK:
                for key in list(PDF_FILES):
                    if PDF_FILES[key][0] <= now:
                        del PDF_FILES[key]
                if len(PDF_FILES) >= PDF_LIMIT:
                    del PDF_FILES[next(iter(PDF_FILES))]
                PDF_FILES[token] = (now + PDF_LIFETIME, company, pdf)
            body = json.dumps({'file': token}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_pdf(company, pdf, download=True)

    def send_pdf(self, company, pdf, download):
        filename = urllib.parse.quote(company + '-사전검토.pdf')
        disposition = 'attachment' if download else 'inline'
        self.send_response(200)
        self.send_header('Content-Type', 'application/pdf')
        self.send_header('Content-Disposition', f'{disposition}; filename="dart-report.pdf"; filename*=UTF-8\'\'{filename}')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(pdf)))
        self.end_headers()
        self.wfile.write(pdf)


def setup_key():
    path = ROOT / '.env'
    if path.exists():
        sys.exit('.env 파일이 이미 있습니다. 기존 파일에서 인증키를 확인해 주세요.')
    key = getpass.getpass('OpenDART 인증키 (입력값이 화면에 표시되지 않습니다): ').strip()
    if not re.fullmatch(r'[A-Za-z0-9]{40}', key):
        sys.exit('40자리 인증키를 입력해 주세요.')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as config:
        config.write('OPENDART_API_KEY=' + key + '\n')
    print('로컬 .env 파일에 인증키를 저장했습니다.')


if __name__ == '__main__':
    if sys.argv[1:] == ['--setup-key']:
        setup_key()
    else:
        with ThreadingHTTPServer(('127.0.0.1', 8765), Handler) as server:
            print('http://127.0.0.1:8765', flush=True)
            server.serve_forever()
