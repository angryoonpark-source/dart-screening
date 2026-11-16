const form = document.querySelector('#analysis-form');
const companyInput = document.querySelector('#company');
const agendaInput = document.querySelector('#agenda');
const kaitPages = document.querySelectorAll('[data-kait]');
const demoPages = document.querySelectorAll('[data-demo]');
const agendaPage = document.querySelector('#agenda-page');
const agendaText = document.querySelector('#agenda-text');
const agendaChecks = document.querySelector('#agenda-checks');
const status = document.querySelector('#status');
const pdfForm = document.querySelector('#pdf-form');
const pdfStatus = document.querySelector('#pdf-status');
const pdfActions = document.querySelector('#pdf-actions');
const pdfButton = pdfForm.querySelector('button');

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function reportTable(headers, rows, className) {
  const table = element('table', '', className);
  const header = table.createTHead().insertRow();
  headers.forEach((label) => {
    const cell = element('th', label);
    cell.scope = 'col';
    header.append(cell);
  });
  const body = table.createTBody();
  rows.forEach(([label, ...values]) => {
    const row = body.insertRow();
    const title = element('th', label);
    title.scope = 'row';
    row.append(title, ...values.map((value) => element('td', value)));
  });
  return table;
}

function sources(references) {
  const line = element('p', '', 'source');
  references.forEach(([label, receipt], index) => {
    if (index) line.append(' · ');
    const link = element('a', label);
    link.href = 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=' + receipt;
    line.append(link);
  });
  return line;
}

function renderCompanyPages(company, report) {
  document.querySelectorAll('[data-company-report]').forEach((page) => page.remove());
  if (!report) return;

  function page(title) {
    const article = element('article', '', 'paper');
    article.dataset.companyReport = '';
    article.append(element('p', report.scope, 'report-meta'), element('h2', title));
    agendaPage.before(article);
    return article;
  }

  function section(parent, heading, ...content) {
    parent.append(element('h3', heading), ...content);
  }

  const years = ['항목', '2024년', '2025년'];
  const overview = page(company + ' 기업 분석');
  section(overview, '종합 의견', element('p', report.opinion));
  section(overview, '회사 개요', element('p', report.overview));
  section(overview, '사업 및 영업 개요', element('p', report.business));
  const figures = element('div', '', 'financial-tables');
  const balance = element('section');
  const income = element('section');
  section(balance, '재무상태표 요약', reportTable(years, report.balance, 'numeric-table'));
  section(income, '손익계산서 요약', reportTable(years, report.income, 'numeric-table'));
  overview.append(element('p', '단위 억 원', 'comparison-note'), figures, sources(report.sources.slice(0, 1)));
  figures.append(balance, income);

  const finances = page('현금흐름·실적 추이·감사');
  finances.append(element('p', '단위 억 원', 'comparison-note'));
  section(finances, '현금흐름표 요약', reportTable(years, report.cash, 'numeric-table'));
  section(finances, '최근 3개년 실적', reportTable(['항목', '2023년', '2024년', '2025년'], report.trend, 'numeric-table'));
  section(finances, '감사·회계 유의사항', element('p', report.audit), sources(report.sources.slice(0, 2)));

  const risks = page('업종별 위험과 주요 소송 현황');
  section(risks, '재무제표 주석과 업종별 위험', reportTable(['항목', '공시에서 확인한 사실', '정밀검토 질문'], report.risks, 'notes-table'));
  section(risks, '주요 소송 현황', reportTable(['사건', '진행 상태', '공시 금액', '확정 여부', '출처'], report.litigation, 'litigation-table'));
  section(risks, '우선 요청 자료', element('p', report.followup), sources(report.sources));
}

const agendaTopics = [
  [/차입|대출|회사채|사채/, '금리, 차입 만기, 기존 금융약정과 상환재원을 확인합니다.'],
  [/보증|담보/, '보증 또는 담보의 제공 한도, 청구 조건, 계약 종료일을 확인합니다.'],
  [/대여|지원/, '상대방의 상환재원, 대여 조건과 회수 방안을 확인합니다.'],
  [/인수|합병|출자|투자|취득/, '거래 목적, 가격 산정 근거, 거래 후 추가 자금 투입 계획을 확인합니다.'],
];

companyInput.addEventListener('input', () => companyInput.setCustomValidity(''));

function agendaReview(isKait, agenda) {
  const pledge = /담보|질권|양도/.test(agenda);
  const trustReceivable = /신탁\s*계정\s*대|계정\s*대여|계정대/.test(agenda);
  if (isKait && pledge && trustReceivable) {
    const amount = agenda.match(/([\d,]+(?:\.\d+)?)\s*억\s*원/)?.[1];
    const principal = amount ? '원금 ' + amount + '억 원' : '예정 대여 원금';
    return {
      opinion: '집행 보류. 반기 말 신탁계정대는 총액 7,056억 원, 대손충당금 2,019억 원입니다. 충당금 설정률은 전년 말 20.1%에서 28.6%로 상승했고, 일부 사업장의 비용상환청구권은 기존 차입 담보로 제공된 상태입니다. 담보로 받을 채권의 사업장과 순위, 실제 회수 가능액을 확인할 때까지 대여 한도를 판단하기 어렵습니다.',
      checks: [
        '담보 대상 사업장별 채권 명세와 신탁계약을 받아 권리의 범위, 기존 담보·중복 제공 여부, 우선순위와 담보 설정·집행 요건을 확인합니다.',
        '분양대금이나 처분대금에서 선순위 사업비, 공사비, 반환청구 등 우선 지급액을 차감한 뒤 남는 회수액을 산정합니다.',
        '분양 지연과 가격 하락을 가정해 회수 부족 및 만기 불일치를 점검하고, 대여 원리금 대비 담보 여유와 한국자산신탁 자체 상환재원을 각각 확인합니다.',
        principal + '에 이자·집행비용까지 더해 회수 여력을 검토합니다. 타당성이 확인되면 회수금 관리와 담보 부족 시 조치 조건을 계약에 반영할 수 있는지 확인합니다.',
      ],
    };
  }

  const checks = agendaTopics
    .filter(([pattern]) => pattern.test(agenda))
    .map(([, question]) => question);
  if (agenda && !checks.length) {
    checks.push('거래 목적, 상대방, 금액, 집행 시점과 계약 조건을 확인합니다.');
  }
  if (checks.length > 1) {
    checks.push('복수 거래의 자금 집행, 상환, 보증 청구 시점이 겹치는지 확인합니다.');
  }
  return {
    opinion: isKait
      ? '안건에 따른 신규 지급 일정과 기존 차입금 만기, 신탁계정대 회수 일정을 대조합니다. 사업장별 회수 자료와 계약 조건을 확보한 후 부담을 판단할 수 있습니다.'
      : '가상 기업의 현금성자산은 1년 내 차입금 만기액을 밑돕니다. 안건에서 발생할 지급액을 기존 차입금 상환 일정에 합쳐 확인합니다.',
    checks,
  };
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const company = companyInput.value.trim();
  if (!company) {
    companyInput.setCustomValidity('기업명을 입력하세요.');
    companyInput.reportValidity();
    return;
  }

  const isKait = ['한국자산신탁', '123890', '00404701'].includes(company.replace(/\s+/g, ''));
  const matched = Object.entries(companyReports).find(([name, report]) => name === company || report.code === company);
  const isDemo = company === '한빛산업';
  if (!isKait && !matched && !isDemo) {
    companyInput.setCustomValidity('등록된 보고서는 한국자산신탁, 한국금거래소, 토스뱅크입니다. 다른 기업은 DART 공시 조회를 이용해 주세요.');
    companyInput.reportValidity();
    return;
  }

  const agenda = agendaInput.value.trim();
  const reportCompany = isKait ? '한국자산신탁' : matched?.[0] ?? '한빛산업';
  pdfForm.elements.company.value = reportCompany;
  pdfForm.elements.agenda.value = agenda;
  pdfStatus.hidden = true;
  pdfActions.hidden = true;
  const review = agendaReview(isKait, agenda);
  if (matched) {
    review.opinion = '입력된 거래 조건을 확인한 뒤 기업 검토본의 관련 위험과 대조합니다. ' + matched[1].followup;
  }
  kaitPages.forEach((page) => { page.hidden = !isKait; });
  demoPages.forEach((page) => { page.hidden = !isDemo; });
  renderCompanyPages(reportCompany, matched?.[1]);
  agendaPage.hidden = !agenda;
  agendaText.textContent = agenda;
  document.querySelector('#agenda-opinion').textContent = review.opinion;
  document.querySelector('#agenda-source').hidden = !isKait;

  agendaChecks.replaceChildren(...review.checks.map((question) => {
    const item = document.createElement('li');
    item.textContent = question;
    return item;
  }));

  status.textContent = reportCompany
    + (agenda ? ' 기업 분석과 안건 의견' : ' 기업 분석') + '을 표시했습니다.';
  if (window.matchMedia('(max-width: 800px)').matches) {
    document.querySelector('#preview-title').scrollIntoView();
  }
});

pdfForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  pdfStatus.hidden = false;
  pdfActions.hidden = true;
  if (window.location.protocol === 'file:') {
    pdfStatus.textContent = 'PDF 저장은 서버에서 열린 화면에서 사용할 수 있습니다.';
    return;
  }
  pdfButton.disabled = true;
  pdfStatus.textContent = 'PDF를 만드는 중입니다…';
  const data = new URLSearchParams(new FormData(pdfForm));
  try {
    const response = await fetch(pdfForm.action, {
      method: 'POST',
      headers: { Accept: 'application/json' },
      body: data,
    });
    if (!response.ok) {
      pdfStatus.textContent = 'PDF 생성 요청에 실패했습니다. 서버 응답 ' + response.status + '.';
      return;
    }
    const { file } = await response.json();
    if (!/^[a-f0-9]{32}$/.test(file)) throw new Error('Unexpected PDF response');
    if (data.get('company') !== pdfForm.elements.company.value ||
        data.get('agenda') !== pdfForm.elements.agenda.value) return;
    const url = new URL('api/report-files/' + file, document.baseURI);
    document.querySelector('#pdf-open').href = url.href;
    url.searchParams.set('download', '1');
    document.querySelector('#pdf-download').href = url.href;
    pdfStatus.textContent = 'PDF가 준비됐습니다. 아래에서 열거나 다운로드하세요.';
    pdfActions.hidden = false;
    document.querySelector('#pdf-download').click();
  } catch {
    pdfStatus.textContent = 'PDF 저장 서버에 연결하지 못했습니다. 화면을 새로고침한 뒤 다시 시도해 주세요.';
  } finally {
    pdfButton.disabled = false;
  }
});

const renderData = document.querySelector('#pdf-render-data');
if (renderData) {
  const report = JSON.parse(renderData.textContent);
  companyInput.value = report.company;
  agendaInput.value = report.agenda;
  form.requestSubmit();
} else {
  const company = new URLSearchParams(window.location.search).get('company');
  if (company && Object.hasOwn(companyReports, company)) {
    companyInput.value = company;
    form.requestSubmit();
  }
}

const lookupButton = document.querySelector('#lookup');
const lookupStatus = document.querySelector('#lookup-status');
const disclosures = document.querySelector('#disclosures');

lookupButton.hidden = window.location.protocol === 'file:';
lookupButton.addEventListener('click', async () => {
  const company = companyInput.value.trim();
  if (!company) {
    companyInput.setCustomValidity('기업명을 입력하세요.');
    companyInput.reportValidity();
    return;
  }

  lookupButton.disabled = true;
  disclosures.hidden = true;
  lookupStatus.textContent = company + ' 공시 조회 중…';
  try {
    const query = new URLSearchParams({ company: Object.hasOwn(companyReports, company) ? companyReports[company].code : company });
    const response = await fetch('/api/disclosures?' + query);
    const result = await response.json();
    if (!response.ok) {
      lookupStatus.textContent = result.error;
      return;
    }

    document.querySelector('#disclosures-title').textContent = result.company + ' DART 공시';
    const count = result.filings.length;
    document.querySelector('#disclosures-range').textContent =
      result.start + ' ~ ' + result.end + ' · ' + count + '건';
    document.querySelector('#disclosures-list').replaceChildren(...result.filings.map((filing) => {
      const item = document.createElement('li');
      const link = document.createElement('a');
      link.href = filing.url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = filing.title;
      item.append(filing.date.replace(/^(\d{4})(\d{2})(\d{2})$/, '$1.$2.$3') + ' · ', link);
      return item;
    }));
    disclosures.hidden = false;
    lookupStatus.textContent = count + '건을 조회했습니다.';
    disclosures.scrollIntoView();
  } catch {
    lookupStatus.textContent = '공시 조회 서버 응답을 읽지 못했습니다.';
  } finally {
    lookupButton.disabled = false;
  }
});
