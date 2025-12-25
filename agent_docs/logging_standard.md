# Logging Standards

본 프로젝트는 비동기 환경(`asyncio`)에서 동작하므로, 파일 I/O 차단을 방지하기 위해 `aiofiles`를 사용하는 커스텀 로깅 방식을 사용합니다.

## 1. Project-Specific Logging (`writelog`)

이 프로젝트의 메인 로깅 함수입니다. 스크립트 실행 디렉토리에 로그를 기록하며, 자동 회전(Log Rotation)을 지원합니다.

* **Logic**:
    * Async Write (Non-blocking).
    * Log Rotation: 1MB 초과 시 백업 파일(`.1` ~ `.5`) 생성.
    * Thread-safety: `asyncio.Lock` 사용.
    * Format: `YYYY.MM.DD. HH:MM:SS\t{Message}`

```python
# [Current Implementation in ITSM_Request_Auto_Submission.py]
# 글로벌 로그 락
log_lock = Lock()

async def writelog(log):
    global scriptInfo
    d = datetime.now()
    log_file = Path(scriptInfo.dir_path, f'{scriptInfo.script_name}.log')
    msg = f"{d.strftime('%Y.%m.%d. %H:%M:%S')}\t{log}"

    try:
        # Log Rotation Logic (Simplified)
        if log_file.exists() and log_file.stat().st_size > 1024 * 1024:
            # ... rotation implementation ...
            pass
            
        async with log_lock:
            async with aiofiles.open(log_file, 'a', encoding='utf-8') as f:
                await f.write(msg + '\n')
    except Exception as e:
        print(traceback.format_exc())

```

## 2. Notice Logging (`write_notice`)

중요 알림 로그는 로컬 기록 후 **SFTP로 즉시 업로드**합니다.

* **Logic**: 로컬 파일 쓰기 -> SFTP Upload -> 관리자 알림용.

## 3. Reference: Synchronous Logger Standard

향후 동기식 모듈을 추가하거나 표준 라이브러리 로깅으로 마이그레이션할 경우 아래 표준을 참고하십시오.

```python
# [Standard Reference Snippet]
import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logger(name, log_file, file_level=logging.INFO, console_level=logging.DEBUG, max_size=1024*1024, backup_count=5):
    """로그 설정 함수 - 파일과 콘솔에 다른 레벨 적용 가능"""
    # Windows 환경인지 확인하여 적절한 날짜 형식 지정
    datefmt = '%Y.%#m.%#d. %H:%M:%S'  # Windows에서는 앞의 0 제거

    # 파일 핸들러 설정
    file_handler = RotatingFileHandler(
        log_file, maxBytes=max_size, backupCount=backup_count, encoding='utf-8')
    formatter = logging.Formatter(
        '%(asctime)s\t[%(levelname)s]\t%(message)s', datefmt=datefmt)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(file_level)

    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(console_level)

    # 로거 설정
    logger = logging.getLogger(name)
    logger.setLevel(min(file_level, console_level))
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Path Utils
script_path = os.getcwd()
script_name = os.path.basename(__file__).split(".")[0]

```