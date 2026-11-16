# DART 기업 사전검토

기업의 사업 구조와 재무 변화, 공시에 드러난 위험을 한 보고서에 정리하는 도구입니다. 정밀검토를 시작할 때 **무엇이 바뀌었고 어떤 자료를 먼저 확인해야 하는지** 파악할 수 있도록 만들었습니다.

[한국자산신탁 검토 예시](examples/korea-asset-trust.md) · [금융감독원 OpenDART](https://opendart.fss.or.kr/)

## 주요 기능

| 기능 | 화면에서 할 수 있는 일 |
|---|---|
| 공시 조회 | 회사명이나 종목코드로 최근 3년치 공시 목록을 조회하고 DART 원문을 엽니다. 정정공시도 목록에 포함됩니다. |
| 기업 검토본 | 한국자산신탁·한국금거래소·토스뱅크의 실공시를 대조해 작성한 보고서를 봅니다. 회사와 사업 개요, 재무제표 요약, 3개년 실적, 감사, 업종별 위험, 주석과 소송이 포함됩니다. |
| 새 기업 기본 검토 | 본인의 OpenDART 인증키로 기업을 조회합니다. 재무 API가 제공하는 연간 재무제표와 최근 주요 공시를 보고서로 정리합니다. |
| AI 종합 검토 | 회사명과 선택 안건을 받아 DART 사업·감사보고서와 주요 수시공시 원문 발췌를 검토합니다. 회사 개요, 재무, 주석, 감사, 소송 및 안건 의견을 같은 양식에 표시합니다. |
| PDF 저장 | 현재 표시된 보고서를 A4 PDF로 내려받습니다. |

공시 목록은 OpenDART에서 실시간으로 조회합니다. 세 회사의 예시 검토본은 기준일에 확인한 공시를 바탕으로 작성했습니다. 기본 검토는 재무 수치와 공시 제목을 정리하고, AI 종합 검토는 선택한 공시 본문 발췌를 분석합니다. 확인하지 못한 항목은 공란으로 표시될 수 있습니다.

## 로컬 실행

Python 3.9 이상이 필요합니다. PDF 생성에는 Mac의 Microsoft Edge 또는 서버에 설치된 Chromium·Chrome이 필요합니다. 브라우저 경로가 다르면 `PDF_BROWSER` 환경변수로 실행 파일을 지정할 수 있습니다.

```sh
git clone https://github.com/angryoonpark-source/dart-screening.git
cd dart-screening
python3 server.py
```

[로컬 화면](http://127.0.0.1:8765/)을 열고 회사명을 입력한 뒤 **보고서 미리보기**를 누릅니다. 한국자산신탁은 기본 화면에 표시됩니다. 검토본 미리보기와 PDF 저장은 인증키 없이 체험할 수 있습니다.

**실시간 공시 조회**를 사용하려면 프로젝트 폴더에서 `python3 server.py --setup-key`를 실행하고 본인의 [OpenDART 인증키](https://opendart.fss.or.kr/uss/umt/EgovMberInsertView.do)를 입력합니다. 키는 로컬 `.env`에 저장됩니다.

**AI 종합 검토**를 사용하려면 본인의 [OpenAI API 키](https://platform.openai.com/api-keys)를 발급받고 API 프로젝트의 결제를 설정한 뒤, 프로젝트 폴더에서 `python3 server.py --setup-ai-key`를 실행합니다. 인증키는 로컬 `.env`에 저장합니다. 회사명과 선택 안건을 입력하고 **AI 종합 검토**를 눌렀을 때만 OpenAI API를 호출합니다. 공시 발췌와 안건이 OpenAI로 전송되며 토큰 사용료는 등록한 API 키의 계정에 청구됩니다. 기본 모델은 `gpt-5-mini`이고 `OPENAI_MODEL`로 변경할 수 있습니다. PDF 저장은 기존 AI 검토 결과를 15분 동안 재사용합니다. [OpenAI API 요금](https://openai.com/api/pricing/)

## 구성

- `server.py` · 기업 고유번호 탐색, 페이지 단위 공시 조회, PDF 생성
- `ai_review.py` · OpenAI API 요청과 검토 결과 형식
- `dist/` · 보고서 화면, 공시 검토본, 인쇄 디자인
- `examples/` · 공개 공시에 근거한 검토 예시
