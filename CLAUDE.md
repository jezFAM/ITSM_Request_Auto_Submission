# ITSM Request Auto Submission (v1.1.8)

## Project Purpose
ITSM 포털의 결재 및 접수 프로세스를 자동화하는 Python 데몬입니다. Playwright를 사용하여 웹 UI를 제어하고, JSON 규칙 및 **NMS DB(MySQL)** 조회를 통해 요청을 정밀하게 분류하며, 직원 근무 상태를 반영하여 동적으로 결재선을 수정합니다.

## Tech Stack
* **Language**: Python 3.13.2
* **Core Library**: `playwright` (Async Web Automation)
* **Data Sources**:
  * JSON/Pickle (Config & Cache)
  * `NMS_API` (External MySQL DB Integration for IP lookup)
* **Concurrency**: `asyncio`, `aiofiles`
* **Remote Sync**: `asyncssh` (SFTP Client)
* **System**: `win32api`, `win32con` (Windows Integration)

## Core Commands
* **Run Script**:
    ```bash
    python ITSM_Request_Auto_Submission.py
    ```
* **Install Dependencies**:
    ```bash
    pip install playwright asyncssh aiofiles pywin32
    playwright install chromium
    # NMS_API module must be present in the path
    ```

## Documentation Map
* **Data Structure**: See `agent_docs/database_schema.md` (JSON Rules, Staff Info & External NMS DB)
* **Business Logic**: See `agent_docs/project_context.md` (Workflows, NMS Classification, & Approval Logic)
* **Logging Standards**: See `agent_docs/logging_standard.md` (Async Logger)

## Guidelines
* **Async First**: 모든 I/O 작업(파일, 네트워크, 브라우저, DB)은 메인 루프가 차단되지 않도록 주의하십시오.
* **NMS Integration**: `NMS_API` 호출 시 블로킹 가능성이 있으므로, 타임아웃 및 예외 처리를 철저히 하십시오.
* **Browser Context**: `playwright` 요소 대기(`wait_for_selector`)를 사용하여 타이밍 이슈를 방지하십시오.
* **Error Handling**: `try-except` 블록 내에서 `traceback`을 사용하여 로그를 상세히 기록하십시오.
