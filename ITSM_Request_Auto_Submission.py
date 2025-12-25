from __future__ import annotations
import win32timezone  # 명시적으로 import 추가
import win32api
import win32con
import os
import traceback
import sys
import time
import re
import socket
import threading
import ctypes
import ctypes.wintypes
import json
import configparser
import urllib3
import asyncio
import pickle
import asyncio
import aiofiles
import asyncssh
import subprocess
import ipaddress

from asyncio import Lock
from playwright.async_api import async_playwright, TimeoutError
from playwright.async_api import Error as PlaywrightError

from pprint import pprint
from collections import defaultdict
from typing import List
from dataclasses import dataclass, field

import asyncio

from pathlib import Path
from datetime import datetime
from dateutil.relativedelta import relativedelta
from ast import literal_eval

from bs4 import BeautifulSoup as bs
from urllib import parse

# 한글깨짐 처리
os.putenv('NLS_LANG', 'KOREAN_KOREA.KO16KSC5601')

# InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def set_console_size(lines, columns, buffer):
    # STD_OUTPUT_HANDLE의 핸들을 얻어옵니다.
    # -11은 STD_OUTPUT_HANDLE을 의미합니다.
    h_out = ctypes.windll.kernel32.GetStdHandle(-11)

    # 현재 콘솔 창 정보를 가져옵니다.
    csbi = ctypes.create_string_buffer(22)
    res = ctypes.windll.kernel32.GetConsoleScreenBufferInfo(h_out, csbi)
    if res == 0:
        raise OSError("Failed to get console screen buffer info.")

    # 현재 콘솔 창의 크기와 스크롤 버퍼를 변경합니다.
    buf_size = ctypes.wintypes._COORD(columns, buffer)
    ctypes.windll.kernel32.SetConsoleScreenBufferSize(h_out, buf_size)

    window_size = ctypes.wintypes._SMALL_RECT(0, 0, columns - 1, lines - 1)
    ctypes.windll.kernel32.SetConsoleWindowInfo(
        h_out, True, ctypes.byref(window_size))


# 예시: 콘솔 창 크기를 높이 30, 가로 90, 스크롤 버퍼를 90으로 설정
set_console_size(lines=60, columns=90, buffer=90)
# os.system("mode con: cols=90 lines=90")

# 팝업


def Mbox(title, text, mbType=0):
    '''
    MB_ABORTRETRYIGNORE = 2
    MB_CANCELTRYCONTINUE = 6
    MB_HELP = 0x4000
    MB_OK = 0
    MB_OKCANCEL = 1
    MB_RETRYCANCEL = 5
    MB_YESNO = 4
    MB_YESNOCANCEL = 3
    '''

    MB_ICONEXCLAMATION = MB_ICONWARNING = 0x30
    MB_ICONINFORMATION = MB_ICONASTERISK = 0x40
    MB_ICONQUESTION = 0x20
    MB_ICONSTOP = MB_ICONERROR = MB_ICONHAND = 0x10

    MB_DEFBUTTON1 = 0
    MB_DEFBUTTON2 = 0x100
    MB_DEFBUTTON3 = 0x200
    MB_DEFBUTTON4 = 0x300

    MB_APPLMODAL = 0
    MB_SYSTEMMODAL = 0x1000
    MB_TASKMODAL = 0x2000

    MB_DEFAULT_DESKTOP_ONLY = 0x20000
    MB_RIGHT = 0x80000
    MB_RTLREADING = 0x100000

    MB_SETFOREGROUND = 0x10000
    MB_TOPMOST = 0x40000
    MB_SERVICE_NOTIFICATION = 0x200000
    return ctypes.windll.user32.MessageBoxW(0, text, title, MB_ICONINFORMATION | mbType | MB_SYSTEMMODAL | MB_TOPMOST)


def Select_Mbox(title, text, resultList, mbType=1):
    '''
    OKCANCEL = 1
    YESNO = 4
    YESNOCANCEL = 3
    '''
    IDYES = 6
    IDNO = 7
    IDCANCEL = 2

    response = Mbox(title, text, mbType)
    if response == IDYES:
        resultList[0] = 'YES'
    elif response == IDNO:
        resultList[0] = 'NO'
    elif response == IDCANCEL:
        resultList[0] = 'CANCEL'
    else:
        resultList[0] = response


class ExcThread(threading.Thread):
    '''
    쓰레드 실행 함수
    '''

    def excRun(self):
        if hasattr(self, '_Thread__target'):
            # Thread uses name mangling prior to Python 3.
            self.ret = self._Thread__target(
                *self._Thread__args, **self._Thread__kwargs)
        else:
            self.ret = self._target(*self._args, **self._kwargs)

    def run(self):
        self.exc = None
        try:
            # Possibly throws an exception
            self.excRun()
        except:
            self.exc = sys.exc_info()
            # Save details of the exception thrown but don't rethrow,
            # just complete the function

    def join(self):
        threading.Thread.join(self)
        if self.exc:
            msg = "Thread '%s' threw an exception: %s" % (
                self.name, self.exc[1])
            new_exc = Exception(msg)
            raise new_exc.with_traceback(self.exc[2])


# 글로벌 로그 파일 락 생성
log_lock = Lock()
max_log_size = 1024 * 1024  # 10 MB
backup_count = 5


async def writelog(log):
    '''
    비동기 로그 기록 함수
    log : 기록할 log 메세지
    '''
    global scriptInfo

    d = datetime.now()
    log_file = Path(scriptInfo.dir_path, f'{scriptInfo.script_name}.log')
    msg = f"{d.strftime('%Y.%m.%d. %H:%M:%S')}\t{log}"

    try:
        # 로그 파일 롤링
        if log_file.exists() and log_file.stat().st_size > max_log_size:
            # 가장 오래된 로그 파일 삭제
            oldest_log = log_file.with_suffix(f'.{backup_count}')
            if oldest_log.exists():
                oldest_log.unlink()
            for i in range(backup_count - 1, 0, -1):
                old_log_file = log_file.with_suffix(f'.{i}')
                if old_log_file.exists():
                    old_log_file.rename(log_file.with_suffix(f'.{i + 1}'))
            log_file.rename(log_file.with_suffix('.1'))

        # 로그 파일에 안전하게 쓰기 위해 락을 사용
        async with log_lock:
            async with aiofiles.open(log_file, 'a', encoding='utf-8') as f:
                await f.write(msg + '\n')
    except Exception as e:
        error_msg = f'{d.strftime("%Y.%m.%d. %H:%M:%S")}\t{
            traceback.format_exc()}'
        print(error_msg)

notice_log_lock = Lock()


async def write_notice(log):
    '''
    로그기록 함수
    log : 기록할 log 메세지
    '''
    global scriptInfo, sftpInfo

    d = datetime.now()
    log_file = Path(scriptInfo.dir_path, f'{
                    scriptInfo.script_name}_notice.log')
    msg = f"{d.strftime('%Y.%#m.%#d. %H:%M:%S')}\n{log}"
    try:
        # 로그 파일에 안전하게 쓰기 위해 락을 사용
        async with log_lock:
            async with aiofiles.open(log_file, 'w', encoding='utf-8') as f:
                await f.write(msg)

        sftpInfo.upload_sftp(log_file, f'{scriptInfo.script_name}_notice.log')
    except Exception as e:
        error_msg = f'{d.strftime("%Y.%m.%d. %H:%M:%S")}\t{
            traceback.format_exc()}'
        print(error_msg)

# 전역변수


@dataclass(frozen=True)
class ScriptInfo:
    cur_ver: float = field(init=False, default=1.0)
    dir_path: str = field(init=False, default=os.getcwd())
    script_name: str = field(
        init=False, default=os.path.basename(__file__).split(".")[0])


scriptInfo = ScriptInfo()


@dataclass(unsafe_hash=True, order=True)
class ConfigInfo:
    config: configparser.ConfigParser = field(default=None, init=False)

    async def async_init(self):
        global scriptInfo

        ''' 비동기 환경에서 설정 파일을 로드하는 메서드 '''
        config_file = Path(
            f'{scriptInfo.dir_path}\\{scriptInfo.script_name}.ini')
        if config_file.is_file():
            self.config = configparser.ConfigParser()
            async with aiofiles.open(config_file, 'r', encoding='utf-8') as f:
                content = await f.read()
            self.config.read_string(content)
        else:
            msg = f'{scriptInfo.script_name}.ini 파일을 찾을 수 없습니다.\n' \
                f'실행파일과 같은 폴더에 {
                scriptInfo.script_name}.ini 파일을 복사한 후 다시 실행하세요.'
            asyncio.create_task(writelog(msg, telegram=False))
            raise FileNotFoundError(msg)

    async def change_config_file(self):
        global scriptInfo

        ''' 비동기적으로 ini 파일 업데이트 '''
        async with aiofiles.open(Path(f'{scriptInfo.dir_path}\\{scriptInfo.script_name}.ini'), 'w', encoding='utf-8') as configfile:
            self.config.write(configfile)


@dataclass(unsafe_hash=True, order=True)
class ShareInfo:
    username: str = field(init=False, default='network')
    password: str = field(init=False, default='@admin1357')
    host_ip: str = None
    port: int = 0
    remote_path: str = None
    sftp: asyncssh.SFTPClient = None
    transport: asyncssh.SSHClientConnection = None

    async def create_sftp_client(self):
        '''
        sftp에 비동기 접속하는 함수
        '''
        self.transport = await asyncssh.connect(self.host_ip,
                                                port=self.port,
                                                username=self.username,
                                                password=self.password,
                                                known_hosts=None,  # 호스트 키 검증 비활성화
                                                client_keys=None   # 클라이언트 키 비활성화
                                                )
        self.sftp = await self.transport.start_sftp_client()
        return

    async def close_sftp_client(self):
        '''
        sftp 연결을 종료하는 비동기 함수
        '''
        if self.sftp:
            await self.sftp.close()
        if self.transport:
            self.transport.close()
        return

    async def is_sftp_connected(self):
        '''
        sftp 연결이 유지되고 있는지 확인하는 비동기 함수
        '''
        if self.sftp is None or self.transport is None:
            return False
        try:
            await self.sftp.stat('.')
            return True
        except (asyncssh.SFTPError, EOFError, IOError):
            return False

    async def reconnect_sftp_client(self):
        '''
        sftp 클라이언트 재연결 비동기 함수
        '''
        await self.close_sftp_client()
        await self.create_sftp_client()

    async def get_remote_mtime(self, filename):
        '''
        파일의 수정 시간을 확인하기 위한 비동기 함수
        '''
        try:
            attr = await self.sftp.stat(f'{self.remote_path}/{filename}')
            return attr.mtime
        except FileNotFoundError:
            return 0

    async def upload_sftp(self, local_file_with_path, remote_file, temp_tag='temp'):
        '''
        sftp 업로드 비동기 함수
        local_file_with_path : 업로드할 로컬 파일
        remove_file : 업로드할 파일명
        temp_tag : 업로드 시 임시로 붙일 prefix
        '''
        if not await self.is_sftp_connected():
            await self.reconnect_sftp_client()

        result = True
        temp_remote_file = f'{temp_tag}_{remote_file}'
        try:
            # Upload with temp_ prefix
            await self.sftp.put(local_file_with_path, f'{self.remote_path}/{temp_remote_file}')

            # Get the modification time of the local file
            local_mod_time = os.path.getmtime(local_file_with_path)

            # Set the modification time of the remote file to match the local file
            await self.sftp.set_mtime(f'{self.remote_path}/{temp_remote_file}', local_mod_time)

            # Rename file to remove temp_ prefix after successful upload
            try:
                await self.sftp.remove(f'{self.remote_path}/{remote_file}')
            except FileNotFoundError:
                pass
            await self.sftp.rename(f'{self.remote_path}/{temp_remote_file}', f'{self.remote_path}/{remote_file}')

        except Exception as e:
            msg = f'{traceback.format_exc()}'
            await writelog(msg)
            result = False

        return result

    async def download_sftp(self, local_file_with_path, remote_file, max_retries=3):
        '''
        sftp 파일 다운로드 비동기 함수 (재시도 포함)
        '''
        if not await self.is_sftp_connected():
            await self.reconnect_sftp_client()

        for attempt in range(max_retries):
            try:
                remote_file_info = await self.sftp.stat(f'{self.remote_path}/{remote_file}')
                remote_file_mtime = remote_file_info.mtime

                # 파일 다운로드
                await self.sftp.get(f'{self.remote_path}/{remote_file}', local_file_with_path)

                # 다운받은 파일의 수정시간 변경
                try:
                    os.utime(local_file_with_path,
                             (remote_file_mtime, remote_file_mtime))
                except (PermissionError, OSError) as e:
                    # utime 실패는 치명적이지 않음 (파일은 다운로드됨)
                    await writelog(f"파일 수정시간 변경 실패 (무시): {e}")

                return True  # 성공

            except FileNotFoundError:
                await writelog(f"파일을 찾을 수 없음: {remote_file}")
                return False  # 재시도 불필요

            except (PermissionError, OSError) as e:
                if attempt < max_retries - 1:
                    await writelog(f"파일 잠금 감지 ({attempt + 1}/{max_retries}): {e}")
                    await asyncio.sleep(2)  # 2초 대기 후 재시도
                else:
                    await writelog(f"파일 다운로드 실패 (최대 재시도 초과): {e}")
                    return False

            except Exception as e:
                await writelog(f"다운로드 중 예외: {e}")
                return False

        return False


@dataclass(unsafe_hash=True, order=True)
class ImportFileInfo:
    pickleFile: str = None
    jsonFile: str = None

    async def save_pickle(self, data: dict) -> None:
        '''
        data를 pickle 데이터로 비동기적으로 저장하는 함수
        '''
        async with aiofiles.open(self.pickleFile, 'wb') as f:
            await f.write(pickle.dumps(data))

    async def init_pickle(self) -> None:
        '''
        모든 pickle 데이터를 비동기적으로 삭제하는 함수
        '''
        data = {}
        async with aiofiles.open(self.pickleFile, 'wb') as f:
            await f.write(pickle.dumps(data))

    async def get_all_pickle(self):
        '''
        pickle 데이터를 비동기적으로 불러오는 함수
        '''
        try:
            async with aiofiles.open(self.pickleFile, 'rb') as f:
                data = await f.read()
                return pickle.loads(data)
        except FileNotFoundError:
            msg = f'{self.pickleFile} 파일이 없습니다.'
            asyncio.create_task(writelog(msg, telegram=False))
            return dict()

    async def json_to_file(self, jsonData):
        '''
        dict 값을 비동기적으로 JSON 파일로 저장
        '''
        async with aiofiles.open(self.jsonFile, 'w', encoding='utf-8') as file:
            await file.write(json.dumps(jsonData, ensure_ascii=False, indent="\t"))

    async def read_to_json(self):
        '''
        파일에서 JSON 값을 비동기적으로 읽어오는 함수
        '''
        async with aiofiles.open(self.jsonFile, 'r', encoding='utf-8') as file:
            data = await file.read()
            return json.loads(data)


@dataclass(unsafe_hash=True, order=True)
class SiteInfo:
    domain: str = None
    id: str = None
    password: str = None


@dataclass(unsafe_hash=True, order=True)
class DataInfo:
    interval: int = 0
    failClassifcation: List[int] = field(default_factory=list)
    restInfo: defaultdict[dict] = field(
        default_factory=lambda: defaultdict(dict))
    provInfo: defaultdict[dict] = field(
        default_factory=lambda: defaultdict(dict))
    provLine: defaultdict[dict] = field(
        default_factory=lambda: defaultdict(dict))
    calendarInfo: defaultdict[dict] = field(
        default_factory=lambda: defaultdict(dict))
    classification_conditions: defaultdict[dict] = field(
        default_factory=lambda: defaultdict(dict))
    weekday_reception_hours: defaultdict[dict] = field(
        default_factory=lambda: defaultdict(dict))
    reception_time_str: str = None
    reception_time_start: datetime = None
    reception_time_end: datetime = None
    vacationMember: str = None
    nightWorker: str = None
    teamManager: str = None
    prov_file_mtime: datetime = None
    prov_refresh_time: List[int] = field(default_factory=list)
    last_update_date: str = None


async def getConfig():
    '''
    스크립트 환경설정 정보를 가져오는 함수
    '''
    global scriptInfo, configInfo
    global dataInfo, network_prov_file, network_calendar_file
    global prov_info_file, classification_conditions_file, rest_info_file
    global sftpInfo, itsmInfo

    # 현재 망 선택
    hostname = socket.gethostname()
    await configInfo.async_init()

    if (hostname.find('UPMU') > -1 or hostname.find('업무') > -1 or hostname.find('NW229') > -1):
        pprint('업무망에서 실행 중')
        sel = 1
    elif (hostname.find('JungYo') > -1 or hostname.find('중요') > -1):
        pprint('중요망에서 실행 중')
        sel = 2
    elif (hostname.find('INTERNET') > -1 or hostname.find('인터넷') > -1):
        pprint('인터넷망에서 실행 중')
        sel = 3
    elif (hostname.find('file') > -1):
        pprint('파일서버에서 실행 중')
        sel = 4
    else:
        pprint('망구분이 안되서 중요망으로 실행 중')
        sel = 2
        # time.sleep(1)
        # sys.exit()

    # 환경정보 확인
    if (sel == 1):
        # 업무망
        sftpInfo.host_ip = configInfo.config['SERVER']['host_upmu']
    elif (sel == 2):
        # 중요망
        sftpInfo.host_ip = configInfo.config['SERVER']['host_jongyo']
    elif (sel == 3):
        # 인터넷망
        time.sleep(1)
        sys.exit()
    elif (sel == 4):
        # 파일서버
        sftpInfo.host_ip = configInfo.config['SERVER']['host_jongyo']

    # FILE 정보
    network_prov_file.pickleFile = configInfo.config['FILE']['network_prov_file']
    network_calendar_file.pickleFile = configInfo.config['FILE']['network_calendar_file']
    prov_info_file.jsonFile = configInfo.config['FILE']['prov_info']
    classification_conditions_file.jsonFile = configInfo.config[
        'FILE']['classification_conditions']
    rest_info_file.jsonFile = configInfo.config['FILE']['rest_info']

    # SFTP 정보
    sftpInfo.port = int(configInfo.config['SFTP']['sftp_port'])
    sftpInfo.remote_path = configInfo.config['SFTP']['remote_path']

    # ITSM 정보
    itsmInfo.domain = configInfo.config['ITSM']['itsmURL']
    itsmInfo.id = configInfo.config['ITSM']['itsmID']
    itsmInfo.password = configInfo.config['ITSM']['itsmPWD']

    # DATA 정보
    dataInfo.interval = int(configInfo.config['DATA']['interval'])
    dataInfo.classification_conditions = await classification_conditions_file.read_to_json()  # 요청분류 조건
    dataInfo.restInfo = await rest_info_file.read_to_json()  # 휴일정보
    dataInfo.provInfo = await prov_info_file.read_to_json()
    dataInfo.prov_file_mtime = datetime.fromtimestamp(
        os.path.getmtime(prov_info_file.jsonFile))
    dataInfo.weekday_reception_hours = literal_eval(
        configInfo.config['DATA']['weekday_reception_hours'])
    dataInfo.prov_refresh_time = literal_eval(
        configInfo.config['DATA']['prov_refresh_time'])

    return


def printConsole(log):
    '''
    날짜와 시간을 붙여서 콘솔에 메시지 출력
    log : 출력할 메세지
    '''
    d = datetime.now()
    msg = f"{d.strftime('%Y.%#m.%#d. %H:%M:%S')}\t{log}"
    print(f'{msg}\n')


def are_lists_equal(list1, list2):
    # 리스트를 중복제거 후 정렬하여 순서를 무시하고 비교합니다.
    sorted_list1 = sorted(list1)
    sorted_list2 = sorted(list2)

    # 정렬된 리스트끼리 비교합니다.
    return sorted_list1 == sorted_list2


async def fetch_approval_list(page):
    '''
    결재할 요청을 확인하는 함수
    '''

    # 업무함 클릭
    await page.wait_for_selector("a[title='업무함']")
    업무함_element = await page.query_selector("a[title='업무함']")
    is_expanded = await 업무함_element.get_attribute("aria-expanded")
    if is_expanded != "true":
        await 업무함_element.click()
        # 메뉴가 펼쳐질 때까지 잠시 대기
        await page.wait_for_timeout(1000)

    # 결재함 클릭
    await page.wait_for_selector("a[title='결재함']")
    await page.click("a[title='결재함']")

    # 페이지가 로드될 때까지 대기
    await page.wait_for_load_state('networkidle')

    # 결재함 목록에서 데이터를 추출
    # print("결재함 목록을 가져오는 중...")

    # 결재함 데이터를 가져옴
    # 결재함 header
    await page.wait_for_selector("div[role='columnheader']")  # 요소가 나타날 때까지 대기
    await page.wait_for_timeout(1000)
    try:
        # 체크박스가 나타날 때까지 대기 후 클릭
        checkbox_locator = page.locator('div.jqx-checkbox-default')
        first_checkbox = checkbox_locator.first
        if first_checkbox:
            await first_checkbox.click()
        else:
            return False

        # 체크박스가 모두 선택될때까지 잠시 대기
        await page.wait_for_timeout(1000)

        # 일괄결재 버튼 클릭
        await page.click('button.btn.button-lst-action[title="일괄결재"]')
        # 버튼이 클릭될떄까지 잠시 대기
        await page.wait_for_timeout(1000)

        # 팝업의 "확인" 버튼이 나타날 때까지 대기 후 클릭
        await page.wait_for_selector('button.btn.btn-default.btn-point:has-text("확인")', timeout=5000)
        confirm_button = page.locator(
            'button.btn.btn-default.btn-point:has-text("확인")').first
        await confirm_button.click()

        # print("결재함 일괄결재 완료!")

    except Exception as e:
        error_message = f"체크박스 클릭 중 오류 발생: {traceback.format_exc()}"
        await writelog(error_message)
        return False

    return True


async def fetch_receive_list(page):
    '''
    접수할 요청을 확인하는 함수
    '''

    # 업무함 클릭
    await page.wait_for_selector("a[title='업무함']")
    업무함_element = await page.query_selector("a[title='업무함']")
    is_expanded = await 업무함_element.get_attribute("aria-expanded")
    if is_expanded != "true":
        await 업무함_element.click()
        # 메뉴가 펼쳐질 때까지 잠시 대기
        await page.wait_for_timeout(1000)

    # 나의할일 클릭
    await page.wait_for_selector("a[title='나의할일']")
    await page.click("a[title='나의할일']")

    # 페이지가 로드될 때까지 대기
    await page.wait_for_load_state('networkidle')

    # 나의할일 목록에서 데이터를 추출
    # print("나의할일 목록을 가져오는 중...")

    # 나의할일 데이터를 가져옴
    # 나의할일 header
    await page.wait_for_selector("div[role='columnheader']")  # 요소가 나타날 때까지 대기
    # role이 'columnheader' 인 모든 div 선택
    columnheader_elements = await page.locator("div[role='columnheader']").element_handles()
    columnList = [await columnheader_element.inner_text() for columnheader_element in columnheader_elements]

    # 나의할일 데이터
    await page.wait_for_selector("div[role='row']")  # 요소가 나타날 때까지 대기
    # Role이 'row'인 모든 div 선택
    row_elements = await page.locator("div[role='row']").element_handles()

    # 나의할일 목록 세부내역 확인
    requests = []
    for idx, row_element in enumerate(row_elements, start=1):
        # 해당 row 요소의 하위 <span> 태그들을 가져옴
        # 각 row 내의 모든 <span> 태그 선택
        span_elements = await row_element.query_selector_all("span")

        # row 요소가 없으면 pass
        if not span_elements:
            break

        # 각 span 요소의 텍스트 가져오기
        span_texts = [await span_element.inner_text() for span_element in span_elements]

        request_data = {}
        for i, span_text in enumerate(span_texts, start=1):
            request_data[columnList[i]] = span_text

        if request_data:
            requests.append(request_data)
            # print(f"Row {idx}: {request_data}")

    return requests


async def collect_field_data(page, fields):
    """
    필드 데이터를 비동기적으로 수집하는 함수
    """
    request_data = {}
    tasks = []

    for key, selector in fields.items():
        async def get_field_value(selector, key):
            try:
                # waitForSelector 를 사용하여 요소가 나타날 때까지 대기
                # 타임아웃 설정
                element = await page.wait_for_selector(selector, state="attached", timeout=3000)
                if element:
                    # input value 시도
                    value = await element.get_attribute('value')

                    # input value가 없으면 text content 시도
                    if not value or not value.strip():
                        value = await element.text_content()

                    # 값이 있고 공백이 아닌 경우만 저장
                    if value and value.strip():
                        return key, value.strip()
            except Exception as e:
                await writelog(f"Field {key} extraction error: {str(e)}")
            return key, None

        tasks.append(get_field_value(selector, key))

    # 모든 필드 데이터 수집 완료 대기
    results = await asyncio.gather(*tasks)

    # 결과 처리
    for key, value in results:
        if value:  # None이 아닌 값만 저장
            request_data[key] = value

    return request_data


async def collect_table_data(page):
    """
    표 데이터를 비동기적으로 수집하는 함수
    """
    table_data = []

    try:
        # 헤더 영역이 나타날 때까지 대기
        await page.wait_for_selector('div.rel-header', state='attached')

        # 헤더(컬럼명) 추출
        headers = []

        # 직접 HTML 구조대로 정확한 셀렉터 사용
        header_rows = await page.query_selector_all('div.scroll-columns > div.float-l.rel-row-sub')

        for header_row in header_rows:
            try:
                # 각 헤더의 텍스트 내용 추출
                text = await header_row.evaluate('el => el.querySelector(".grid_header_lb").textContent.trim()')
                if text:
                    headers.append(text)
            except Exception as e:
                continue

        if not headers:
            await writelog("헤더를 찾을 수 없습니다")
            return []

        # 데이터 행 추출
        rows = await page.query_selector_all('div.data-area div.data')

        for row in rows:
            row_data = {}
            try:
                # 각 행의 데이터 셀 선택
                cells = await row.query_selector_all('div.scroll-columns > div.float-l.rel-row-sub-data')

                for i, cell in enumerate(cells):
                    if i >= len(headers):
                        break

                    try:
                        # relation-atom div에서 값 추출 시도
                        atom_text = await cell.evaluate('el => { const div = el.querySelector("div.relation-atom div"); return div ? div.textContent : null; }')

                        if atom_text:
                            row_data[headers[i]] = atom_text.strip()
                            continue

                        # hidden input에서 값 추출 시도
                        input_value = await cell.evaluate('el => { const input = el.querySelector("input[type=hidden]"); return input ? input.value : null; }')

                        if input_value:
                            row_data[headers[i]] = input_value.strip()
                            continue

                    except Exception as e:
                        error_message = f"Cell extraction error: {str(e)}"
                        await writelog(error_message)
                        print(error_message)  # 디버깅용
                        continue

                # 의미 있는 데이터가 있는 행만 추가
                if row_data and any(v.strip() for v in row_data.values()):
                    table_data.append(row_data)

            except Exception as e:
                print(f"Row processing error: {str(e)}")  # 디버깅용
                continue

    except Exception as e:
        error_message = f"Table data collection error:\n{
            traceback.format_exc()}"
        await writelog(error_message)
        print(error_message)  # 디버깅용

    return table_data


async def analyze_request(page, request):
    """
    요청 상세 내용을 분석하는 함수

    Args:
        page: Playwright page 객체
        request: 요청 기본 정보를 담은 dict
    Returns:
        dict: 분석된 요청 정보
    """
    try:
        # 요청 상세 페이지로 이동
        # selector와 title 속성 사용
        await page.locator(f'div[title="{request['요청 ID']}"]').click()

        # 페이지 로딩 완료 대기
        await page.wait_for_load_state('networkidle')

        # 필드 정의
        fields = {
            'request_id': '#Field_RefS1F17',
            'requester_id': '#Field_RefS1F2',
            'requester_name': '#Field_RefS1F2_name',
            'request_datetime': '#Field_RefS1F18',
            'deadline': '#Field_RefS1F9',
            'title': '#Field_RefS1F4',
            'relname': '#Field_RefS7F87',
            'summary': '#Field_RefS7F86',
            'content': '#Field_RefS7F5',
            'urgency': '#Field_RefS7F32'
        }

        # 필드 데이터와 표 데이터를 동시에 비동기로 수집
        field_data_task = collect_field_data(page, fields)
        table_data_task = collect_table_data(page)

        # 두 작업이 모두 완료될 때까지 대기
        request_data, table_data = await asyncio.gather(field_data_task, table_data_task)

        # 표 데이터 추가
        request_data['table_data'] = table_data

        # 로그 메시지 구성
        log_message = "요청 분석 결과:\n"
        log_message += json.dumps(request_data, ensure_ascii=False, indent=4)
        # 로그 기록
        await writelog(log_message)

        # 요청 분류
        reason, category = classify_request(request_data)

        # 결과 구성
        result = {
            '요청 ID': request['요청 ID'],
            '제목': request['제목'],
            '기한': request_data['deadline'],
            '요청자': request['요청부서'] + ' ' + request['요청자'],
            '분류': category,
            '분류기준': reason
        }

        # 로그 메시지 구성
        log_message = "요청 분석 결과:\n"
        log_message += json.dumps(result, ensure_ascii=False, indent=4)
        printConsole(log_message)

        # 로그 기록
        await writelog(log_message)

        return result

    except Exception as e:
        error_message = f"요청 분석 중 오류 발생:\n{traceback.format_exc()}"
        await writelog(error_message)
        await writelog(f"실패한 요청: {request}")
        return None


def is_ip_in_range(ip_address, ip_ranges):
    """IP 주소가 주어진 IP 주소 범위 목록에 포함되는지 확인합니다.

    Args:
        ip_address: 확인할 IP 주소 (문자열).
        ip_ranges: IP 주소 범위 목록 (CIDR 표기법 문자열 리스트).

    Returns:
        IP 주소가 범위 내에 있으면 True, 그렇지 않으면 False.
        잘못된 IP 주소 또는 범위 형식이면 예외 발생.
    """
    try:
        ip = ipaddress.ip_address(ip_address)
    except ValueError:
        error_message = f"[is_ip_in_range] 잘못된 IP 주소 형식: {ip_address}"
        writelog(error_message)
        return False

    for ip_range_str in ip_ranges:
        try:
            ip_range = ipaddress.ip_network(ip_range_str)
            if ip in ip_range:
                return True
        except ValueError:
            error_message = f"[is_ip_in_range] 잘못된 IP 주소 범위 형식: {ip_range_str}"
            writelog(error_message)
            continue  # 다음 범위 확인

    return False


def classify_request(content):
    requestTermsStr = json.dumps(content, ensure_ascii=False, indent=4).lower()
    for condition in dataInfo.classification_conditions['conditions']:
        all_key_match = True
        for key in condition.get('keys', []):
            if key in condition and not any(keyword.lower() in content.get(key, '').lower() for keyword in condition[key]):
                all_key_match = False
                break
        if not all_key_match:
            continue

        all_table_key_match = True
        for table_key in condition.get('table_keys', []):
            if not bool(content.get('table_data', [])):
                # table_data 가 없으면 불일치
                all_table_key_match = False
                break
            if 'ip' not in table_key.lower():
                # 비교할 데이터가 IP가 아니면 포함여부 확인
                for row in content['table_data']:
                    if table_key not in row:
                        continue
                    if table_key in condition and not any(keyword.lower() in row.get(table_key, '').lower() for keyword in condition[table_key]):
                        all_table_key_match = False
                        break
            else:
                # 비교할 데이터가 IP이면 IP주소범위에 포함여부 확인
                all_table_key_match = False
                for row in content['table_data']:
                    if table_key not in row:
                        continue
                    if table_key in condition and is_ip_in_range(row[table_key], condition[table_key]):
                        all_table_key_match = True
                        break
        if not all_table_key_match:
            continue

        if "include_keywords" in condition and not all(keyword.lower() in requestTermsStr for keyword in condition["include_keywords"]):
            continue

        if "or_keywords" in condition and not any(keyword.lower() in requestTermsStr for keyword in condition["or_keywords"]):
            continue

        if "exclude_keywords" in condition and any(keyword.lower() in requestTermsStr for keyword in condition["exclude_keywords"]):
            continue

        if "regex" in condition and not re.search(condition["regex"], requestTermsStr):
            continue

        if "and_keywords" in condition and not all(keyword.lower() in requestTermsStr for keyword in condition["and_keywords"]):
            continue

        return condition["name"], condition["menu"]  # 모든 조건을 만족하면 해당 메뉴 반환

    return None, None  # 어떤 조건도 만족하지 않는 경우


async def try_click_element(page, elements, timeout=3000, dblclick=False):
    """
    주어진 요소들을 순차적으로 클릭 시도하는 함수

    Args:
        page: Playwright page 객체
        elements: 클릭할 요소들의 리스트
        timeout: 각 요소 클릭 시도의 타임아웃(ms)

    Returns:
        bool: 클릭 성공 여부
    """
    for element in elements:
        try:
            if not dblclick:
                await element.click(timeout=timeout)
            else:
                await element.dblclick(timeout=timeout)

            return True
        except Exception:
            continue
    return False


async def modify_approval_line(page, analyzed_request):
    """
    결재선을 수정하는 함수

    Args:
        page: Playwright page 객체
        analyzed_request: 요청 정보를 담은 dict
    """
    try:
        # 결재 및 참조 대상자 지정
        # 1. 참조자 리스트 생성
        # 담당자 제외한 나머지 인원
        referrers = dataInfo.provLine[analyzed_request['분류'][1]][1:]

        # 2. 결재자 리스트 생성
        approvers = []
        # 첫번째 결재자 - 업무 담당자
        approvers.append(dataInfo.provLine[analyzed_request['분류'][1]][0])
        # 두번째 결재자 - 결재권자
        if dataInfo.provInfo['결재권자'][0] not in dataInfo.provInfo['휴가']:
            approvers.append(dataInfo.provInfo['결재권자'][0])
        else:
            referrers.insert(0, dataInfo.provInfo['결재권자'][0])

        # UI 조작 시작
        # 1. "결재자 추가" 버튼 클릭
        await page.click("button.btn-add-appr-line")

        # 2. 결재자 추가 팝업이 나타날 때까지 대기
        await page.wait_for_selector("div.ui-dialog.preform", state="visible")
        await page.wait_for_timeout(1000)  # 추가 대기 시간

        # 3. 기존 결재자들 삭제
        while True:
            # 결재 라인 목록에서 첫 번째 행과 다음 행의 cell 가져오기
            rows = await page.locator("div.appr-line-list .jqx-grid-cell").all()
            if not rows or len(rows) == 0:
                break

            # 첫 번째 행의 다음 행이 있고, 그 행의 텍스트가 비어있다면 모든 데이터 행이 삭제된 것
            if len(rows) > 1:
                next_row_text = await rows[1].text_content()
                if not next_row_text.strip():
                    break

            # 첫 번째 행 선택 (클릭)
            await rows[0].click()
            await page.wait_for_timeout(500)  # 선택 후 잠시 대기

            # "결재자 삭제" 버튼 클릭
            await page.click("button.btn-del-appr.appr")
            await page.wait_for_timeout(500)  # 삭제 후 잠시 대기

        await page.wait_for_timeout(1000)  # 모든 삭제 작업 완료 후 대기

        # 4. 새로운 결재자 추가
        # 4-1. 네트워크팀 검색
        await page.fill("input.org-srch", "네트워크팀")
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(1000)

        # 4-2. 네트워크팀 선택
        await page.click("div.jqx-rc-all.jqx-tree-item:has-text('네트워크팀')")
        await page.wait_for_timeout(1000)

        # 4-3. 결재자 추가
        for approver in approvers:
            elements = await page.locator(f"text={approver}").all()
            await try_click_element(page, elements)
            await page.click("button.btn-appr.btn-add-appr")
            await page.wait_for_timeout(1000)

        # 4-4. 참조자 추가
        for referrer in referrers:
            elements = await page.locator(f"text={referrer}").all()
            await try_click_element(page, elements)
            await page.click("button.btn-appr.btn-add-refer")
            await page.wait_for_timeout(1000)

        await page.wait_for_timeout(1000)

        # 5. 결재선 설정 완료
        try:
            # 먼저 버튼이 클릭 가능한 상태가 될 때까지 명시적으로 대기
            # class와 text로 찾기
            buttons = await page.query_selector_all(
                "button.btn-point span.ui-button-text:has-text('확인')"
            )
            # 버튼클릭 시도
            await try_click_element(page, buttons)

        except Exception as e:
            await writelog(f"결재선 설정 완료 버튼 클릭 실패: {str(e)}")
            raise e

        await page.wait_for_timeout(1000)

        # 6. 결재정보 - "확인" 버튼 클릭
        # 먼저 버튼이 클릭 가능한 상태가 될 때까지 명시적으로 대기
        try:
            # class와 text로 찾기
            buttons = await page.query_selector_all(
                "button.btn-point span.ui-button-text:has-text('확인')"
            )
            # 버튼클릭 시도
            await try_click_element(page, buttons)
        except Exception as e:
            await writelog(f"결재정보 완료 버튼 클릭 실패: {str(e)}")
            raise e

        await page.wait_for_timeout(2000)

    except Exception as e:
        error_message = f"결재선 수정 중 오류 발생:\n{traceback.format_exc()}"
        await writelog(error_message)
        raise e


def is_deadline_past(deadline_str):
    """
    주어진 deadline 문자열이 오늘 날짜 이전인지 확인합니다.

    Args:
    deadline_str: YYYYMMDDHHMMSS 형식의 마감일 문자열.

    Returns:
    마감일이 오늘 또는 그 이전이면 True, 그렇지 않으면 False.
    """
    try:
        deadline = datetime.strptime(deadline_str, "%Y%m%d%H%M%S")
    except ValueError:
        print("잘못된 형식의 마감일 문자열입니다. YYYYMMDDHHMMSS 형식으로 입력해주세요.")
        return False

    today = datetime.today() + relativedelta(days=1)
    return deadline <= today


async def request_deadline_extension(page, analyzed_request) -> bool:
    """
    기한 조정 요청을 처리하는 비동기 함수

    Args:
        page: Playwright page 객체
        analyzed_request: 분석된 요청 정보를 담은 dict (기한, 제목, 요청 ID 등 포함)

    Returns:
        bool: 기한 조정 요청 처리 성공 여부
    """
    try:
        # 체크박스 클릭
        checkbox_ids = ['Field_F82_disp', 'Field_F88_disp', 'Field_F86_disp']
        checkbox_clicked = await page.evaluate('''
            (checkboxIds) => {
                for (const id of checkboxIds) {
                    const checkbox = document.querySelector(`input[type='checkbox'][id='${id}']`);
                    if (checkbox) {
                        // checked 속성 설정
                        checkbox.checked = true;
                        
                        // change 이벤트 발생
                        const event = new Event('change', { bubbles: true });
                        checkbox.dispatchEvent(event);
                        
                        // 연결된 onclick 핸들러 실행
                        if (checkbox.onclick) {
                            checkbox.onclick();
                        }
                        return true; // 체크박스를 찾아서 처리했음을 알림
                    }
                }
                return false; // 어떤 체크박스도 찾지 못함
            }
        ''', checkbox_ids)
        await page.wait_for_timeout(1000)

        if not checkbox_clicked:
            await writelog(f"{analyzed_request['요청자']} 가 신청한 {analyzed_request['제목']}({analyzed_request['요청 ID']}) 기한조정요청 체크박스를 찾을 수 없습니다.")
            return False

        # 한달 후 날짜 계산 (토요일, 일요일인 경우 다음 월요일로 조정)
        today = datetime.now()
        one_month_later = today + relativedelta(months=1)
        while one_month_later.weekday() in [5, 6]:  # 5는 토요일, 6은 일요일
            one_month_later += relativedelta(days=1)
        target_date = one_month_later.strftime('%Y-%m-%d')

        # 날짜 입력 - 여러 가능한 ID 처리
        date_script = """
            ({ids, date}) => {
                for (const id of ids) {
                    const input = document.querySelector(`#${id}`);
                    if (input) {
                        input.value = date;
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                        if (input.onchange) input.onchange();
                        if (input.onblur) input.onblur();
                        return true;
                    }
                }
                return false;
            }
        """
        date_input_found = await page.evaluate(date_script, {
            'ids': ['Field_F79_dt', 'Field_F84_dt', 'Field_F85_dt', 'Field_F86_dt'],
            'date': target_date
        })

        if not date_input_found:
            await writelog(f"{analyzed_request['요청자']} 가 신청한 {analyzed_request['제목']}({analyzed_request['요청 ID']}) 기한조정날짜 입력 필드를 찾을 수 없습니다.")
            return False
        await page.wait_for_timeout(500)

        # 사유 입력 - 여러 가능한 ID 처리
        reason_success = False  # 성공 여부를 추적하기 위한 변수
        try:
            # 여러 ID를 순회하면서 시도
            for field_id in ['Field_F80', 'Field_F84', 'Field_F85', 'Field_F87']:
                try:
                    # 해당 요소가 있는지 빠르게 체크 (짧은 timeout으로)
                    await page.wait_for_selector(f'#{field_id}', state='visible', timeout=1000)

                    # fill() 메서드로 값 입력
                    await page.fill(f'#{field_id}', '완료기한 조정을 요청합니다.')

                    # 값이 제대로 설정되었는지 확인
                    value = await page.evaluate(f'document.querySelector("#{field_id}").value')

                    if value == '완료기한 조정을 요청합니다.':
                        # 성공적으로 값이 입력되면 success를 True로 설정하고 루프 종료
                        reason_success = True
                        break

                except Exception:
                    # 개별 필드 실패는 무시하고 계속 진행
                    continue

            if not reason_success:
                # 모든 필드 시도 실패
                await writelog(f"{analyzed_request['요청자']} 가 신청한 {analyzed_request['제목']}({analyzed_request['요청 ID']}) 기한조정사유 입력 필드를 찾을 수 없습니다.")
                return False

        except Exception as e:
            # 전체 프로세스 실패
            await writelog(f"{analyzed_request['요청자']} 가 신청한 {analyzed_request['제목']}({analyzed_request['요청 ID']}) 기한조정사유 입력 중 오류 발생: {str(e)}")
            return False

        await page.wait_for_timeout(500)
        # 기한조정요청 버튼 클릭
        await page.click("#CTL03341_0")
        await page.wait_for_timeout(1000)

        # 확인 버튼 클릭
        confirm_button = await page.wait_for_selector('div.jconfirm-buttons button.btn-point:has-text("확인")', timeout=5000)
        if confirm_button:
            await confirm_button.click()
            await page.wait_for_timeout(1000)

        # 저장 확인 버튼 클릭
        await page.click("button.btn.btn-default.btn-point:has-text('확인')")

        # 로그 기록
        msg = f"{analyzed_request['요청자']} 가 신청한 {analyzed_request['제목']}({analyzed_request['요청 ID']}) 기한을 {
            datetime.strptime(analyzed_request['기한'], '%Y%m%d%H%M%S').strftime('%Y-%m-%d')} → {target_date} 으로 조정요청 완료"
        print(msg)
        await writelog(msg)
        return True

    except Exception as e:
        error_message = f"{analyzed_request['요청자']} 가 신청한 {analyzed_request['제목']}({
            analyzed_request['요청 ID']}) 기한조정요청 처리 중 오류 발생:\n{traceback.format_exc()}"
        await writelog(error_message)
        return False


async def check_reject_status(page):
    """
    반려 여부를 확인하는 함수
    category_menu1(히스토리맵)과 category_menu3(이관 및 반려) 둘 다 확인

    Returns:
        bool: 반려 상태이면 True, 아니면 False
    """

    # 1. category_menu1 히스토리맵에서 반려 확인
    has_reject_history = await check_reject_from_history(page)

    # 2. category_menu3 이관 및 반려에서 반려 확인
    has_reject_record = await check_reject_from_record(page)

    # 둘 중 하나라도 반려가 있으면 True 반환
    return has_reject_history or has_reject_record


async def check_reject_from_history(page):
    """
    category_menu1의 히스토리맵에서 반려 여부 확인
    """
    try:
        # category_menu1이 존재하는지 확인
        await page.wait_for_selector('#category_menu1', state='attached', timeout=3000)

        # 히스토리맵에서 반려 항목 확인
        has_reject = await page.evaluate('''
            () => {
                try {
                    // 히스토리맵의 timeline 항목들 선택
                    const timelineItems = document.querySelectorAll('#category_menu1 .timeline-sm-item');
                    
                    if (timelineItems.length === 0) {
                        return false;
                    }
                    
                    let mostRecentTime = new Date(0);
                    let isMostRecentReject = false;
                    
                    for (const item of timelineItems) {
                        // 반려 클래스가 있는지 확인
                        const hasRejectClass = item.classList.contains('timeline-reject');
                        
                        // 타임라인 텍스트에서 반려 확인
                        const timelineText = item.querySelector('.timeline-text');
                        const isRejectText = timelineText && 
                                           (timelineText.textContent.includes('반려') || 
                                            timelineText.textContent.includes('(반려)'));
                        
                        // 반려 항목인지 확인 (클래스 또는 텍스트로)
                        if (hasRejectClass || isRejectText) {
                            // 날짜와 시간 정보 추출
                            const dateSpan = item.querySelector('.timeline-sm-date:not(.top)');
                            const timeSpan = item.querySelector('.timeline-sm-date.top');
                            
                            if (dateSpan && timeSpan) {
                                const dateString = dateSpan.textContent.trim();
                                const timeString = timeSpan.textContent.trim();
                                
                                try {
                                    // YYYY-MM-DD HH:MM 형식으로 파싱
                                    const currentTime = new Date(dateString + ' ' + timeString);
                                    
                                    if (currentTime > mostRecentTime) {
                                        mostRecentTime = currentTime;
                                        isMostRecentReject = true;
                                    }
                                } catch (parseError) {
                                    console.error('날짜 파싱 오류:', parseError);
                                }
                            }
                        } else {
                            // 반려가 아닌 항목이 더 최근이면 반려 상태 해제
                            const dateSpan = item.querySelector('.timeline-sm-date:not(.top)');
                            const timeSpan = item.querySelector('.timeline-sm-date.top');
                            
                            if (dateSpan && timeSpan && !dateSpan.textContent.includes('(진행중)')) {
                                const dateString = dateSpan.textContent.trim();
                                const timeString = timeSpan.textContent.trim();
                                
                                try {
                                    const currentTime = new Date(dateString + ' ' + timeString);
                                    
                                    if (currentTime > mostRecentTime) {
                                        mostRecentTime = currentTime;
                                        isMostRecentReject = false;
                                    }
                                } catch (parseError) {
                                    console.error('날짜 파싱 오류:', parseError);
                                }
                            }
                        }
                    }
                    
                    return isMostRecentReject;
                } catch (error) {
                    console.error('히스토리맵 반려 확인 중 오류:', error);
                    return false;
                }
            }
        ''')

        if has_reject:
            await writelog("히스토리맵에서 반려 상태 확인됨")

        return has_reject

    except Exception as e:
        await writelog(f"히스토리맵 반려 확인 중 오류 발생: {str(e)}")
        return False


async def check_reject_from_record(page):
    """
    category_menu3의 이관 및 반려에서 반려 여부 확인 (기존 로직)
    """
    try:
        # category_menu3가 존재하는지 확인
        await page.wait_for_selector('#category_menu3', state='attached', timeout=3000)

        # "이관 및 반려" 탭이 활성화되어 있는지 확인
        is_active = await page.evaluate('''
            () => {
                const tab = document.querySelector('li[target="recordGroup_01"]');
                return tab && tab.classList.contains('active');
            }
        ''')

        if not is_active:
            # "이관 및 반려" 탭 클릭
            await page.click('li[target="recordGroup_01"]')
            await page.wait_for_timeout(1000)  # 탭 전환 대기

        # 반려 여부 확인 (기존 버전)
        has_reject = await page.evaluate('''
            () => {
                try {
                    // 반려 항목들 선택
                    const recordGroups = document.querySelectorAll('#recordGroup_01 div.dashboard-list-box ul > li');
                    
                    if (recordGroups.length === 0) {
                        return false;
                    }
                    
                    let mostRecentTime = new Date(0);
                    let isMostRecentReject = false;
                    
                    for (const record of recordGroups) {
                        // 각 반려 항목 내의 세부 정보 항목들 찾기
                        const detailItems = record.querySelectorAll('ul li');
                        
                        // 필요한 정보 변수
                        let dateString = '';
                        let isRejectType = false;
                        let isRequestPlanStage = false;
                        
                        // 각 세부 정보 항목 확인
                        for (const item of detailItems) {
                            const text = item.textContent.trim();
                            
                            // 유형 확인
                            if (item.classList.contains('point-text') && text.includes('유형: 반려')) {
                                isRejectType = true;
                            }
                            // 단계 확인
                            else if (text.includes('단계:') && text.includes('요청계획')) {
                                isRequestPlanStage = true;
                            }
                            // 등록일시 확인
                            else if (text.includes('등록일시:')) {
                                const parts = text.split('등록일시:');
                                if (parts.length > 1) {
                                    dateString = parts[1].trim();
                                }
                            }
                        }
                        
                        // 날짜 파싱 및 비교
                        if (dateString) {
                            try {
                                const currentTime = new Date(dateString);
                                
                                if (currentTime > mostRecentTime) {
                                    mostRecentTime = currentTime;
                                    isMostRecentReject = isRejectType && isRequestPlanStage;
                                }
                            } catch (parseError) {
                                console.error('날짜 파싱 오류:', parseError);
                            }
                        }
                    }
                    
                    return isMostRecentReject;
                } catch (error) {
                    console.error('반려 확인 중 오류:', error);
                    return false;
                }
            }
        ''')

        if has_reject:
            await writelog("이관 및 반려에서 반려 상태 확인됨")

        return has_reject

    except Exception as e:
        await writelog(f"이관 및 반려 반려 확인 중 오류 발생: {str(e)}")
        return False


async def approve_request(page, analyzed_request):
    """
    요청을 승인하는 함수

    Args:
        page: Playwright page 객체
        analyzed_request: 요청 정보를 담은 dict (요청 ID, 제목, 요청자, 분류)
    """
    global dataInfo
    try:
        # 0. 반려 여부 확인 (수정된 로직)
        has_reject = await check_reject_status(page)

        if has_reject:
            # 반려 버튼 클릭
            await page.click('button.btn.button-lst-action[title="반려"]')
            await page.wait_for_timeout(1000)

            # 확인 버튼 클릭
            await page.click("button.btn-point:has-text('확인')")
            await page.wait_for_timeout(1000)

            # 반려 사유 입력 대화상자가 나타날 때까지 대기
            await page.wait_for_selector("div.reject", state="visible")
            await page.wait_for_timeout(1000)

            # 반려 사유 입력
            await page.fill("textarea#reason", "담당자 확인 후 반려")
            await page.wait_for_timeout(1000)

            # 확인 버튼 클릭
            await page.click("button.btn-point:has-text('확인')")

            # 작업 완료 대기
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(1000)

            # 저장 확인 버튼 클릭
            await page.click("button.btn-point:has-text('확인')")
            await page.wait_for_timeout(1000)

            # 로그 기록
            reject_msg = f"{analyzed_request['요청자']} 가 신청한 {analyzed_request['제목']}({analyzed_request['요청 ID']}) 반려 완료"
            print(reject_msg)
            await writelog(reject_msg)
            return

        # 0. 기한만료인 경우 기한조정요청
        if is_deadline_past(analyzed_request['기한']):
            extension_result = await request_deadline_extension(page, analyzed_request)
            if not extension_result:
                dataInfo.failClassifcation.append(analyzed_request['요청 ID'])
                try:
                    # JavaScript를 사용하여 closeForm 함수 실행
                    await page.evaluate("closeForm()")
                    await page.wait_for_timeout(1000)  # 폼이 닫히는 것을 기다림
                    # 로그 기록
                except Exception as close_error:
                    await writelog(f"{analyzed_request['요청자']} 가 신청한 {analyzed_request['제목']}({analyzed_request['요청 ID']}) 기한조정요청 실패로 폼 닫기 중 오류 발생: {str(close_error)}")
            return  # 기한 조정 요청 처리

        # 0. 분류가 없으면 return
        if not bool(analyzed_request['분류']):
            dataInfo.failClassifcation.append(analyzed_request['요청 ID'])
            msg = f"{analyzed_request['요청자']} 가 신청한 {
                analyzed_request['제목']}({analyzed_request['요청 ID']}) 분류실패!"
            await asyncio.gather(writelog(msg), write_notice(msg))
            return

        # 1. 요청 구분 선택 (일반/변경)
        if analyzed_request['분류'][0] == '일반':
            await page.click("label[for='Field_F71_0'], label[for='Field_F75_0'], label[for='Field_F78_0']")
        else:  # '변경'
            await page.click("label[for='Field_F71_1'], label[for='Field_F75_1'], label[for='Field_F78_1']")

        # 값이 변경될 때까지 잠시 대기
        await page.wait_for_timeout(1000)

        # 2. 담당자 선택 버튼 클릭
        search_button = await page.wait_for_selector("span.atom-group-addon.right.hover i.fa.fa-search")
        await search_button.click()

        # 담당자 목록이 나타날 때까지 대기
        await page.wait_for_selector(".jqx-grid-cell")
        await page.wait_for_timeout(1000)

        # 담당자명 입력
        target_name = dataInfo.provLine[analyzed_request['분류'][1]][0]
        await page.fill('input[name="emp_name_display"]', target_name)

        # 조회 버튼 클릭
        search_button = await page.wait_for_selector("button.btn.button-lst-action[title='조 회']")
        await search_button.click()
        await page.wait_for_timeout(1000)  # 검색 결과가 로드될 때까지 대기

        # dataInfo.provLine[request['분류'][1]][0]과 일치하는 담당자 찾기
        cells = await page.locator('.jqx-grid-cell').all()
        targetCells = []
        for cell in cells:
            cell_text = await cell.text_content()
            if cell_text.strip() == "네트워크팀":
                targetCells.append(cell)
        await try_click_element(page, targetCells)

        # 담당자 선택 후 메인 화면으로 돌아오기까지 대기
        await page.wait_for_load_state('networkidle')
        await page.wait_for_timeout(1000)

        # 3. 대표CI 선택
        # 대표CI 검색 버튼 클릭
        search_button = await page.wait_for_selector("#Field_F35_s span.atom-group-addon.right.hover")
        await search_button.click()

        # 대표CI 목록이 나타날 때까지 대기
        await page.wait_for_selector(".jqx-grid-cell")
        await page.wait_for_timeout(1000)

        # CI명 필드에서 request['분류'][1]이 포함된 셀 찾기
        cells = await page.locator('.jqx-grid-cell').all()
        targetCells = []
        for cell in cells:
            cell_text = await cell.text_content()
            if analyzed_request['분류'][1] in cell_text.strip():
                targetCells.append(cell)
        await try_click_element(page, targetCells)
        await page.wait_for_timeout(1000)

        # 선택 후 메인 화면으로 돌아오기까지 대기
        await page.wait_for_load_state('networkidle')

        # 시스템 선택
        # 시스템 검색 버튼 클릭
        search_button = await page.wait_for_selector("#Field_F74_s span.atom-group-addon.right.hover, #Field_F80_s span.atom-group-addon.right.hover, #Field_F82_s span.atom-group-addon.right.hover")
        await search_button.click()

        # 시스템 목록이 나타날 때까지 대기
        await page.wait_for_selector(".jqx-grid-cell")
        await page.wait_for_timeout(1000)

        # 첫번째 항목 클릭
        cells = await page.locator('.jqx-grid-cell').all()
        targetCells = []
        for cell in cells:
            cell_text = await cell.text_content()
            if 'CM' in cell_text.strip():
                targetCells.append(cell)
        await try_click_element(page, targetCells)

        # 선택 후 메인 화면으로 돌아오기까지 대기
        await page.wait_for_load_state('networkidle')
        await page.wait_for_timeout(1000)

        # 4. 승인 버튼 선택 및 클릭
        if analyzed_request['분류'][0] == '일반':
            # 일반 요청인 경우 "승인요청" 버튼
            await page.evaluate('''
                const buttons = Array.from(document.querySelectorAll('button.btn.button-lst-action.btn-next'));
                const approveButton = buttons.find(button => button.title === '승인요청' || button.textContent.includes('승인요청'));
                if(approveButton) {
                    approveButton.click();
                }
            ''')
            # 확인 다이얼로그가 나타날 때까지 대기
            await page.wait_for_selector("div.jconfirm-box-container div.jconfirm-content")

            # 확인 버튼 클릭
            await page.click("button.btn.btn-default.btn-point:has-text('확인')")

            # 확인 버튼 클릭 후 대기
            await page.wait_for_timeout(2000)  # 2초 대기

            # 결재선 수정
            await modify_approval_line(page, analyzed_request)
        else:
            # 변경 요청인 경우 "등록" 버튼
            await page.evaluate('''
                const buttons = Array.from(document.querySelectorAll('button.btn.button-lst-action.btn-next'));
                const regButton = buttons.find(button => button.title === '등록' || button.textContent.includes('등록'));
                if(regButton) {
                    regButton.click();
                }
            ''')

            # 확인 다이얼로그가 나타날 때까지 대기
            await page.wait_for_selector("div.jconfirm-box-container div.jconfirm-content")

            # 확인 버튼 클릭
            await page.click("button.btn.btn-default.btn-point:has-text('확인')")

            # 확인 버튼 클릭 실행 후 대기
            await page.wait_for_timeout(2000)  # 2초 대기

        # 저장 확인 버튼 클릭
        await page.click("button.btn.btn-default.btn-point:has-text('확인')")

        # 승인 완료 대기
        await page.wait_for_load_state('networkidle')

        # 로그 기록
        action = "승인요청" if analyzed_request['분류'][0] == '일반' else "등록"
        await writelog(f"요청 {analyzed_request['요청 ID']} {action} 완료")

    except Exception as e:
        error_message = f"요청 승인 중 오류 발생:\n{traceback.format_exc()}"
        await writelog(error_message)
        raise e


async def prov_update_task():
    """
    결재정보 체크하는 태스크
    """
    global dataInfo

    executed_times = set()

    while True:
        try:
            current_time = datetime.now()
            current_hour_min = current_time.strftime('%H:%M')
            today = current_time.strftime('%Y-%m-%d')

            # 날짜 바뀌면 초기화
            if not hasattr(dataInfo, 'last_update_date') or dataInfo.last_update_date != today:
                dataInfo.last_update_date = today
                executed_times.clear()

            # 체크 및 실행
            if (current_hour_min in dataInfo.prov_refresh_time and
                    current_hour_min not in executed_times):

                await writelog(f"⏰ prov_refresh_time 도달: {current_hour_min}")
                update_prov_result = await update_prov_info()
                if update_prov_result:
                    await set_prov_line()
                executed_times.add(current_hour_min)

            # dataInfo.interval 초마다 체크
            await asyncio.sleep(dataInfo.interval)

        except Exception as e:
            await writelog(f"prov_update_task 오류: {e}")
            await asyncio.sleep(dataInfo.interval0)


async def periodic_task(page):
    '''
    ITSM 자동접수 함수
    '''
    global dataInfo

    while True:
        try:
            # 현재 시간 확인 및 결재라인 갱신
            current_time = datetime.now().time()

            # 로그인 상태 체크
            is_logged_in = await check_login_status(page)

            if not is_logged_in:
                await writelog("세션이 만료되어 재로그인을 시도합니다.")

                # 로그인 페이지로 이동
                await page.goto(itsmInfo.domain)

                # 재로그인 시도
                login_result = await login(page)
                if not login_result:
                    await writelog("재로그인 실패. 1분 후 다시 시도합니다.")
                    await asyncio.sleep(60)
                    continue

                await writelog("재로그인 성공")

            # 결재할 요청 확인
            requests = await fetch_approval_list(page)

            # 접수시간 여부 확인
            if dataInfo.reception_time_end.time() > current_time >= dataInfo.reception_time_start.time():
                # 접수할 요청 확인
                requests = await fetch_receive_list(page)
                for request in requests:
                    if request.get('요청 ID', '데이터가 없습니다.') == '데이터가 없습니다.':
                        # 요청번호가 없는 경우 pass
                        continue
                    if request['요청 ID'] in dataInfo.failClassifcation:
                        # 분류실패한 요청 pass
                        continue
                    analyzed_request = await analyze_request(page, request)
                    await approve_request(page, analyzed_request)
                    break
                else:
                    await asyncio.sleep(dataInfo.interval)
            else:
                await asyncio.sleep(dataInfo.interval)
        except PlaywrightError as e:
            # Playwright 관련 예외 처리 (브라우저 연결 끊김 등)
            error_msg = f"Playwright 오류 발생: {str(e)}\n{traceback.format_exc()}"
            await writelog(error_msg)
            # 브라우저 연결이 끊어진 경우 main 함수로 제어를 반환하여 재시작하도록 함
            raise e
        except Exception as e:
            await writelog(f"작업 수행 중 오류 발생: {str(e)}")
            # 오류 발생시 잠시 대기 후 다음 시도
            await asyncio.sleep(dataInfo.interval)
            continue


async def check_login_status(page) -> bool:
    """
    로그인 상태를 확인하는 함수
    Returns:
        bool: 로그인 상태이면 True, 아니면 False
    """
    try:
        # 로그아웃 페이지 확인 (타임아웃을 짧게 설정)
        try:
            logout_text = await page.locator("h2.logout-title").text_content(timeout=3000)
            if "로그아웃" in logout_text:
                return False
        except Exception:
            # 로그아웃 페이지가 아닌 경우 (로그인 된 상태) - 계속 진행
            pass

        # 로그인 페이지 요소 확인 (타임아웃을 짧게 설정)
        try:
            login_element = await page.wait_for_selector("input[placeholder='ID']", timeout=3000)
            if login_element:
                return False
        except Exception:
            # 로그인 페이지가 아닌 경우 (로그인 된 상태) - 계속 진행
            pass

        # 현재 URL이 로그인 페이지인지 확인
        current_url = page.url
        if '/login' in current_url.lower():
            return False

        # 위의 모든 체크를 통과했다면 로그인된 상태로 판단
        return True

    except Exception as e:
        await writelog(f"로그인 상태 체크 중 오류 발생: {str(e)}")
        return False


async def login(page):
    '''
    ITSM 에 로그인하는 함수
    '''
    await page.goto(itsmInfo.domain)
    await page.fill("input[placeholder='ID']", itsmInfo.id)
    await page.fill("input[placeholder='PASSWORD']", itsmInfo.password)
    await page.click("a.btn-slide:has-text('LOGIN')")
    await page.wait_for_load_state('networkidle')

    # 로그인 후 추가 대기 (다이얼로그 로딩 시간 확보)
    await page.wait_for_timeout(2000)

    # 1. 비밀번호 변경 다이얼로그 처리
    try:
        # 여러 방법으로 비밀번호 변경 다이얼로그 확인
        password_change_selectors = [
            'span.ui-dialog-title:has-text("비밀번호 변경")',
            'div.ui-dialog:has-text("비밀번호 변경")',
            '.change-password',
            'div.ui-dialog-titlebar:has-text("비밀번호 변경")'
        ]

        password_dialog_found = False
        for selector in password_change_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=1000)
                if element:
                    password_dialog_found = True
                    await writelog(f"비밀번호 변경 다이얼로그 감지 (셀렉터: {selector})")
                    break
            except TimeoutError:
                continue

        if password_dialog_found:
            await writelog("비밀번호 변경 다이얼로그가 나타났습니다. '30일 후 변경하기' 버튼을 클릭합니다.")

            # "30일 후 변경하기" 버튼 클릭 시도 (여러 방법)
            close_button_selectors = [
                'button#close',  # HTML에서 확인된 정확한 ID
                'button:has-text("30일 후 변경하기")',
                'button.ui-button:has-text("30일 후 변경하기")',
                'button.ui-button.ui-widget.ui-state-default:has-text("30일 후 변경하기")'
            ]

            button_clicked = False
            for selector in close_button_selectors:
                try:
                    button = await page.wait_for_selector(selector, timeout=1000)
                    if button:
                        await button.click()
                        button_clicked = True
                        await writelog(f"'30일 후 변경하기' 버튼 클릭 성공 (셀렉터: {selector})")
                        break
                except TimeoutError:
                    continue
                except Exception as e:
                    await writelog(f"버튼 클릭 시도 중 오류 (셀렉터: {selector}): {str(e)}")
                    continue

            if button_clicked:
                # 다이얼로그가 닫힐 때까지 대기
                await writelog("비밀번호 변경을 30일 연기했습니다.")
                return True
            else:
                await writelog("'30일 후 변경하기' 버튼을 찾을 수 없습니다.")
                return False

    except Exception as e:
        await writelog(f"비밀번호 변경 다이얼로그 처리 중 예외 발생: {str(e)}")
        # 비밀번호 변경 다이얼로그 처리 실패 시에도 계속 진행

    # 2. 로그인 실패 에러 메시지 확인
    try:
        confirm_button = await page.wait_for_selector('button.btn.btn-default.btn-point', timeout=3000)

        if confirm_button:
            error_message_element = await page.query_selector('div.jconfirm-content')
            if error_message_element:
                error_message = await error_message_element.text_content()
            else:
                error_message = '알 수 없음'
            await writelog(f"로그인 실패 : {error_message}")
            return False
    except TimeoutError:
        # 에러 메시지가 없으면 로그인 성공으로 간주
        await writelog("로그인 성공")
        return True

    return True


async def get_browser_path():
    if getattr(sys, 'frozen', False):
        # exe 패키징된 경우 _MEIPASS 경로 사용
        playwright_path = os.path.join(sys._MEIPASS, 'playwright')
        chromium_path = os.path.join(
            playwright_path, 'chromium-1148', 'chrome-win', 'chrome.exe')

        # 디버깅용 경로 출력
        print(f"Playwright path: {playwright_path}")
        print(f"Chromium path: {chromium_path}")

        if os.path.exists(chromium_path):
            return chromium_path
        else:
            print(f"Browser not found at: {chromium_path}")
    return None


async def run(playwright):
    global dataInfo, itsmInfo

    while True:
        try:
            # Chromium 브라우저를 시작합니다.
            # headless=True로 설정하면 브라우저 UI가 표시되지 않습니다.
            browser_path = await get_browser_path()
            browser = await playwright.chromium.launch(
                headless=False,
                executable_path=browser_path,
                args=[
                    '--start-maximized',  # 창 최대화
                    '--disable-popup-blocking',  # 팝업 차단 비활성화
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-translate',
                    '--disable-extensions',
                    '--disable-background-networking',
                    '--disable-sync',
                    '--metrics-recording-only',
                    '--disable-default-apps',
                    '--mute-audio',
                    '--no-first-run'
                ]
            )
            context = await browser.new_context(
                viewport=None,  # viewport를 None으로 설정하여 전체화면 허용
                no_viewport=True,  # viewport 제한을 비활성화
                accept_downloads=True,  # 다운로드 허용
                java_script_enabled=True,  # JavaScript 활성화
                ignore_https_errors=True,  # HTTPS 오류 무시
                has_touch=False,  # 터치 이벤트 비활성화
                bypass_csp=True,  # CSP(Content Security Policy) 우회
                permissions=['notifications']  # 알림 권한 허용
            )
            page = await context.new_page()

            # 모든 dialog를 자동으로 accept하도록 설정
            page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))

            # ITSM 로그인
            loginResult = await login(page)
            if not loginResult:
                msg = f"로그인에 실패하여 스크립트를 종료합니다."
                t = threading.Thread(target=Mbox, args=(
                    f'{scriptInfo.script_name}', msg))
                t.start()
                # 명시적으로 브라우저 닫기
                await browser.close()
                return

            # 자동접수
            await asyncio.gather(
                prov_update_task(),       # 독립 체크
                periodic_task(page)        # 요청 처리
            )

        except Exception as e:
            await writelog(f"브라우저 실행 중 오류 발생: {str(e)}")
            try:
                await browser.close()
            except:
                pass
            await asyncio.sleep(60)  # 오류 발생시 1분 대기 후 재시도


def selWorker(member, exceptBackup=True):
    '''
    휴가자를 제외한 작업자를 선택하는 함수
    member : 담당자 리스트
    vacation : 휴가자 리스트
    nightWorker : 야간근무자 리스트
    return : 담당자 리스트에서 휴가자를 제외하고 가장 앞에 있는 담당자 리턴
    '''
    global dataInfo

    if not member:
        return None
    worker = member.pop(0)
    if exceptBackup:
        if not worker in dataInfo.provInfo['휴가'] and not worker in dataInfo.provInfo['야간'] and not worker in dataInfo.provInfo['백업']:
            return worker
    else:
        if not worker in dataInfo.provInfo['휴가'] and not worker in dataInfo.provInfo['야간']:
            return worker
    worker = selWorker(member, exceptBackup)
    return worker


async def get_calendar_info():
    ''''
    network_calendar 정보를 가져오는 함수
    '''
    global scriptInfo, network_calendar_file, dataInfo, sftpInfo

    sftpResult = await sftpInfo.download_sftp(
        f'{scriptInfo.dir_path}\\{network_calendar_file.pickleFile}', network_calendar_file.pickleFile)
    if not sftpResult:
        await writelog(f'{network_calendar_file.pickleFile} 파일 다운로드 실패!')
        return

    dataInfo.calendarInfo = await network_calendar_file.get_all_pickle()

    return


async def update_prov_info():
    '''
    provInfo 정보를 업데이트 하는 함수
    '''
    global scriptInfo, network_calendar_file, dataInfo, sftpInfo

    isChange = False
    d = datetime.now()
    sftpResult = await sftpInfo.download_sftp(
        f'{scriptInfo.dir_path}\\{network_prov_file.pickleFile}', network_prov_file.pickleFile)
    if sftpResult:
        remote_file_mtime = datetime.fromtimestamp(
            os.path.getmtime(f'{scriptInfo.dir_path}\\{network_prov_file.pickleFile}'))
        # 구글시트에서 가져온 정보가 있고, 로컬에 있는 json 파일보다 최신이며, 업데이트 날짜가 오늘이면
        # 결재자 정보(provData.provInfo)를 구글시트 정보로 업데이트
        remote_prov_info = await network_prov_file.get_all_pickle()
        if remote_file_mtime > dataInfo.prov_file_mtime and \
                remote_prov_info.get('update', None) == d.strftime('%Y-%m-%d'):
            new_timeoff = remote_prov_info.get('timeoff', None)
            if dataInfo.provInfo['휴가'] != new_timeoff:
                dataInfo.provInfo['휴가'] = new_timeoff
                isChange = True

            new_prov_info = remote_prov_info['provInfo']
            for key in new_prov_info:
                if key != '야간':
                    if dataInfo.provInfo[key] != new_prov_info[key]:
                        dataInfo.provInfo[key] = new_prov_info[key]
                        isChange = True
                else:
                    new_nightWorker = list(
                        set(remote_prov_info['nightworker'] + new_prov_info[key]))
                    if not are_lists_equal(dataInfo.provInfo[key], new_nightWorker):
                        dataInfo.provInfo['야간'] = new_nightWorker
                        isChange = True

    if isChange:
        msg = '휴가자 및 야간근무자 정보'
        msg = msg + '\n' + \
            json.dumps(dataInfo.provInfo, ensure_ascii=False, indent=4)
        printConsole(msg)

    return isChange


async def set_prov_line():
    '''
    담당업무별 결재라인을 만드는 함수
    '''
    global dataInfo

    # 담당자 확인
    for kind in dataInfo.provInfo['업무구분']:
        # 결재자, LAN 은 백업도 담당자가 될 수 있음
        manager = selWorker(dataInfo.provInfo[kind].copy(),
                            True if kind != 'LAN' else False)
        if not manager:
            dataInfo.provLine[kind] = None
            continue
        dataInfo.provLine[kind] = [manager]
        # 참조자
        for name in dataInfo.provInfo[kind]:
            if name in dataInfo.provLine[kind]:
                continue
            dataInfo.provLine[kind].append(name)

    return


async def main():
    # CONFIG 확인 전에 먼저 Playwright 설치 확인
    if getattr(sys, 'frozen', False):
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = os.path.join(
            sys._MEIPASS, 'playwright')
        try:
            # Playwright 브라우저가 설치되어 있는지 확인
            if not os.path.exists(os.environ['PLAYWRIGHT_BROWSERS_PATH']):
                print("Installing Playwright browsers...")
                subprocess.run(
                    ['playwright', 'install', 'chromium'], check=True)
        except Exception as e:
            print(f"Failed to install browsers: {e}")
            return

    # CONFIG 확인
    await getConfig()

    # 캘린더정보 확인
    await get_calendar_info()

    # 오늘 접수 마감일자 확인
    dataInfo.reception_time_str = dataInfo.weekday_reception_hours.get(
        datetime.today().strftime("%A"), 'Closed')
    dataInfo.reception_time_start = datetime.strptime(
        dataInfo.reception_time_str.split('~')[0] if dataInfo.reception_time_str != 'Closed' else '00:00', '%H:%M')
    dataInfo.reception_time_end = datetime.strptime(
        dataInfo.reception_time_str.split('~')[1] if dataInfo.reception_time_str != 'Closed' else '00:00', '%H:%M')

    # 휴일여부 확인
    d = datetime.now()
    daystring = d.strftime('%Y%m%d')
    if daystring in dataInfo.restInfo['restdays'] or (bool(dataInfo.calendarInfo) and dataInfo.calendarInfo.get(daystring, False) and bool(dataInfo.calendarInfo[daystring]['휴일'])):
        msg = "오늘은 휴일이므로 접수를 종료합니다."
        await writelog(msg)
        printConsole(msg)
        await asyncio.sleep(1)
        sys.exit()

    # time off, 야간근무자 및 업무담당확인
    await update_prov_info()

    # 결재라인 확인
    await set_prov_line()

    async with async_playwright() as playwright:
        await run(playwright)

if __name__ == '__main__':
    # 스크립트 정보
    configInfo = ConfigInfo()
    dataInfo = DataInfo()
    network_prov_file = ImportFileInfo()
    network_calendar_file = ImportFileInfo()
    prov_info_file = ImportFileInfo()
    classification_conditions_file = ImportFileInfo()
    rest_info_file = ImportFileInfo()
    sftpInfo = ShareInfo()
    itsmInfo = SiteInfo()

    # 비동기 메인 함수 실행
    asyncio.run(main())
