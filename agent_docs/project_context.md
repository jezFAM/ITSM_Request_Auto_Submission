# Project Context & Business Logic

## 1. Project Overview
ITSM 포털의 요청(접수/결재)을 자동화하는 Python 데몬 스크립트입니다. `Playwright`를 사용하여 브라우저를 제어하며, 비동기(`asyncio`)로 동작하여 UI 응답 대기와 백그라운드 작업(SFTP 동기화, 파일 감시)을 동시에 처리합니다.
NMS DB와 연동하여 IP 기반의 정밀한 업무 분류가 가능해졌습니다.

## 2. Core Workflows

### 2.1 Initialization & Environment
* **Network Detection**: 호스트명을 기반으로 망(업무망, 중요망, 인터넷망)을 식별합니다.
  * 이에 따라 **SFTP 서버 IP**와 **NMS DB 접속 정보**(`NmsInfo`)가 결정됩니다.
* **Config Loading**: `.ini` 파일 및 JSON/Pickle 데이터를 비동기로 로드합니다.
* **Browser Launch**: Chromium 브라우저를 실행하고 자동 로그인을 수행합니다.

### 2.2 Polling Loop (`periodic_task`)
* **Login Check**: 세션 만료 시 자동 재로그인.
* **Approval Scanning (`fetch_approval_list`)**: '결재함'을 확인하여 일괄 결재 처리.
* **Reception Scanning (`fetch_receive_list`)**: '나의 할일' 목록을 확인하여 신규 접수 건 처리.

### 2.3 Request Classification Logic
`analyze_request` 함수에서 수행하며, 다음 순서로 판단합니다:

1. **Page Parsing**: 요청 상세 페이지의 Field Data 및 Table Data 추출.
2. **Rule Iteration**: `classification_conditions.json` 규칙 순회.
3. **NMS DB Lookup (`iptable_memo` Key)**:
   * 규칙에 `iptable_memo` 키가 포함된 경우 실행.
   * Table Data에서 IP 주소를 추출.
   * `NMS_API.DB_Query`를 통해 외부 MySQL DB(`kftc_nms_ip`) 조회.
   * 조회된 `memo` 필드에 규칙의 패턴(예: `*VAN*`)이 포함되는지 검사 (Wildcard 지원).
4. **Keyword/Data Matching**: 제목, 내용 텍스트 키워드 및 Table Data(IP 범위, 도메인) 매칭.
5. **Result**: 모든 조건 만족 시 `[요청유형(일반/변경), 업무구분]` 반환.

### 2.4 Auto-Approval & Modification Logic
* **Validation**: 분류 실패 시 로그 기록.
* **Deadline Extension**: 마감 기한 경과 시 자동 연장 요청.
* **Reject Check**: 반려 이력 확인 시 자동 반려 처리.
* **Approval Line Update**:
  * `prov_info.json` 기반 결재자/참조자 생성.
  * **Worker Selection**: 휴가/야간/백업 담당자를 고려하여 가용한 담당자 자동 선택(`selWorker`).
  * Playwright로 UI 조작하여 결재선 반영.

## 3. Data Synchronization
* **SFTP Sync**: `prov_update_task`가 원격 서버의 `network_prov_info.bin` 등을 다운로드하여 로컬 정보 업데이트.

## 4. Key Constraints
* **Operating System**: Windows (Win32 API 사용).
* **Browser**: Chromium (Playwright).
* **Dependencies**: `NMS_API` 모듈(DB 연결) 필수.