# ITSM Request Auto Submission (v1.1.7)

## Project Purpose
ITSM 포털의 결재 및 접수 프로세스를 자동화하는 Python 데몬입니다. Playwright를 사용하여 웹 UI를 제어하고, JSON 규칙에 따라 요청을 분류하며, 직원 근무 상태(휴가/야간)를 반영하여 동적으로 결재선을 수정합니다.

## Tech Stack
* **Language**: Python 3.13.2
* **Core Library**: `playwright` (Async Web Automation)
* **Concurrency**: `asyncio`, `aiofiles`
* **Remote Sync**: `asyncssh` (SFTP Client)
* **System**: `win32api`, `win32con`, `win32timezone` (Windows Integration)
* **Configuration**: `configparser` (INI), `json`, `pickle`

## Core Commands
* **Run Script**:
    ```bash
    python ITSM_Request_Auto_Submission.py
    ```
* **Install Dependencies**:
    ```bash
    pip install playwright asyncssh aiofiles pywin32
    playwright install chromium
    ```

## Documentation Map
* **Data Structure**: See `agent_docs/database_schema.md` (JSON Rules & Staff Info)
* **Business Logic**: See `agent_docs/project_context.md` (Workflows, Classification, & Approval Logic)
* **Logging Standards**: See `agent_docs/logging_standard.md` (Async Logger & Reference Standard)

## Guidelines
* **Async First**: 모든 I/O 작업(파일, 네트워크, 브라우저)은 `async`/`await`를 사용하여 메인 루프가 차단되지 않도록 해야 합니다.
* **Browser Context**: `playwright` 사용 시 페이지 로딩(`networkidle`) 및 요소 대기(`wait_for_selector`)를 철저히 처리하여 타이밍 이슈를 방지하십시오.
* **Error Handling**: 웹 자동화 특성상 예외 발생이 잦으므로, `try-except` 블록 내에서 `traceback`을 사용하여 로그를 상세히 기록하십시오.
* **Logging**: 기존 `writelog` 함수(Async)를 사용하십시오.
