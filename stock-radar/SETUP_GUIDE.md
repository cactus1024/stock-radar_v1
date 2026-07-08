# 주식레이더 셋업 가이드 (비개발자용)

> 이 문서 하나만 따라하면 "매일 자동으로 업데이트되는 주식 대시보드"가 완성됩니다.
> 예상 소요 시간: 약 30~40분 (한 번만 하면 끝)
> 월 비용: 약 $3~5 (Gemini API) + 호스팅 $0

---

## 전체 흐름 (한눈에)

```
[1회 셋업]
GitHub 계정 → 저장소 생성 → 파일 업로드 → API 키 등록 → Pages 켜기

[매일 자동]
16:10 KST 자동 실행:
  시세 수집 → Top30 분석 → AI 피드(Gemini) → 페이지 빌드 → 자동 배포
```

**당신이 매일 할 일: 없음. 페이지만 열어보면 됩니다.**

---

## 사전 준비물 (확인 체크리스트)

- [ ] GitHub 계정 (없으면 https://github.com 에서 무료 가입)
- [ ] Google AI Studio API 키 (아래 STEP 0에서 발급 방법 안내)
- [ ] 웹 브라우저 (크롬 권장)

---

## STEP 0: Gemini API 키 확인/발급

> 이미 API 키가 있다면 이 단계는 건너뛰세요.

1. https://aistudio.google.com/apikey 접속
2. Google 계정으로 로그인
3. **"API 키 만들기"** (또는 "Create API key") 클릭
4. 프로젝트 선택 (기존 것 또는 새로 생성)
5. 생성된 키를 **메모장에 임시 복사** (나중에 GitHub에 넣을 것)

⚠️ **주의:** API 키는 비밀번호와 같습니다. 카카오톡, SNS 등에 절대 공유하지 마세요.

### API 키가 유료 티어인지 확인하는 방법

Gemini 3.1 Pro는 무료 티어에서 사용할 수 없습니다:
1. https://aistudio.google.com 에서 좌측 메뉴 → "Settings" 또는 "설정"
2. "Billing" 또는 "결제" 섹션에서 결제 수단이 연결되어 있는지 확인
3. 연결되어 있으면 유료 티어 → 정상 사용 가능
4. 연결 안 되어 있으면 → Google Cloud Console에서 결제 계정 연결 필요
   (Google AI Pro 구독과 별개입니다. API 사용료는 종량제로 별도 청구됩니다.)

---

## STEP 1: GitHub 저장소 만들기

1. https://github.com 로그인
2. 우측 상단 **"+"** 버튼 → **"New repository"** 클릭
3. 설정:
   - Repository name: `stock-radar` (원하는 이름으로 변경 가능)
   - Description: `주식레이더 자동 대시보드` (선택)
   - **Public** 선택 (GitHub Pages 무료 사용을 위해)
   - ✅ "Add a README file" 체크
4. **"Create repository"** 클릭

---

## STEP 2: 파일 업로드

### 방법 A: 한 번에 업로드 (권장)

1. 이 가이드와 함께 받은 프로젝트 폴더(stock-radar)를 PC에 준비
2. GitHub 저장소 페이지에서 **"Add file"** → **"Upload files"** 클릭
3. stock-radar 폴더 안의 모든 파일/폴더를 드래그앤드롭
4. 하단 "Commit changes" 클릭

⚠️ **중요:** `.github` 폴더는 숨김 폴더라 보이지 않을 수 있습니다.
   이 경우 방법 B를 사용하세요.

### 방법 B: 파일을 하나씩 만들기 (확실한 방법)

GitHub 웹에서 직접 파일을 생성합니다.

**파일 1: requirements.txt**
1. 저장소 페이지 → "Add file" → "Create new file"
2. 파일 이름: `requirements.txt`
3. 내용 복사 붙여넣기:

```
pykrx==1.0.45
pandas>=2.0.0
jinja2>=3.1.0
google-genai>=1.0.0
```

4. 하단 "Commit changes" 클릭

**파일 2: scripts/fetch.py**
1. "Add file" → "Create new file"
2. 파일 이름: `scripts/fetch.py` (슬래시를 입력하면 자동으로 폴더가 생김)
3. fetch.py의 전체 내용을 복사 붙여넣기
4. "Commit changes" 클릭

**파일 3: scripts/analysis.py**
- 같은 방식으로 `scripts/analysis.py` 생성

**파일 4: scripts/feed.py**
- 같은 방식으로 `scripts/feed.py` 생성

**파일 5: scripts/build.py**
- 같은 방식으로 `scripts/build.py` 생성

**파일 6: .github/workflows/update.yml**
1. "Add file" → "Create new file"
2. 파일 이름: `.github/workflows/update.yml`
   (점(.)으로 시작! 슬래시 2번 입력해서 3단계 폴더가 됨)
3. update.yml 내용 전체 복사 붙여넣기
4. "Commit changes" 클릭

**파일 7: data/.gitkeep**
1. "Add file" → "Create new file"
2. 파일 이름: `data/.gitkeep`
3. 내용은 비워둠 (빈 파일)
4. "Commit changes" 클릭

**파일 8: docs/.gitkeep**
- 같은 방식으로 `docs/.gitkeep` 생성

---

## STEP 3: API 키를 GitHub에 안전하게 등록

API 키는 코드에 직접 넣지 않고, GitHub의 "비밀 금고(Secrets)"에 넣습니다.

1. 저장소 페이지 → 상단 **"Settings"** 탭 클릭
2. 좌측 메뉴에서 **"Secrets and variables"** → **"Actions"** 클릭
3. **"New repository secret"** 버튼 클릭
4. 설정:
   - Name: `GEMINI_API_KEY` (정확히 이 이름으로!)
   - Secret: STEP 0에서 복사한 API 키 붙여넣기
5. **"Add secret"** 클릭

✅ 이제 API 키는 암호화되어 저장됩니다. 누구도 볼 수 없고,
   GitHub Actions가 실행될 때만 자동으로 불러옵니다.

---

## STEP 4: GitHub Pages 켜기 (무료 웹 호스팅)

1. 저장소 → **"Settings"** 탭
2. 좌측 메뉴에서 **"Pages"** 클릭
3. Source: **"Deploy from a branch"** 선택
4. Branch: **"main"** 선택, 폴더: **"/docs"** 선택
5. **"Save"** 클릭

📌 1~2분 후 페이지 주소가 표시됩니다:
`https://[당신의GitHub아이디].github.io/stock-radar/`

> 아직 데이터가 없어서 빈 페이지이거나 404가 뜰 수 있습니다.
> STEP 5에서 첫 실행을 하면 정상적으로 보입니다.

---

## STEP 5: 첫 번째 수동 실행 (테스트)

자동 스케줄을 기다리지 않고 바로 테스트합니다.

1. 저장소 → 상단 **"Actions"** 탭 클릭
2. 좌측에 **"Stock Radar Daily Update"** 클릭
3. 우측 **"Run workflow"** 버튼 → **"Run workflow"** 확인 클릭
4. 노란 동그라미가 돌다가 초록 체크(✅)가 되면 성공!

### 실행 시간

- 전체 약 2~3분 소요
- 1단계(시세 수집): ~30초
- 2단계(분석): ~5초
- 3단계(AI 피드): ~60~90초 (Gemini API 호출)
- 4단계(HTML 빌드): ~3초
- 5단계(커밋/푸시): ~10초

### 성공 확인

- Actions 탭에서 초록 체크(✅) 확인
- `https://[아이디].github.io/stock-radar/` 접속 → 페이지 표시 확인

### ⚠️ 빨간 X(❌)가 뜨면?

1. 실패한 워크플로우 클릭 → 실패한 단계 클릭
2. 빨간 로그를 읽어보기
3. 흔한 원인과 해결법:

| 증상 | 원인 | 해결 |
|------|------|------|
| `ModuleNotFoundError: pykrx` | requirements.txt 누락/오타 | 파일 내용 재확인 |
| `GEMINI_API_KEY 환경변수 없음` | 시크릿 미등록 | STEP 3 다시 진행 |
| `403 Forbidden` (push 실패) | 권한 부족 | update.yml의 `permissions: contents: write` 확인 |
| 데이터 없음 (주말 실행) | 휴장일 → 정상 동작 | 월~금에 재실행 |
| `Quota exceeded` | API 한도 초과 | 잠시 후 재시도, 또는 결제 티어 확인 |
| JSON 파싱 실패 | Gemini 출력 불안정 | 재실행하면 보통 해결 (feed.py 폴백이 있어 페이지는 뜸) |

4. 해결이 안 되면 → 빨간 로그 전체를 복사해서 Claude에게 붙여넣기

---

## STEP 6: 자동화 확인

STEP 5까지 성공했다면, 이제 **매일 16:10 KST에 자동 실행**됩니다.

### 확인 방법
- 다음 날(평일) 16:30쯤 → Actions 탭에서 자동 실행 기록 확인
- 페이지에서 "데이터 기준" 시각이 오늘 날짜인지 확인

### 알아둘 것
- GitHub Actions 스케줄은 정각 실행이 보장되지 않습니다 (보통 5~15분 지연)
- 주말·공휴일에도 cron은 돌지만, fetch.py가 데이터 없음을 감지하고 자동 중단합니다
  → 불필요한 API 호출 없음, 비용 0원
- 60일간 저장소에 변화가 없으면 GitHub이 스케줄을 자동 중지할 수 있습니다
  → 평일마다 자동 커밋이 생기므로 보통 해당 없음

---

## 완성 후 폴더 구조

```
stock-radar/
├── .github/
│   └── workflows/
│       └── update.yml        ← 자동화 스케줄 (건드릴 일 없음)
├── scripts/
│   ├── fetch.py              ← 시세 수집
│   ├── analysis.py           ← Top30 + 섹터 분석
│   ├── feed.py               ← Gemini AI 피드 생성
│   └── build.py              ← HTML 페이지 빌드
├── data/                     ← 매일 자동 생성되는 JSON (건드릴 일 없음)
│   ├── raw_market.json
│   ├── top30.json
│   ├── feed.json
│   └── sector_history.json
├── docs/
│   └── index.html            ← 이게 실제 웹페이지 (자동 생성)
├── requirements.txt          ← 의존성 목록
└── README.md
```

**규칙: scripts/ 폴더만 수정하면 됩니다. data/와 docs/는 자동 생성이니 건드리지 마세요.**

---

## 비용 요약 (월간)

| 항목 | 비용 | 설명 |
|------|------|------|
| Gemini 3.1 Pro API | ~$3~5 | 평일 21일 × 1회 호출 |
| Google 검색 그라운딩 | $0 | 월 5,000회 무료 (21회만 사용) |
| GitHub Actions | $0 | 공개 저장소 무료 |
| GitHub Pages | $0 | 정적 사이트 무료 호스팅 |
| **합계** | **~$3~5/월** | 약 4,000~6,500원 |

---

## 배포 전 최종 체크리스트

### 필수 확인
- [ ] GitHub 저장소가 Public으로 설정됨
- [ ] 파일 8개 모두 올바른 경로에 존재함
- [ ] GEMINI_API_KEY 시크릿이 등록됨
- [ ] GitHub Pages가 main 브랜치 /docs 폴더로 설정됨
- [ ] Actions 탭에서 수동 실행(Run workflow) 1회 성공 (초록 체크)
- [ ] 페이지 URL 접속 시 대시보드가 정상 표시됨

### 선택 확인
- [ ] 모바일(핸드폰)에서 페이지 열어서 레이아웃 확인
- [ ] Top10 카드의 분석 내용이 올바른지 눈으로 확인
- [ ] 11~30위 아코디언 클릭 시 상세 내용이 펼쳐지는지 확인
- [ ] 섹터 흐름 탭에 오늘/요일별 요약이 표시되는지 확인

---

## 문제가 생겼을 때

1. **Actions 실패 로그를 Claude에게 그대로 복사 붙여넣기**
   → "이 GitHub Actions 로그에서 오류를 찾아줘" 라고 하면 됩니다.

2. **페이지가 안 뜨면**
   → Settings → Pages에서 "Your site is live at..." 링크 확인
   → 없으면 source 설정이 잘못된 것

3. **데이터가 어제 것이면**
   → Actions 탭에서 오늘 실행 기록 확인
   → 실패했으면 로그 확인 후 "Run workflow"로 수동 재실행

---

## 다음 단계 (v1 안정화 이후)

이 개인용 v1이 1~2주 안정적으로 돌아간 후:

1. **피드 품질 개선**: Gemini 프롬프트를 Claude에게 검토 받아 개선
2. **디자인 업그레이드**: Claude Code로 HTML/CSS 수정
3. **수익형 v2 설계**: 개인용 운영 경험을 기반으로 새 프로젝트 기획
4. **생활정보 페이지**: 같은 파이프라인 구조를 복사해 새 주제로 확장
