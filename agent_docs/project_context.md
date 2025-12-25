# Project Context & Business Logic

## 1. Project Overview
ITSM 포털의 요청(접수/결재)을 자동화하는 Python 데몬 스크립트입니다. `Playwright`를 사용하여 브라우저를 제어하며, 비동기(`asyncio`)로 동작하여 UI 응답 대기와 백그라운드 작업(SFTP 동기화, 파일 감시)을 동시에 처리합니다.

## 2. Core Workflows

### 2.1 Initialization & Environment
* **Network Detection**: 호스트명을 기반으로 망(업무망, 중요망, 인터넷망)을 식별하고 SFTP 서버 IP를 결정합니다.
* **Config Loading**: `.ini` 파일 및 JSON/Pickle 데이터를 비동기로 로드합니다.
* **Browser Launch**: Chromium 브라우저를 실행하고 자동 로그인을 수행합니다. (비밀번호 변경 팝업 자동 회피 로직 포함)

### 2.2 Polling Loop (`periodic_task`)
* **Login Check**: 세션 만료 시 자동 재로그인.
* **Approval Scanning (`fetch_approval_list`)**: '결재함'을 확인하여 일괄 결재 처리.
* **Reception Scanning (`fetch_receive_list`)**: '나의 할일' 목록을 확인하여 신규 접수 건 처리.

### 2.3 Request Classification Logic
`analyze_request` 함수에서 수행하며, 다음 순서로 판단합니다:
1. 요청 상세 페이지 파싱 (Table Data 및 Field Data 추출).
2. `classification_conditions.json` 규칙 순회.
3. **Keyword Matching**: 제목, 내용 등 텍스트 키워드 매칭.
4. **Table Data Matching**: IP 주소 범위(`ipaddress` 모듈 사용) 또는 도메인명 매칭.
5. 매칭 성공 시 `[요청유형(일반/변경), 업무구분]` 반환.

### 2.4 Auto-Approval & Modification Logic
* **Validation**: 분류 실패 시 `failClassifcation` 리스트에 추가하고 로그 기록.
* **Deadline Extension**: 마감 기한(`is_deadline_past`)이 지난 경우, 자동으로 '1개월 후'로 기한 조정 요청을 수행.
* **Reject Check**: 반려 이력(히스토리맵/이관반려 탭)이 있는 경우 자동 반려 처리.
* **Approval Line Update**:
  * `prov_info.json`의 정보를 바탕으로 결재자/참조자 리스트 생성.
  * **Worker Selection (`selWorker`)**: 휴가자(`휴가`), 야간근무자(`야간`)를 제외하고 가용한 담당자를 선택.
  * Playwright로 결재선 UI를 조작하여 담당자 변경 및 결재 상신.

## 3. Data Synchronization
* **SFTP Sync**: 별도의 `prov_update_task`가 주기적으로 실행됨.
* **Mechanism**: 원격 서버의 `network_prov_info.bin` 등을 다운로드하여 로컬 정보 업데이트. 변경 사항 발생 시 로그 기록.

## 4. Key Constraints
* **Operating System**: Windows (Win32 API 사용).
* **Browser**: Chromium (Playwright).
* **Concurrency**: `asyncio` 기반 단일 스레드 이벤트 루프 사용. 로그 기록 시 `asyncio.Lock` 사용.