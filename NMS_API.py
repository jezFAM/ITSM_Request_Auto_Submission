import os
import traceback
import codecs
import sys
import time
import json
import requests
import urllib3
import copy
import pandas as pd
import urllib3
import urllib.parse
import pymysql.cursors
import shutil

from pathlib import Path
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP, PKCS1_v1_5
from base64 import b64decode, b64encode, b16decode, b16encode

from sqlalchemy import create_engine, types

# InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 한글깨짐 처리
os.putenv('NLS_LANG', 'KOREAN_KOREA.KO16KSC5601')

# InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 실행파일 위치
dir_path = os.getcwd()
script_name = os.path.basename(__file__)
script_name = script_name.split(".")[0]

# nms db정보
db_ip_jungyo = '192.168.107.12'
db_ip_upmu = '10.220.100.11'
userName = 'kftc_watchall'
password = '@admin1357'
mysql_port = 53306
noSQL_port = 59200

# nms ap정보
ap_ip_jungyo = '192.168.107.10'
ap_ip_upmu = '10.220.100.10'

# nosql 쿼리문
nmsHeader = {'Content-Type': 'application/json'}
perfhist_URL = f'/perfhist-nms*/_search'
dayPerf_URL = f'/rscstatrawday-nms*/_search'
weekPerf_URL = f'/rscstatrawweek-nms*/_search'
monthPerf_URL = f'/rscstatrawmonth-nms*/_search'
yearPerf_URL = f'/rscstatrawyear-nms*/_search'
scroll_URL = f'/_search/scroll'

init_nosqlJson = {
    "version": 'true',
    "size": 5000,
    "sort": [
        {
            "@timestamp": {
                "order": "desc",
                "unmapped_type": "boolean"
            }
        }
    ],
    "_source": {
        "excludes": []
    },
    "aggs": {
        "2": {
            "date_histogram": {
                "field": "@timestamp",
                "interval": "30s",
                "time_zone": "Asia/Tokyo",
                "min_doc_count": 1
            }
        }
    },
    "stored_fields": [
        "*"
    ],
    "script_fields": {},
    "docvalue_fields": [
        {
            "field": "@timestamp",
            "format": "date_time"
        },
        {
            "field": "timestamp",
            "format": "date_time"
        }
    ],
    "query": {
        "bool": {
            "must": [
                {
                    "match_all": {}
                },
                {
                    "match_phrase": {
                    }
                },
                {
                    "bool": {
                        "should": [
                        ],
                        "minimum_should_match": 1
                    }
                },
                {
                    "range": {
                        "@timestamp": {
                            "gte": "2021-11-16 11:09:47",
                            "lte": "2021-11-16 11:11:47",
                            "format": "yyyy-MM-dd HH:mm:ss"
                        }
                    }
                }
            ]
        }
    }
}


def writelog(log):
    '''
    로그기록 함수
    '''
    d = datetime.now()
    log_file = Path(f'{dir_path}\\{script_name}.log')
    msg = f"{d.strftime('%Y.%#m.%#d. %H:%M:%S')}\t{log}"

    if log_file.is_file():
        f = codecs.open(log_file, 'a', encoding='utf-8')
    else:
        f = codecs.open(log_file, 'w', encoding='utf-8')

    f.writelines(msg)
    f.writelines('\n')
    f.close()


def format_time(seconds):
    """
    시간을 포맷팅
    - 1시간 미만: mm:ss
    - 1시간 이상: hh:mm:ss
    """
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)

    if h > 0:  # 1시간 이상일 경우
        return f"{h:02d}:{m:02d}:{s:02d}"
    else:      # 1시간 미만일 경우
        return f"{m:02d}:{s:02d}"


def printProgressBar(iteration, total, prefix='', suffix='', decimals=1, fill='█', start_time=time.time()):
    '''
    진행상태바를 출력하는 함수 (콘솔 창 크기에 따라 동적 길이 조정, 진행 시간 및 남은 예상 시간 추가)
    '''
    # 콘솔 창 너비 가져오기
    terminal_width = shutil.get_terminal_size().columns

    # prefix, suffix 및 기타 요소들의 길이를 계산하여 진행 바의 최대 길이 결정
    max_progress_info = f'{prefix}: | | {100.0:.{decimals}f}% {
        suffix} Elapsed: 99:59:59 Remaining: 99:59:59'
    reserved_space = len(max_progress_info)  # 전체 진행 정보를 고려한 최대 길이 계산
    bar_length = max(10, terminal_width - reserved_space -
                     1)  # 최소 길이 10 보장, 추가 여백 1칸 확보

    # 진행 바 상태 계산
    percents = f'{100 * (iteration / float(total)):.{decimals}f}'
    filled_length = int(round(bar_length * iteration / float(total)))
    bar = f'{fill * filled_length}{"-" * (bar_length - filled_length)}'

    # 진행 시간 및 남은 예상 시간 계산
    elapsed_time = time.time() - start_time
    if iteration == total:  # 100% 완료 시
        remaining_time = 0
    else:
        avg_time_per_iter = elapsed_time / iteration if iteration > 0 else 0
        remaining_time = avg_time_per_iter * (total - iteration)

    elapsed_str = f'Elapsed: {format_time(elapsed_time)}'
    remaining_str = f'Remaining: {format_time(remaining_time)}'

    # 진행 바 출력
    sys.stdout.write(f'\r{prefix}: |{bar}| {percents}% {
                     suffix} {elapsed_str} {remaining_str}')

    if iteration == total:
        sys.stdout.write('\n')
    sys.stdout.flush()


def DB_Query(nmsDB_ip, nmsDB_port, dbName, query, raw_data=False, isLogging=False):
    '''
    NMS DB를 조회하는 함수
    nmsDB_ip = nms db서버 ip
    nmsDB_port = nms rdb 포트번호
    dbName = watchall, kftc_db 중 선택
    query = 조회할 select 문
    isLogging = 오류에 대한 로깅 기록 여부
    '''
    global userName, password

    try:
        connection = pymysql.connect(host=nmsDB_ip,
                                     port=nmsDB_port,
                                     user=userName,
                                     password=password,
                                     database='watchall_2x' if dbName == "watchall" else 'kftc_db',
                                     cursorclass=pymysql.cursors.DictCursor)
        with connection:
            with connection.cursor() as cursor:
                # DB쿼리
                cursor.execute(query)
                result = cursor.fetchall()
                if raw_data:
                    data = result
                else:
                    data = list(map(lambda x: list(x.values()), result))
    except Exception as e:
        msg = f'[DB_Query] : {traceback.format_exc()}'
        if isLogging:
            writelog(msg)
        return False

    # 검색결과 리턴
    return data


def DB_Query_with_colName(nmsDB_ip, nmsDB_port, dbName, query, isLogging=False):
    '''
    NMS DB를 조회하는 함수
    nmsDB_ip = nms db서버 ip
    nmsDB_port = nms rdb 포트번호
    dbName = watchall, kftc_db 중 선택
    query = 조회할 select 문
    isLogging = 오류에 대한 로깅 기록 여부
    '''
    global userName, password

    try:
        connection = pymysql.connect(host=nmsDB_ip,
                                     port=nmsDB_port,
                                     user=userName,
                                     password=password,
                                     database='watchall_2x' if dbName == "watchall" else 'kftc_db',
                                     cursorclass=pymysql.cursors.DictCursor)
        with connection:
            with connection.cursor() as cursor:
                # DB쿼리
                cursor.execute(query)
                result = cursor.fetchall()
                colName = list(map(lambda x: x[0], cursor.description))
                data = list(map(lambda x: list(x.values()), result))
    except Exception as e:
        msg = f'[DB_Query_with_colName] : {traceback.format_exc()}'
        if isLogging:
            writelog(msg)
        return None, None

    # 검색결과 리턴
    return colName, data


def DB_Table_Copy(nmsDB_ip, nmsDB_port, dbName, sourcetableName, targetTableName, isSourceClear=False, isLogging=False):
    '''
    source 테이블을 target 테이블에 복사하는 함수
    nmsDB_ip = nms db서버 ip
    nmsDB_port = nms rdb 포트번호
    dbName = watchall, kftc_db 중 선택
    sourcetableName = 복사할 테이블
    targetTableName = 복사한 테이블을 붙여넣을 테이블
    isSourceClear = 복사할 테이블 초기화여부
    isLogging = 오류에 대한 로깅 기록 여부
    '''
    global userName, password

    del_last_dmz_sql = f"""
              TRUNCATE TABLE {targetTableName}
              """
    copy_sql = f"""
              INSERT INTO {targetTableName} SELECT * FROM {sourcetableName}
              """
    del_dmz_sql = f"""
              TRUNCATE TABLE {sourcetableName}
              """

    try:
        connection = pymysql.connect(host=nmsDB_ip,
                                     port=nmsDB_port,
                                     user=userName,
                                     password=password,
                                     database='watchall_2x' if dbName == "watchall" else 'kftc_db',
                                     cursorclass=pymysql.cursors.DictCursor)
        with connection:
            with connection.cursor() as cursor:
                # source 테이블 초기화
                cursor.execute(del_last_dmz_sql)
                # tartget table을 source table에 복사
                cursor.execute(copy_sql)
                # target tabel 초기화
                if isSourceClear:
                    cursor.execute(del_dmz_sql)
                connection.commit()

    except Exception as e:
        msg = f'[NMS_DB_Table_Copy] : {traceback.format_exc()}'
        if isLogging:
            writelog(msg)
        return False

    return True


def DB_Change(nmsDB_ip, nmsDB_port, dbName, query, isLogging=False):
    '''
    NMS DB를 업데이트 하는 함수
    nmsDB_ip = nms db서버 ip
    nmsDB_port = nms rdb 포트번호
    dbName = watchall, kftc_db 중 선택
    query = 변경쿼리
    isLogging = 오류에 대한 로깅 기록 여부
    '''
    global userName, password

    try:
        connection = pymysql.connect(host=nmsDB_ip,
                                     port=nmsDB_port,
                                     user=userName,
                                     password=password,
                                     database='watchall_2x' if dbName == "watchall" else 'kftc_db',
                                     cursorclass=pymysql.cursors.DictCursor)
        with connection:
            with connection.cursor() as cursor:
                # update query
                cursor.execute(query)
                connection.commit()
    except Exception as e:
        msg = f'[NMS_DB_Change] : {traceback.format_exc()}'
        if isLogging:
            writelog(msg)
        return False

    # 검색결과 리턴
    return True

# df progressbar calc


def chunker(seq, size):
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))


def DB_bulk_insert(nmsDB_ip, nmsDB_port, df, tableName, dbName='kftc_db', isBar=True, barName='InsertDB', includeIndex=True):
    '''
    dataframe 을 일괄 Db로 insert 하는 함수
    df : 입력할 dataframe
    dbName : 데이터베이스 이름, 기본 kftc_db, kftc_db 또는 watchall 입력
    '''
    global userName, password

    # 데이터베이스 확인
    if dbName == 'watchall':
        dbName = 'watchall_2x'

    # db 입력
    chunksize = int(len(df) / 10)
    engine = create_engine(
        f"mysql+pymysql://{userName}:{urllib.parse.quote_plus(password)}@{nmsDB_ip}:{nmsDB_port}/{dbName}?charset=utf8")
    conn = engine.connect()
    if chunksize == 0:
        df.to_sql(name=tableName, con=engine,
                  if_exists='append', index=includeIndex)
    else:
        if isBar:
            l = len(df)
            printProgressBar(0, l, prefix=barName, suffix='Complete')
            for i, cdf in enumerate(chunker(df, chunksize), start=1):
                cdf.to_sql(name=tableName, con=engine,
                           if_exists='append', index=includeIndex)
                printProgressBar(i * chunksize, l,
                                 prefix=barName, suffix='Complete')
        else:
            for i, cdf in enumerate(chunker(df, chunksize)):
                cdf.to_sql(name=tableName, con=engine,
                           if_exists='append', index=includeIndex)
    conn.close()

    return True


def get_nms_dev_id_by_ip(nmsDB_ip, nmsDB_port, deviceList):
    '''
    nms db 에서 device objID 를 가져오는 함수
    deviceList : objID 를 가져올 IP LIST
    nmsDB_ip = nms db서버 ip
    nmsDB_port = nms rdb 포트번호
    {'장비ip':'장비ID'} 리턴
    '''
    init_sql = '''
      SELECT a1.obj_name AS '장비명', a1.obj_id AS 'id'
      FROM obj a1
      WHERE a1.obj_define_id='NETDEVICE'
      AND a1.ipaddress_ipv4 = '%s'
  '''

    deviceIDs = dict()

    for device in deviceList:
        sql = init_sql % (deviceList[device])
        result = DB_Query(nmsDB_ip, nmsDB_port, 'watchall', sql)
        deviceIDs[device] = result[0][1] if result else 0

    return deviceIDs


def get_nms_dev_id_by_name(nmsDB_ip, nmsDB_port, deviceName):
    '''
    nms db 에서 device objID 를 가져오는 함수
    deviceName : objID 를 가져올 장비이름
    nmsDB_ip = nms db서버 ip
    nmsDB_port = nms rdb 포트번호
    objID 리턴
    '''
    init_sql = '''
      SELECT a1.obj_name AS '장비명', a1.obj_id AS 'id'
      FROM obj a1
      WHERE a1.obj_define_id='NETDEVICE'
      AND a1.obj_name = '%s'
  '''

    sql = init_sql % (deviceName)
    result = DB_Query(nmsDB_ip, nmsDB_port, 'watchall', sql)
    if not result:
        return None

    return result[0][1]


def get_nms_dev_id_by_name_like(nmsDB_ip, nmsDB_port, deviceName):
    '''
    nms db 에서 device objID 를 가져오는 함수
    deviceName : objID 를 가져올 장비이름(like검색)
    nmsDB_ip = nms db서버 ip
    nmsDB_port = nms rdb 포트번호
    objID 리턴
    '''
    init_sql = '''
      SELECT a1.obj_name AS '장비명', a1.obj_id AS 'id'
      FROM obj a1
      WHERE a1.obj_define_id='NETDEVICE'
      AND a1.obj_name like '%%%s%%'
  '''

    sql = init_sql % (deviceName)
    result = DB_Query(nmsDB_ip, nmsDB_port, 'watchall', sql)
    if not result:
        return None

    return result


def get_nms_dev_name_by_id(nmsDB_ip, nmsDB_port, deviceID):
    '''
    nms db 에서 device name 을 가져오는 함수
    deviceID : obj_name 을 가져올 장비ID
    nmsDB_ip = nms db서버 ip
    nmsDB_port = nms rdb 포트번호
    device name 리턴
    '''
    init_sql = '''
      SELECT a1.obj_name AS '장비명', a1.obj_id AS 'id'
      FROM obj a1
      WHERE a1.obj_define_id='NETDEVICE'
      AND a1.obj_id = '%s'
  '''

    sql = init_sql % (deviceID)
    result = DB_Query(nmsDB_ip, nmsDB_port, 'watchall', sql)
    if not result:
        return None

    return result[0][0]


def make_nms_dev_alive_json(deviceID, startDate, endDate):
    '''
    NMS netdevice 상태조회 쿼리 만들기
    deviceID : 성능조회할 objID 
    startDate :성능조회 시작일
    endDate :성능조회 종료일
    json query 리턴
    '''
    global init_nosqlJson

    match_phrase = {
        "match_phrase": {
            "objId": ""
        }
    }
    # UTC 타임으로 변환
    try:
        startDate = datetime.strptime(
            startDate, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=9)))
        startDate = datetime.astimezone(startDate, timezone.utc)
        startDate = startDate.strftime('%Y-%m-%d %H:%M:%S')

        endDate = datetime.strptime(
            endDate, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=9)))
        endDate = datetime.astimezone(endDate, timezone.utc)
        endDate = endDate.strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None

    nmsDevicAlivefJson = copy.deepcopy(init_nosqlJson)
    match_phrase['match_phrase']['objId'] = deviceID
    nmsDevicAlivefJson['query']['bool']['must'][1]['match_phrase'] = {
        "rsctypeId": {"query": "ND_RUNNINGSTATUS"}}
    nmsDevicAlivefJson['query']['bool']['must'][2]['bool']['should'].append(
        match_phrase)
    nmsDevicAlivefJson['query']['bool']['must'][3]['range']['@timestamp']['gte'] = startDate
    nmsDevicAlivefJson['query']['bool']['must'][3]['range']['@timestamp']['lte'] = endDate
    # del nmsDevicAlivefJson['query']['bool']['must'][1]

    return nmsDevicAlivefJson


def get_nms_dev_alive(nmsDB_ip, nmsDB_noSQL_port, deviceID, startDate, endDate, returnCode=200, isLogging=False):
    '''
    netdevice_alive 를 확인하는 함수
    nmsDB_ip : nms db ip주소
    nmsDB_noSQL_port : elastic search 포트
    nms 에서 2시간별 장비cpu 최대값을 가져오는 함수
    deviceID  : 성능을 조회할 장비ID
    startDate : 시작일
    endDate : 종료일

    kind : 2h는 2시간, d는 일별        
    maxCPU : cpu 최대값 리턴
    maxMEM : cpu 최대값 리턴
    maxCPU_date : cpu 최대값 일시 리턴
    maxMEM_date : mem 최대값 일시 리턴
    '''
    global nmsHeader, perfhist_URL, scroll_URL

    # NMS 성능조회 쿼리 만들기
    nmsDevicePerfJson = make_nms_dev_alive_json(deviceID, startDate, endDate)
    if not nmsDevicePerfJson:
        # 날짜 입력 오류
        msg = f"get_nms_dev_alive error : 조회일자 입력 오류입니다.\n" \
            f"{startDate}\n" \
            f"{endDate}\n"
        if isLogging:
            writelog(msg)
        return None

    # NMS 성능조회
    with requests.session() as s:
        s.auth = ('elastic', 'watchall')
        # 요청 JSON object_ids
        request = s.post(f"http://{nmsDB_ip}:{nmsDB_noSQL_port}{perfhist_URL}",
                         headers=nmsHeader, data=json.dumps(nmsDevicePerfJson), verify=False)
        if request.status_code != returnCode:
            # 조회오류
            msg = f"get_nms_dev_MaxPerf_daily error : {str(request.status_code)} 오류입니다.\n" \
                f"{request.text}"
            if isLogging:
                writelog(msg)
            s.close()
            return None

        result = json.loads(request.text)
        docs = result['hits']['hits']
        if '_scroll_id' in result:
            scrollJson = {
                'scroll': '1m',
                'scroll_id': result['_scroll_id']
            }

            while len(result['hits']['hits']):
                request = s.post(f"http://{nmsDB_ip}:{nmsDB_noSQL_port}{scroll_URL}",
                                 headers=nmsHeader, data=json.dumps(scrollJson), verify=False)
                result = json.loads(request.text)
                docs = docs + result['hits']['hits']
                scrollJson = {
                    'scroll': '1m',
                    'scroll_id': result['_scroll_id']
                }

    return docs[0]['_source']['NETDEVICE_ALIVE'] if docs else None


def make_nms_dev_perf_json(deviceID, startDate, endDate):
    '''
    NMS 성능조회 쿼리 만들기
    deviceID : 성능조회할 objID 
    startDate :성능조회 시작일
    endDate :성능조회 종료일
    json query 리턴
    '''
    global init_nosqlJson

    match_phrase = {
        "match_phrase": {
            "objId": ""
        }
    }
    # UTC 타임으로 변환
    try:
        startDate = datetime.strptime(
            startDate, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=9)))
        startDate = datetime.astimezone(startDate, timezone.utc)
        startDate = startDate.strftime('%Y-%m-%d %H:%M:%S')

        endDate = datetime.strptime(
            endDate, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=9)))
        endDate = datetime.astimezone(endDate, timezone.utc)
        endDate = endDate.strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None

    nmsDevicePerfJson = copy.deepcopy(init_nosqlJson)
    match_phrase['match_phrase']['objId'] = deviceID
    nmsDevicePerfJson['query']['bool']['must'][1]['match_phrase'] = {
        "rsctypeId": {"query": "DEVICE_PERF"}}
    nmsDevicePerfJson['query']['bool']['must'][2]['bool']['should'].append(
        match_phrase)
    nmsDevicePerfJson['query']['bool']['must'][3]['range']['@timestamp']['gte'] = startDate
    nmsDevicePerfJson['query']['bool']['must'][3]['range']['@timestamp']['lte'] = endDate

    return nmsDevicePerfJson


def get_nms_dev_MaxPerf(nmsDB_ip, nmsDB_noSQL_port, deviceID, startDate, endDate, returnCode=200, isLogging=False):
    '''
    nmsDB_ip : nms db ip주소
    nmsDB_noSQL_port : elastic search 포트
    nms 에서 2시간별 장비cpu 최대값을 가져오는 함수
    deviceID  : 성능을 조회할 장비ID
    startDate : 시작일
    endDate : 종료일
    kind : 2h는 2시간, d는 일별    
    maxCPU : cpu 최대값 리턴
    maxMEM : cpu 최대값 리턴
    maxCPU_date : cpu 최대값 일시 리턴
    maxMEM_date : mem 최대값 일시 리턴
    '''
    global nmsHeader, dayPerf_URL, weekPerf_URL, monthPerf_URL, yearPerf_URL, scroll_URL

    # NMS 성능조회 쿼리 만들기
    nmsDevicePerfJson = make_nms_dev_perf_json(deviceID, startDate, endDate)
    if not nmsDevicePerfJson:
        # 날짜 입력 오류
        msg = f"make_nms_dev_perf_json error : 조회일자 입력 오류입니다.\n" \
            f"{startDate}\n" \
            f"{endDate}\n"
        if isLogging:
            writelog(msg)
        return None

    # NMS 성능조회
    with requests.session() as s:
        s.auth = ('elastic', 'watchall')
        # 조회기간 선택
        startDate = datetime.strptime(
            startDate, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=9)))
        endDate = datetime.strptime(
            endDate, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=9)))
        nowDate = datetime.now().replace(tzinfo=timezone(timedelta(hours=9)))
        diff = (endDate - startDate).total_seconds()
        diff_now = (nowDate - endDate).total_seconds()
        diff_start = (datetime(nowDate.year, nowDate.month, nowDate.day, 0, 0, 0).replace(
            tzinfo=timezone(timedelta(hours=9))) - startDate).total_seconds()
        if diff_start <= 691200 and (diff_now <= 1800 or diff <= 1800):
            subURL = dayPerf_URL
        elif diff_now <= 3600 or diff <= 3600:
            subURL = weekPerf_URL
        elif diff_now <= 86400 or diff <= 86400:
            subURL = monthPerf_URL
        else:
            subURL = yearPerf_URL

        # 요청 JSON object_ids
        request = s.post(f"http://{nmsDB_ip}:{nmsDB_noSQL_port}{subURL}",
                         headers=nmsHeader, data=json.dumps(nmsDevicePerfJson), verify=False)
        if request.status_code != returnCode:
            # 조회오류
            msg = f"get_nms_dev_MaxPerf_daily error : {str(request.status_code)} 오류입니다.\n" \
                f"{request.text}"
            if isLogging:
                writelog(msg)
            s.close()
            return None

        result = json.loads(request.text)
        docs = result['hits']['hits']
        if '_scroll_id' in result:
            scrollJson = {
                'scroll': '1m',
                'scroll_id': result['_scroll_id']
            }

            while len(result['hits']['hits']):
                request = s.post(f"http://{nmsDB_ip}:{nmsDB_noSQL_port}{scroll_URL}",
                                 headers=nmsHeader, data=json.dumps(scrollJson), verify=False)
                result = json.loads(request.text)
                docs = docs + result['hits']['hits']
                scrollJson = {
                    'scroll': '1m',
                    'scroll_id': result['_scroll_id']
                }

    devicePerfList = list()
    for item in docs:
        if item['_source']['statType'] != 'MAX':
            continue
        devicePerfRaw = dict()
        devicePerfRaw['cpu'] = item['_source']['CPU_USERATE'] if 'CPU_USERATE' in item['_source'] else 0
        devicePerfRaw['mem'] = item['_source']['MEM_USERATE'] if 'MEM_USERATE' in item['_source'] else 0
        devicePerfRaw['date'] = datetime.strptime(
            item['_source']['@timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
        devicePerfRaw['date'] = datetime.astimezone(
            devicePerfRaw['date'], timezone(timedelta(hours=9)))
        devicePerfRaw['date'] = devicePerfRaw['date'].strftime(
            '%Y-%m-%d %H:%M:%S')
        devicePerfList.append(devicePerfRaw)

    devicePerfDF = pd.DataFrame(devicePerfList)

    try:
        maxCPU = devicePerfDF['cpu'].max()
        maxCPU_date = devicePerfDF.loc[devicePerfDF['cpu'] == maxCPU, 'date'].tolist()[
            0]
    except KeyError:
        maxCPU = 0
        maxCPU_date = '-'

    try:
        maxMEM = devicePerfDF['mem'].max()
        maxMEM_date = devicePerfDF.loc[devicePerfDF['mem'] == maxMEM, 'date'].tolist()[
            0]
    except KeyError:
        maxMEM = 0
        maxMEM_date = '-'

    return maxCPU, maxMEM, maxCPU_date, maxMEM_date


def get_nms_dev_AvgPerf(nmsDB_ip, nmsDB_noSQL_port, deviceID, startDate, endDate, returnCode=200, isLogging=False):
    '''
    nmsDB_ip : nms db ip주소
    nmsDB_noSQL_port : elastic search 포트
    nms 에서 2시간별 장비cpu 최대값을 가져오는 함수
    deviceID  : 성능을 조회할 장비ID
    startDate : 시작일
    endDate : 종료일
    kind : 2h는 2시간, d는 일별    
    maxCPU : cpu 최대값 리턴
    maxMEM : cpu 최대값 리턴
    maxCPU_date : cpu 최대값 일시 리턴
    maxMEM_date : mem 최대값 일시 리턴
    '''
    global nmsHeader, dayPerf_URL, weekPerf_URL, monthPerf_URL, yearPerf_URL, scroll_URL

    # NMS 성능조회 쿼리 만들기
    nmsDevicePerfJson = make_nms_dev_perf_json(deviceID, startDate, endDate)
    if not nmsDevicePerfJson:
        # 날짜 입력 오류
        msg = f"make_nms_dev_perf_json error : 조회일자 입력 오류입니다.\n" \
            f"{startDate}\n" \
            f"{endDate}\n"
        if isLogging:
            writelog(msg)
        return None

    # NMS 성능조회
    with requests.session() as s:
        s.auth = ('elastic', 'watchall')
        # 조회기간 선택
        startDate = datetime.strptime(
            startDate, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=9)))
        endDate = datetime.strptime(
            endDate, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=9)))
        nowDate = datetime.now().replace(tzinfo=timezone(timedelta(hours=9)))
        diff = (endDate - startDate).total_seconds()
        diff_now = (nowDate - endDate).total_seconds()
        diff_start = (datetime(nowDate.year, nowDate.month, nowDate.day, 0, 0, 0).replace(
            tzinfo=timezone(timedelta(hours=9))) - startDate).total_seconds()
        if diff_start <= 691200 and (diff_now <= 1800 or diff <= 1800):
            subURL = dayPerf_URL
        elif diff_now <= 3600 or diff <= 3600:
            subURL = weekPerf_URL
        elif diff_now <= 86400 or diff <= 86400:
            subURL = monthPerf_URL
        else:
            subURL = yearPerf_URL

        # 요청 JSON object_ids
        request = s.post(f"http://{nmsDB_ip}:{nmsDB_noSQL_port}{subURL}",
                         headers=nmsHeader, data=json.dumps(nmsDevicePerfJson), verify=False)
        if request.status_code != returnCode:
            # 조회오류
            msg = f"get_nms_dev_AvgPerf_daily error : {str(request.status_code)} 오류입니다.\n" \
                f"{request.text}"
            if isLogging:
                writelog(msg)
            s.close()
            return None

        result = json.loads(request.text)
        docs = result['hits']['hits']
        if '_scroll_id' in result:
            scrollJson = {
                'scroll': '1m',
                'scroll_id': result['_scroll_id']
            }

            while len(result['hits']['hits']):
                request = s.post(f"http://{nmsDB_ip}:{nmsDB_noSQL_port}{scroll_URL}",
                                 headers=nmsHeader, data=json.dumps(scrollJson), verify=False)
                result = json.loads(request.text)
                docs = docs + result['hits']['hits']
                scrollJson = {
                    'scroll': '1m',
                    'scroll_id': result['_scroll_id']
                }

    devicePerfList = list()
    for item in docs:
        if item['_source']['statType'] != 'MAX':
            continue
        devicePerfRaw = dict()
        devicePerfRaw['cpu'] = item['_source']['CPU_USERATE'] if 'CPU_USERATE' in item['_source'] else 0
        devicePerfRaw['mem'] = item['_source']['MEM_USERATE'] if 'MEM_USERATE' in item['_source'] else 0
        devicePerfRaw['date'] = datetime.strptime(
            item['_source']['@timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
        devicePerfRaw['date'] = datetime.astimezone(
            devicePerfRaw['date'], timezone(timedelta(hours=9)))
        devicePerfRaw['date'] = devicePerfRaw['date'].strftime(
            '%Y-%m-%d %H:%M:%S')
        devicePerfList.append(devicePerfRaw)

    devicePerfDF = pd.DataFrame(devicePerfList)

    try:
        avgCPU = round(devicePerfDF['cpu'].mean(), 2)
    except KeyError:
        avgCPU = 0

    try:
        avgMEM = round(devicePerfDF['mem'].mean(), 2)
    except KeyError:
        avgMEM = 0

    return avgCPU, avgMEM


def make_nms_traffic_json(lineID, startDate, endDate):
    '''
    NMS 트래픽 조회 쿼리 만들기
    deviceID : 트래픽 조회할 회선ID 
    startDate :트래픽 조회 시작일
    endDate :트래픽 조회 종료일
    json query 리턴
    '''
    global init_nosqlJson

    match_phrase = {
        "match_phrase": {
            "objId": ""
        }
    }
    # UTC 타임으로 변환
    try:
        startDate = datetime.strptime(
            startDate, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=9)))
        startDate = datetime.astimezone(startDate, timezone.utc)
        startDate = startDate.strftime('%Y-%m-%d %H:%M:%S')

        endDate = datetime.strptime(
            endDate, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=9)))
        endDate = datetime.astimezone(endDate, timezone.utc)
        endDate = endDate.strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None
    nmsDevicePerfJson = copy.deepcopy(init_nosqlJson)
    match_phrase['match_phrase']['objId'] = lineID
    nmsDevicePerfJson['query']['bool']['must'][1]['match_phrase'] = {
        "rsctypeId": {"query": "TRAFFIC"}}
    nmsDevicePerfJson['query']['bool']['must'][2]['bool']['should'].append(
        match_phrase)
    nmsDevicePerfJson['query']['bool']['must'][3]['range']['@timestamp']['gte'] = startDate
    nmsDevicePerfJson['query']['bool']['must'][3]['range']['@timestamp']['lte'] = endDate

    return nmsDevicePerfJson


def get_nms_MaxTraffic_daily(nmsDB_ip, nmsDB_noSQL_port, lineID, startDate, endDate, returnCode=200, isLogging=False):
    '''
    nms 에서 회선 2시간별 트래픽 최대값을 가져오는 함수
    lineID  : 성능을 조회할 회선ID
    startDate : 시작일
    endDate : 종료일    
    리턴값
    maxBps_in : inbound 최대값
    maxBps_out : outbound 최대값
    maxBps_in_date : inbound 최대값 일시 
    maxBps_out_date : outbound 최대값 일시
    '''
    global nmsHeader, dayPerf_URL, weekPerf_URL, monthPerf_URL, yearPerf_URL

    # NMS 트래픽 조회 쿼리 만들기
    nmsTrafficJson = make_nms_traffic_json(lineID, startDate, endDate)
    if not nmsTrafficJson:
        # 날짜 입력 오류
        msg = f"make_nms_traffic_json error : 조회일자 입력 오류입니다.\n" \
            f"{startDate}\n" \
            f"{endDate}\n"
        if isLogging:
            writelog(msg)
        return None

    # NMS 트래픽 조회
    with requests.session() as s:
        s.auth = ('elastic', 'watchall')
        # 조회기간 선택
        startDate = datetime.strptime(
            startDate, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=9)))
        endDate = datetime.strptime(
            endDate, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=9)))
        nowDate = datetime.now().replace(tzinfo=timezone(timedelta(hours=9)))
        diff = (endDate - startDate).total_seconds()
        diff_now = (nowDate - endDate).total_seconds()
        diff_start = (datetime(nowDate.year, nowDate.month, nowDate.day, 0, 0, 0).replace(
            tzinfo=timezone(timedelta(hours=9))) - startDate).total_seconds()
        if diff_start <= 691200 and (diff_now <= 1800 or diff <= 1800):
            subURL = dayPerf_URL
        elif diff_now <= 3600 or diff <= 3600:
            subURL = weekPerf_URL
        elif diff_now <= 86400 or diff <= 86400:
            subURL = monthPerf_URL
        else:
            subURL = yearPerf_URL

        # 요청 JSON object_ids
        request = s.post(f"http://{nmsDB_ip}:{nmsDB_noSQL_port}{subURL}",
                         headers=nmsHeader, data=json.dumps(nmsTrafficJson), verify=False)
        if request.status_code != returnCode:
            # 조회오류
            msg = f"get_nms_dev_MaxTraffic_daily error : {str(request.status_code)} 오류입니다.\n" \
                f"{request.text}"
            if isLogging:
                writelog(msg)
            s.close()
            return None

        result = json.loads(request.text)
        docs = result['hits']['hits']
        if '_scroll_id' in result:
            scrollJson = {
                'scroll': '1m',
                'scroll_id': result['_scroll_id']
            }

            while len(result['hits']['hits']):
                request = s.post(f"http://{nmsDB_ip}:{nmsDB_noSQL_port}{scroll_URL}",
                                 headers=nmsHeader, data=json.dumps(scrollJson), verify=False)
                result = json.loads(request.text)
                docs = docs + result['hits']['hits']
                scrollJson = {
                    'scroll': '1m',
                    'scroll_id': result['_scroll_id']
                }

    trafficfList = list()
    for item in result['hits']['hits']:
        if item['_source']['statType'] != 'MAX':
            continue
        linePerf = dict()
        linePerf['bps_in'] = item['_source']['TRAFFIC_BPS_IN'] if 'TRAFFIC_BPS_IN' in item['_source'] else 0
        linePerf['bps_out'] = item['_source']['TRAFFIC_BPS_OUT'] if 'TRAFFIC_BPS_OUT' in item['_source'] else 0
        linePerf['date'] = datetime.strptime(
            item['_source']['@timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
        linePerf['date'] = datetime.astimezone(
            linePerf['date'], timezone(timedelta(hours=9)))
        linePerf['date'] = linePerf['date'].strftime('%Y-%m-%d %H:%M:%S')
        trafficfList.append(linePerf)

    trafficDF = pd.DataFrame(trafficfList)

    try:
        maxBps_in = trafficDF['bps_in'].max()
        maxBps_in_date = trafficDF.loc[trafficDF['bps_in'] == maxBps_in, 'date'].tolist()[
            0]
    except KeyError:
        maxBps_in = 0
        maxBps_in_date = '-'

    try:
        maxBps_out = trafficDF['bps_out'].max()
        maxBps_out_date = trafficDF.loc[trafficDF['bps_out'] == maxBps_out, 'date'].tolist()[
            0]
    except KeyError:
        maxBps_out = 0
        maxBps_out_date = '-'

    return maxBps_in, maxBps_out, maxBps_in_date, maxBps_out_date


def get_nms_Traffic_daily(nmsDB_ip, nmsDB_noSQL_port, lineID, startDate, endDate, statType='MAX', returnCode=200, isLogging=False):
    '''
    nms 에서 회선 2시간별 트래픽 평균값을 가져오는 함수
    lineID  : 성능을 조회할 회선ID
    startDate : 시작일
    endDate : 종료일    
    리턴값
    maxBps_in : inbound 최대값
    maxBps_out : outbound 최대값
    maxBps_in_date : inbound 최대값 일시 
    maxBps_out_date : outbound 최대값 일시
    statType : MAX(최대), AVG(평균), MIN(최소)
    '''
    global nmsHeader, dayPerf_URL, weekPerf_URL, monthPerf_URL, yearPerf_URL

    # NMS 트래픽 조회 쿼리 만들기
    nmsTrafficJson = make_nms_traffic_json(lineID, startDate, endDate)
    if not nmsTrafficJson:
        # 날짜 입력 오류
        msg = f"make_nms_traffic_json error : 조회일자 입력 오류입니다.\n" \
            f"{startDate}\n" \
            f"{endDate}\n"
        if isLogging:
            writelog(msg)
        return None

    # NMS 트래픽 조회
    with requests.session() as s:
        s.auth = ('elastic', 'watchall')
        # 조회기간 선택
        startDate = datetime.strptime(
            startDate, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=9)))
        endDate = datetime.strptime(
            endDate, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=9)))
        nowDate = datetime.now().replace(tzinfo=timezone(timedelta(hours=9)))
        diff = (endDate - startDate).total_seconds()
        diff_now = (nowDate - endDate).total_seconds()
        diff_start = (datetime(nowDate.year, nowDate.month, nowDate.day, 0, 0, 0).replace(
            tzinfo=timezone(timedelta(hours=9))) - startDate).total_seconds()
        if diff_start <= 691200 and (diff_now <= 1800 or diff <= 1800):
            subURL = dayPerf_URL
        elif diff_now <= 3600 or diff <= 3600:
            subURL = weekPerf_URL
        elif diff_now <= 86400 or diff <= 86400:
            subURL = monthPerf_URL
        else:
            subURL = yearPerf_URL

        # 요청 JSON object_ids
        request = s.post(f"http://{nmsDB_ip}:{nmsDB_noSQL_port}{subURL}",
                         headers=nmsHeader, data=json.dumps(nmsTrafficJson), verify=False)
        if request.status_code != returnCode:
            # 조회오류
            msg = f"get_nms_dev_MaxTraffic_daily error : {str(request.status_code)} 오류입니다.\n" \
                f"{request.text}"
            if isLogging:
                writelog(msg)
            s.close()
            return None

        result = json.loads(request.text)
        docs = result['hits']['hits']
        if '_scroll_id' in result:
            scrollJson = {
                'scroll': '1m',
                'scroll_id': result['_scroll_id']
            }

            while len(result['hits']['hits']):
                request = s.post(f"http://{nmsDB_ip}:{nmsDB_noSQL_port}{scroll_URL}",
                                 headers=nmsHeader, data=json.dumps(scrollJson), verify=False)
                result = json.loads(request.text)
                docs = docs + result['hits']['hits']
                scrollJson = {
                    'scroll': '1m',
                    'scroll_id': result['_scroll_id']
                }

    trafficfList = list()
    for item in result['hits']['hits']:
        if item['_source']['statType'] != statType:
            continue
        linePerf = dict()
        linePerf['bps_in'] = item['_source']['TRAFFIC_BPS_IN'] if 'TRAFFIC_BPS_IN' in item['_source'] else 0
        linePerf['bps_out'] = item['_source']['TRAFFIC_BPS_OUT'] if 'TRAFFIC_BPS_OUT' in item['_source'] else 0
        linePerf['date'] = datetime.strptime(
            item['_source']['@timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
        linePerf['date'] = datetime.astimezone(
            linePerf['date'], timezone(timedelta(hours=9)))
        linePerf['date'] = linePerf['date'].strftime('%Y-%m-%d %H:%M:%S')
        trafficfList.append(linePerf)

    trafficDF = pd.DataFrame(trafficfList)

    try:
        maxBps_in = trafficDF['bps_in'].max()
        maxBps_in_date = trafficDF.loc[trafficDF['bps_in'] == maxBps_in, 'date'].tolist()[
            0]
    except KeyError:
        maxBps_in = 0
        maxBps_in_date = '-'

    try:
        maxBps_out = trafficDF['bps_out'].max()
        maxBps_out_date = trafficDF.loc[trafficDF['bps_out'] == maxBps_out, 'date'].tolist()[
            0]
    except KeyError:
        maxBps_out = 0
        maxBps_out_date = '-'

    return maxBps_in, maxBps_out, maxBps_in_date, maxBps_out_date


def make_nms_syslog_json(deviceID, startDate, endDate):
    global init_nosqlJson

    match_phrase = {
        "match_phrase": {
            "objId": ""
        }
    }

    # UTC 타임으로 변환
    try:
        startDate = datetime.strptime(
            startDate, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=9)))
        startDate = datetime.astimezone(startDate, timezone.utc)
        startDate = startDate.strftime('%Y-%m-%d %H:%M:%S')

        endDate = datetime.strptime(
            endDate, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone(timedelta(hours=9)))
        endDate = datetime.astimezone(endDate, timezone.utc)
        endDate = endDate.strftime('%Y-%m-%d %H:%M:%S')

        nmsSyslogJson = copy.deepcopy(init_nosqlJson)
        if deviceID:
            match_phrase['match_phrase']['objId'] = deviceID
            nmsSyslogJson['query']['bool']['must'][2]['bool']['should'].append(
                match_phrase)
        nmsSyslogJson['query']['bool']['must'][1]['match_phrase'] = {
            "logType": {"query": "SYSLOG"}}
        nmsSyslogJson['query']['bool']['must'][3]['range']['@timestamp']['gte'] = startDate
        nmsSyslogJson['query']['bool']['must'][3]['range']['@timestamp']['lte'] = endDate

    except ValueError:
        return None

    return nmsSyslogJson


def get_nms_syslog(nmsDB_ip, nmsDB_noSQL_port, deviceID, startDate, endDate, returnCode=200, isLogging=False):
    '''
    nms 에서 syslog를 조회하는 함수
    nmsDB_ip : nms db ip
    nmsDB_noSQL_port : nms elastic search port
    deviceID : syslog 를 조회할 장비 id
    startDate :성능조회 시작일
    endDate :성능조회 종료일
    {'장비명' : {'cpu':max_usage}, {'mem':max_usage}}  
    '''
    nmsHeader = {'Content-Type': 'application/json'}
    # nmsQuery_Syslog_URL = f'http://{nmsDB_ip}:{nmsDB_noSQL_port}/log*/_search'
    nmsQuery_Syslog_URL = f'http://{nmsDB_ip}:{
        nmsDB_noSQL_port}/log*/_search?scroll=1m'
    nmsQuery_SyslogNext_URL = f'http://{nmsDB_ip}:{
        nmsDB_noSQL_port}/_search/scroll'

    # 조회 쿼리 만들기
    nmsSyslogJson = make_nms_syslog_json(deviceID, startDate, endDate)
    if not nmsSyslogJson:
        return None

    sysList = list()

    # syslog 조회
    with requests.session() as s:
        s.auth = ('elastic', 'watchall')
        # 요청 JSON object_ids
        request = s.post(f"{nmsQuery_Syslog_URL}", headers=nmsHeader,
                         data=json.dumps(nmsSyslogJson), verify=False)
        if request.status_code != returnCode:
            # 조회오류
            msg = f"get_nms_syslog error : {str(request.status_code)} 오류입니다.\n" \
                f"{request.text}"
            if isLogging:
                writelog(msg)
            s.close()
            return None
        result = json.loads(request.text)
        docs = result['hits']['hits']
        if '_scroll_id' in result:
            scrollJson = {
                'scroll': '1m',
                'scroll_id': result['_scroll_id']
            }

            while len(result['hits']['hits']):
                request = s.post(f"{nmsQuery_SyslogNext_URL}", headers=nmsHeader, data=json.dumps(
                    scrollJson), verify=False)
                result = json.loads(request.text)
                docs = docs + result['hits']['hits']
                scrollJson = {
                    'scroll': '1m',
                    'scroll_id': result['_scroll_id']
                }

    for item in docs:
        if deviceID and item['_source']['objId'] != deviceID:
            continue
        SyslogList = dict()
        SyslogList['name'] = item['_source']['objName'] if 'objName' in item['_source'] else None
        SyslogList['id'] = item['_source']['objId']
        SyslogList['ip'] = item['_source']['sourceName']
        SyslogList['log'] = item['_source']['message']
        SyslogList['date'] = datetime.strptime(
            item['_source']['@timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
        SyslogList['date'] = datetime.astimezone(
            SyslogList['date'], timezone(timedelta(hours=9)))
        SyslogList['date'] = SyslogList['date'].strftime(
            '%Y-%m-%d %H:%M:%S.%f')
        sysList.append(SyslogList)

    return sysList


def check_ip_is_van(nmsDB_ip, nmsDB_port, ip_address, isLogging=False):
    '''
    NMS DB에서 IP 주소의 memo 필드에 'van'이 포함되어 있는지 확인하는 함수
    nmsDB_ip = nms db서버 ip
    nmsDB_port = nms rdb 포트번호
    ip_address = 확인할 IP 주소
    isLogging = 오류에 대한 로깅 기록 여부

    Returns:
        True: memo에 'van'이 포함되어 있음
        False: memo에 'van'이 포함되어 있지 않거나 IP를 찾을 수 없음
    '''
    global userName, password

    if not ip_address or not ip_address.strip():
        return False

    query = f"""
        SELECT memo
        FROM kftc_nms_ip
        WHERE ipaddress = '{ip_address.strip()}'
        LIMIT 1
    """

    try:
        result = DB_Query(nmsDB_ip, nmsDB_port, 'watchall', query, raw_data=True, isLogging=isLogging)

        if not result:
            return False

        # memo 필드 확인
        memo = result[0].get('memo', '')
        if memo and 'van' in memo.lower():
            if isLogging:
                writelog(f'[check_ip_is_van] IP {ip_address}는 VAN 관련 IP입니다. (memo: {memo})')
            return True

        return False

    except Exception as e:
        msg = f'[check_ip_is_van] : {traceback.format_exc()}'
        if isLogging:
            writelog(msg)
        return False


def nms_login(s, ip, id, pwd, isLogging=False):
    '''
    NMS 홈페이지에 로그인 하는 함수
    s : request session
    ip : NMS 접속 IP
    id : nms id
    pwd : nms pwd
    isLogging : 로그기록 여부 설정, 기본 False
    로그인 성공여부, 세션 쿠키값 리턴
    '''

    header = {'Accept': 'application/json, text/plain, */*',
              'Connection': 'keep-alive',
              'Content-Type': 'application/json;charset=UTF-8'
              }

    try:
        # RSA 암호화 키 확인
        request = s.get(f'https://{ip}/login/key.do',
                        headers=header, verify=False, timeout=3)
        keyDict = json.loads(request.text)

        # RSA 암호화
        n = int(keyDict['pkm'], 16)
        e = int(keyDict['pke'], 16)
        pubKey = RSA.construct((n, e))
        cipher = PKCS1_OAEP.new(pubKey)
        encID = cipher.encrypt(id.encode())
        encPWD = cipher.encrypt(pwd.encode())
        # 로그인 데이터 생성
        loginData = dict()
        loginData['managerId'] = b16encode(encID).decode()
        loginData['password'] = b16encode(encPWD).decode()
        loginData['locale'] = 'ko_KR'
        # 로그인
        request = s.post(f'https://{ip}/login/sign-in.do', headers=header,
                         data=json.dumps(loginData), verify=False, timeout=3)
        resultDict = json.loads(request.text)
        if not resultDict.get('success', False):
            return False
        if not resultDict.get('data', False):
            return False
        return True
    except Exception as e:
        msg = f'[nms_login] : {traceback.format_exc()}'
        if isLogging:
            writelog(msg)
        return False


if __name__ == '__main__':
    # # 테스트
    # target_date = datetime.today() - relativedelta(days=2)
    # target_date = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)
    # target_date_end = target_date + relativedelta(days=2)

    # target_date_nms_perf = target_date.strftime('%Y-%m-%d %H:%M:%S')
    # target_date_end_nms_perf = target_date_end.strftime('%Y-%m-%d %H:%M:%S')

    # # print(get_nms_MaxTraffic_daily(db_ip_jungyo, noSQL_port, 47475, target_date_nms_perf, target_date_end_nms_perf, kind='d'))
    # # print(get_nms_dev_MaxPerf(db_ip_jungyo, noSQL_port, 47475, target_date_nms_perf, target_date_end_nms_perf))
    # print (get_nms_dev_alive(db_ip_jungyo, noSQL_port, 119211, (datetime.today() - relativedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S'), datetime.today().strftime('%Y-%m-%d %H:%M:%S')))

    # init_query = 'SELECT 1 FROM fw_preproc_list WHERE ticketid = "%s" LIMIT 1;'
    # query = init_query % ("KFTC-20231024-003")
    # # DB쿼리
    # result = DB_Query(db_ip_jungyo, mysql_port, 'kftc_db', query)
    # print (result is not None)
    pass
