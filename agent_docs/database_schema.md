# Data Structure & Schema Documentation

이 프로젝트는 RDBMS(직접 저장용)를 사용하지 않으며, **JSON 파일**과 **Pickle(Binary) 파일**을 통해 데이터와 설정을 관리합니다. 단, 특정 분류 로직을 위해 **외부 NMS MySQL DB**를 참조합니다.

## 1. JSON Configuration Files

### 1.1 `prov_info.json` (Staff & Role Management)
직원 정보, 업무 역할, 휴가 및 야간 근무 현황을 저장합니다.
* **File Path**: `[Config defined]/prov_info.json`
* **Structure**:
  | Key | Type | Description | Example |
  | :--- | :--- | :--- | :--- |
  | `업무구분` | Array[Str] | 업무 카테고리 목록 | `["방화벽", "LAN", ...]` |
  | `CI` | Object | 업무별 CI 가중치/점수 매핑 | `{"방화벽": 5, "LAN": 1}` |
  | `방화벽` | Array[Str] | 방화벽 업무 담당자 목록 | `["홍길동", "이철수"]` |
  | `참가기관` | Array[Str] | 참가기관 업무 담당자 목록 | `[...]` |
  | `수익사업` | Array[Str] | 수익사업 업무 담당자 목록 | `[...]` |
  | `대외기관` | Array[Str] | 대외기관 업무 담당자 목록 | `[...]` |
  | `LAN` | Array[Str] | LAN 업무 담당자 목록 | `[...]` |
  | `인터넷` | Array[Str] | 인터넷 업무 담당자 목록 | `[...]` |
  | `야간` | Array[Str] | 현재 야간 근무자 목록 | `["박근영"]` |
  | `휴가` | Array[Str] | 현재 휴가자 목록 | `["남택호"]` |
  | `결재권자` | Array[Str] | 결재 승인 권한자 | `["팀장명"]` |
  | `확인자` | Array[Str] | 참조/확인자 | `["부팀장명"]` |
  | `백업` | Array[Str] | 백업 담당자 목록 | `[]` |

### 1.2 `ITSM_AUTO_RECEIVER_classification_conditiions.json` (Classification Rules)
요청 내용을 분석하여 업무 유형을 분류하는 규칙 정의입니다.
* **File Path**: `[Config defined]/classification_conditions.json`
* **Root**: `conditions` (Array of Objects)
* **Rule Object Fields**:
  | Field | Type | Description |
  | :--- | :--- | :--- |
  | `name` | String | 규칙 이름 (식별자) |
  | `keys` | Array[Str] | 검사할 필드 목록. 특수 키 `iptable_memo` 포함 가능. |
  | `table_keys` | Array[Str] | (Optional) 테이블 데이터 내 검사할 컬럼명 (예: `Real IP`, `도메인명`) |
  | `title` | Array[Str] | (Optional) 제목에 포함되어야 할 키워드 (OR 조건) |
  | `iptable_memo` | Array[Str] | **[v1.1.8 New]** NMS DB 조회 키워드. IP 조회 후 Memo 필드에 해당 패턴(예: `*VAN*`) 포함 여부 확인. |
  | `include_keywords` | Array[Str] | (Optional) 반드시 포함되어야 할 키워드 (AND 조건) |
  | `exclude_keywords` | Array[Str] | (Optional) 포함되면 안 되는 키워드 |
  | `regex` | String | (Optional) 정규표현식 매칭 패턴 |
  | `menu` | Array[Str] | **[Result]** 매칭 시 분류 결과 `[요청유형, 업무구분]` |
  | `[DynamicKey]` | Array[Str] | `keys`나 `table_keys`에 정의된 필드의 매칭 값 목록 (IP CIDR, 도메인 등) |

### 1.3 `restinfo.json` (Holidays)
휴일 정보를 관리하여 접수 자동 종료 등을 제어합니다.
* **Structure**: `{"restdays": ["20230101", "20230121", ...]}`

## 2. Pickle Binary Files

### 2.1 `network_prov_info.bin`
* **Description**: SFTP를 통해 구글 시트 등 외부 소스와 동기화되는 직원/휴가 정보의 캐시 파일.
* **Fields**: `update` (Date String), `timeoff` (Vacation list), `provInfo` (Full Prov Info object), `nightworker` (List).

### 2.2 `network_calendar.bin`
* **Description**: 네트워크 팀 캘린더/일정 정보.

## 3. External Data Sources

### 3.1 NMS Database (MySQL)
* **Usage**: `iptable_memo` 조건 검사 시 IP 주소의 속성을 확인하기 위해 조회.
* **Connection**: `NMS_API` 모듈 사용 (망별 IP/Port 설정).
* **Target Table**: `kftc_nms_ip`
  * `ipaddress`: 조회 조건 (WHERE 절).
  * `memo`: 조회 대상. 패턴 매칭 수행.