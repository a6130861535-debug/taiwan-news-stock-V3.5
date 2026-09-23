from bs4 import BeautifulSoup
# ==============================================================================
# Windows UTF-8 輸出防護
# ==============================================================================
import sys

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(
            encoding="utf-8",
            errors="replace"
        )
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(
            encoding="utf-8",
            errors="replace"
        )
except Exception:
    pass


# ==============================================================================
# 台股重大公開資訊新聞分析 V3.5
# ==============================================================================

import streamlit as st
import pandas as pd
import numpy as np
import requests
import feedparser
import yfinance as yf
import io
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

# ------------------------------------------------------------------------------
# 基本設定
# ------------------------------------------------------------------------------

st.set_page_config(
    page_title="台股重大公開資訊新聞分析 V3.5",
    page_icon="📊",
    layout="wide"
)

BASE_DIR = Path(r"C:\Users\a6130\taiwan_news_stock_v3")
BASE_DIR.mkdir(parents=True, exist_ok=True)

TWSE_MAJOR_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap04_L"
TWSE_BASIC_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"

TPEX_MAJOR_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O"
TPEX_BASIC_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"

MOPS_URL = "https://mops.twse.com.tw/mops/web/ajax_t05st01"

GOOGLE_NEWS_URL = (
    "https://news.google.com/rss/search"
    "?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/153.0 Safari/537.36"
    )
}

# ------------------------------------------------------------------------------
# 關鍵字
# ------------------------------------------------------------------------------

STRONG_POSITIVE = [
    "重大突破",
    "重大訂單",
    "取得大單",
    "獲利創高",
    "營收創高",
    "EPS創高",
    "併購",
    "合併",
    "處分利益",
    "重大合作",
    "策略合作",
    "新產品量產",
    "擴產",
    "庫藏股",
    "現金股利增加",
]

STRONG_NEGATIVE = [
    "重大損失",
    "財務危機",
    "跳票",
    "違約",
    "下修財測",
    "撤單",
    "解約",
    "停工",
    "裁員",
    "減產",
    "掏空",
    "遭搜索",
    "遭扣押",
    "遭起訴",
    "重大訴訟",
    "舞弊",
]

POSITIVE_KEYWORDS = [
    "營收增加",
    "營收成長",
    "獲利",
    "淨利增加",
    "毛利率增加",
    "EPS增加",
    "接單",
    "訂單",
    "得標",
    "合作",
    "擴產",
    "新廠",
    "量產",
    "技術突破",
    "股利",
    "配息",
    "庫藏股",
    "買回庫藏股",
    "增資",
    "併購",
    "合併",
    "策略聯盟",
    "重大契約",
]

NEGATIVE_KEYWORDS = [
    "營收下降",
    "營收衰退",
    "虧損",
    "淨利下降",
    "毛利率下降",
    "EPS下降",
    "撤單",
    "解約",
    "減產",
    "停工",
    "裁員",
    "資遣",
    "違約",
    "跳票",
    "訴訟",
    "遭搜索",
    "遭扣押",
    "遭起訴",
    "處分",
    "下修",
    "減資",
    "財務困難",
    "重大損失",
    "舞弊",
    "掏空",
]

EVENT_TYPES = {
    "財報/獲利": [
        "財報", "獲利", "淨利", "EPS", "毛利率",
        "損益", "盈餘", "虧損"
    ],
    "營收": [
        "營收", "營業收入", "月營收"
    ],
    "股利": [
        "股利", "配息", "除息", "盈餘分配"
    ],
    "訂單/合約": [
        "訂單", "接單", "得標", "契約", "合約", "採購"
    ],
    "併購/合併": [
        "併購", "合併", "收購"
    ],
    "庫藏股": [
        "庫藏股", "買回庫藏股", "股份買回"
    ],
    "訴訟/法律": [
        "訴訟", "起訴", "搜索", "扣押", "法院", "判決", "官司"
    ],
    "處分/投資": [
        "處分", "投資", "出售", "取得股權"
    ],
    "減資/增資": [
        "減資", "增資", "現金增資"
    ],
    "擴產/新廠": [
        "擴產", "新廠", "建廠", "量產"
    ],
}


# ==============================================================================
# 工具函式
# ==============================================================================

def safe_get_json(url, timeout=20):
    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=timeout
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def normalize_code(x):
    if x is None:
        return ""

    s = str(x).strip()

    m = re.search(r"\b(\d{4,6})\b", s)

    if m:
        return m.group(1)

    return s


def find_column(df, candidates):
    if df is None or df.empty:
        return None

    for c in candidates:
        if c in df.columns:
            return c

    return None


# ==============================================================================
# 股票清單
# ==============================================================================

@st.cache_data(ttl=3600)
def get_stock_universe():

    rows = []

    # --------------------------------------------------------------------------
    # TWSE
    # --------------------------------------------------------------------------

    twse = safe_get_json(TWSE_BASIC_URL)

    if isinstance(twse, list):

        for x in twse:

            if not isinstance(x, dict):
                continue

            code = normalize_code(
                x.get("公司代號")
                or x.get("證券代號")
                or x.get("股票代號")
            )

            name = (
                x.get("公司名稱")
                or x.get("證券名稱")
                or x.get("公司簡稱")
                or ""
            )

            if re.fullmatch(r"\d{4}", code):

                rows.append({
                    "股票代號": code,
                    "股票名稱": str(name),
                    "市場": "上市",
                    "Yahoo": code + ".TW",
                })

    # --------------------------------------------------------------------------
    # TPEx
    # --------------------------------------------------------------------------

    tpex = safe_get_json(TPEX_BASIC_URL)

    if isinstance(tpex, list):

        for x in tpex:

            if not isinstance(x, dict):
                continue

            code = normalize_code(
                x.get("公司代號")
                or x.get("證券代號")
                or x.get("代號")
                or x.get("SecuritiesCompanyCode")
            )

            name = (
                x.get("公司名稱")
                or x.get("證券名稱")
                or x.get("公司簡稱")
                or x.get("SecuritiesCompanyName")
                or ""
            )

            if re.fullmatch(r"\d{4}", code):

                rows.append({
                    "股票代號": code,
                    "股票名稱": str(name),
                    "市場": "上櫃",
                    "Yahoo": code + ".TWO",
                })

    df = pd.DataFrame(rows)

    if df.empty:
        return pd.DataFrame(
            columns=[
                "股票代號",
                "股票名稱",
                "市場",
                "Yahoo"
            ]
        )

    df = df.drop_duplicates(
        subset=["股票代號", "市場"]
    )

    return df.sort_values(
        ["市場", "股票代號"]
    ).reset_index(drop=True)


# ==============================================================================
# 文字清理
# ==============================================================================

def clean_text(x):

    if x is None:
        return ""

    x = str(x)

    x = re.sub(
        r"<[^>]+>",
        " ",
        x
    )

    x = re.sub(
        r"\s+",
        " ",
        x
    )

    return x.strip()


# ==============================================================================
# 官方重大訊息分類
# ==============================================================================

def classify_event(text):

    text = clean_text(text)

    pos = 0
    neg = 0

    matched_pos = []
    matched_neg = []

    for k in STRONG_POSITIVE:

        if k in text:
            pos += 3
            matched_pos.append(k)

    for k in STRONG_NEGATIVE:

        if k in text:
            neg += 3
            matched_neg.append(k)

    for k in POSITIVE_KEYWORDS:

        if k in text:
            pos += 1
            matched_pos.append(k)

    for k in NEGATIVE_KEYWORDS:

        if k in text:
            neg += 1
            matched_neg.append(k)

    score = pos - neg

    if score >= 3:
        sentiment = "正面"
    elif score <= -3:
        sentiment = "負面"
    elif score != 0:
        sentiment = "混合"
    else:
        sentiment = "中性"

    severity_score = abs(score)

    if any(k in text for k in STRONG_POSITIVE + STRONG_NEGATIVE):
        severity_score += 5

    if severity_score >= 8:
        severity = "S"
    elif severity_score >= 5:
        severity = "A"
    elif severity_score >= 2:
        severity = "B"
    else:
        severity = "C"

    event_type = "其他重大訊息"

    for typ, keywords in EVENT_TYPES.items():

        if any(k in text for k in keywords):
            event_type = typ
            break

    return {
        "情緒": sentiment,
        "事件等級": severity,
        "事件分數": score,
        "事件類型": event_type,
        "正面關鍵字": ", ".join(sorted(set(matched_pos))),
        "負面關鍵字": ", ".join(sorted(set(matched_neg))),
    }


# ==============================================================================
# TWSE 當日重大訊息
# ==============================================================================

@st.cache_data(ttl=300)
def get_twse_major():

    data = safe_get_json(TWSE_MAJOR_URL)

    if not isinstance(data, list):
        return pd.DataFrame()

    df = pd.DataFrame(data)

    if df.empty:
        return df

    code_col = find_column(
        df,
        [
            "公司代號",
            "證券代號",
            "股票代號",
        ]
    )

    name_col = find_column(
        df,
        [
            "公司名稱",
            "證券名稱",
            "公司簡稱",
        ]
    )

    date_col = find_column(
        df,
        [
            "發言日期",
            "日期",
            "發布日期",
        ]
    )

    title_col = find_column(
        df,
        [
            "主旨",
            "重大訊息",
            "公告事項",
        ]
    )

    content_col = find_column(
        df,
        [
            "說明",
            "內容",
        ]
    )

    result = pd.DataFrame()

    result["股票代號"] = (
        df[code_col].map(normalize_code)
        if code_col else ""
    )

    result["股票名稱"] = (
        df[name_col].astype(str)
        if name_col else ""
    )

    result["日期"] = (
        df[date_col].astype(str)
        if date_col else ""
    )

    result["主旨"] = (
        df[title_col].map(clean_text)
        if title_col else ""
    )

    result["內容"] = (
        df[content_col].map(clean_text)
        if content_col else ""
    )

    result["市場"] = "上市"
    result["來源"] = "TWSE"

    result["完整訊息"] = (
        result["主旨"].fillna("")
        + " "
        + result["內容"].fillna("")
    )

    return result


# ==============================================================================
# TPEx 當日重大訊息
# ==============================================================================

@st.cache_data(ttl=300)
def get_tpex_major():

    data = safe_get_json(TPEX_MAJOR_URL)

    if not isinstance(data, list):
        return pd.DataFrame()

    df = pd.DataFrame(data)

    if df.empty:
        return df

    code_col = find_column(
        df,
        [
            "公司代號",
            "證券代號",
            "代號",
            "SecuritiesCompanyCode",
        ]
    )

    name_col = find_column(
        df,
        [
            "公司名稱",
            "證券名稱",
            "公司簡稱",
            "SecuritiesCompanyName",
        ]
    )

    date_col = find_column(
        df,
        [
            "發言日期",
            "日期",
            "Date",
        ]
    )

    title_col = find_column(
        df,
        [
            "主旨",
            "重大訊息",
            "Subject",
        ]
    )

    content_col = find_column(
        df,
        [
            "說明",
            "內容",
            "Description",
        ]
    )

    result = pd.DataFrame()

    result["股票代號"] = (
        df[code_col].map(normalize_code)
        if code_col else ""
    )

    result["股票名稱"] = (
        df[name_col].astype(str)
        if name_col else ""
    )

    result["日期"] = (
        df[date_col].astype(str)
        if date_col else ""
    )

    result["主旨"] = (
        df[title_col].map(clean_text)
        if title_col else ""
    )

    result["內容"] = (
        df[content_col].map(clean_text)
        if content_col else ""
    )

    result["市場"] = "上櫃"
    result["來源"] = "TPEx"

    result["完整訊息"] = (
        result["主旨"].fillna("")
        + " "
        + result["內容"].fillna("")
    )

    return result


# ==============================================================================
# 日期處理
# ==============================================================================

def parse_date_series(series):

    if series is None:
        return pd.Series(dtype="datetime64[ns]")

    s = series.astype(str)

    s = s.str.replace(
        "/",
        "-",
        regex=False
    )

    s = s.str.replace(
        "年",
        "-",
        regex=False
    )

    s = s.str.replace(
        "月",
        "-",
        regex=False
    )

    s = s.str.replace(
        "日",
        "",
        regex=False
    )

    # 民國年轉西元年
    def roc_to_ad(x):

        m = re.match(
            r"^(\d{2,3})-(\d{1,2})-(\d{1,2})$",
            x
        )

        if not m:
            return x

        y, mo, d = map(int, m.groups())

        if y < 1911:
            y += 1911

        return f"{y:04d}-{mo:02d}-{d:02d}"

    s = s.map(roc_to_ad)

    return pd.to_datetime(
        s,
        errors="coerce"
    )


# ==============================================================================
# MOPS 歷史重大訊息
# ==============================================================================

def get_mops_history(stock_code, start_date, end_date):
    """
    MOPSOV 歷史重大訊息查詢。

    已驗證：
    https://mopsov.twse.com.tw/mops/web/ajax_t05st01

    回傳：
    日期
    日期_dt
    股票代號
    主旨
    說明
    完整訊息
    來源
    """

    import re
    import requests
    import pandas as pd
    from bs4 import BeautifulSoup

    page_url = "https://mopsov.twse.com.tw/mops/web/t05st01"
    ajax_url = "https://mopsov.twse.com.tw/mops/web/ajax_t05st01"

    columns = [
        "日期",
        "日期_dt",
        "股票代號",
        "主旨",
        "說明",
        "完整訊息",
        "來源",
    ]

    try:

        stock_code = str(stock_code).strip()

        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)

        # ----------------------------------------------------
        # 建立 Session
        # ----------------------------------------------------

        session = requests.Session()

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/153.0.0.0 Safari/537.36"
            ),
            "Referer": page_url,
            "Content-Type": (
                "application/x-www-form-urlencoded"
            ),
        }

        # ----------------------------------------------------
        # 先 GET，建立 Cookie
        # ----------------------------------------------------

        r1 = session.get(
            page_url,
            headers=headers,
            timeout=10
        )

        r1.raise_for_status()

        # ----------------------------------------------------
        # MOPSOV 正確 POST 參數
        # ----------------------------------------------------

        data = {
            "encodeURIComponent": "1",
            "step": "1",
            "firstin": "1",
            "off": "1",
            "keyword4": "",
            "code1": "",
            "TYPEK2": "",
            "checkbtn": "",
            "queryName": "co_id",
            "inpuType": "co_id",
            "TYPEK": "all",
            "co_id": stock_code,
            "year": str(start_dt.year - 1911),
            "month": "",
            "b_date": "",
            "e_date": "",
        }

        # ----------------------------------------------------
        # POST
        # ----------------------------------------------------

        r2 = session.post(
            ajax_url,
            data=data,
            headers=headers,
            timeout=15
        )

        r2.raise_for_status()

        html = r2.text

        # ----------------------------------------------------
        # 解析 HTML
        # ----------------------------------------------------

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        rows = []

        for tr in soup.find_all("tr"):

            cells = tr.find_all(
                ["td", "th"]
            )

            values = [
                cell.get_text(
                    " ",
                    strip=True
                )
                for cell in cells
            ]

            if len(values) < 5:
                continue

            # ------------------------------------------------
            # 必須包含股票代號
            # ------------------------------------------------

            if stock_code not in " ".join(values):
                continue

            # ------------------------------------------------
            # 找 ROC 日期
            # ------------------------------------------------

            date_index = None

            for i, value in enumerate(values):

                value = value.strip()

                if re.fullmatch(
                    r"\d{2,3}/\d{1,2}/\d{1,2}",
                    value
                ):
                    date_index = i
                    break

            if date_index is None:
                continue

            roc_date = values[date_index]

            try:

                y, m, d = [
                    int(x)
                    for x in roc_date.split("/")
                ]

                date_dt = pd.Timestamp(
                    year=y + 1911,
                    month=m,
                    day=d
                )

            except Exception:
                continue

            # ------------------------------------------------
            # 日期範圍
            # ------------------------------------------------

            if date_dt < start_dt:
                continue

            if date_dt > end_dt:
                continue

            # ------------------------------------------------
            # 找發言時間
            # ------------------------------------------------

            speak_time = ""

            for value in values:

                if re.fullmatch(
                    r"\d{1,2}:\d{2}:\d{2}",
                    value.strip()
                ):
                    speak_time = value.strip()
                    break

            # ------------------------------------------------
            # 找主旨
            #
            # MOPS 表格格式：
            # 股票代號
            # 公司名稱
            # 日期
            # 時間
            # 主旨
            # 說明
            # ------------------------------------------------

            subject = ""

            for i in range(
                date_index + 1,
                len(values)
            ):

                value = values[i].strip()

                if not value:
                    continue

                if re.fullmatch(
                    r"\d{1,2}:\d{2}:\d{2}",
                    value
                ):
                    continue

                # 避免把說明欄當主旨
                if len(value) >= 4:
                    subject = value
                    break

            if not subject:
                continue

            # ------------------------------------------------
            # 公司名稱
            # ------------------------------------------------

            company_name = ""

            for i, value in enumerate(values):

                value = value.strip()

                if value == stock_code:
                    if i + 1 < len(values):
                        company_name = (
                            values[i + 1]
                            .strip()
                        )
                    break

            if not company_name:
                company_name = stock_code

            # ------------------------------------------------
            # 說明
            # ------------------------------------------------

            if speak_time:

                description = (
                    f"{company_name}"
                    f"｜發言時間 {speak_time}"
                )

            else:

                description = company_name

            # ------------------------------------------------
            # 完整訊息
            # ------------------------------------------------

            full_message = (
                f"{subject}"
                f"｜{description}"
            )

            rows.append({
                "日期": date_dt.strftime(
                    "%Y-%m-%d"
                ),
                "日期_dt": date_dt,
                "股票代號": stock_code,
                "主旨": subject,
                "說明": description,
                "完整訊息": full_message,
                "來源": "MOPS歷史重大訊息",
            })

        # ----------------------------------------------------
        # 無資料
        # ----------------------------------------------------

        if not rows:

            return pd.DataFrame(
                columns=columns
            )

        # ----------------------------------------------------
        # DataFrame
        # ----------------------------------------------------

        df = pd.DataFrame(rows)

        # 去除重複
        df = df.drop_duplicates(
            subset=[
                "日期",
                "股票代號",
                "主旨"
            ]
        )

        # 排序
        df = df.sort_values(
            by=[
                "日期_dt",
                "股票代號"
            ]
        ).reset_index(
            drop=True
        )

        return df[columns]

    except Exception as e:

        print(
            f"MOPS歷史重大訊息查詢失敗 "
            f"({stock_code}): {e}"
        )

        return pd.DataFrame(
            columns=columns
        )

def get_historical_official_events(
    start_date,
    end_date,
    stock_codes=None,
    progress_callback=None
):
    """
    V3.5 官方全市場歷史重大訊息引擎
    --------------------------------
    資料來源：
        MOPS ezSearch

    市場：
        sii = 上市
        otc = 上櫃

    查詢方式：
        每日分別查詢上市、上櫃，再合併。

    優點：
        1. 真正支援歷史日期
        2. 不需逐檔股票查詢
        3. 不會重複呼叫只有當日資料的 OpenAPI
        4. 避免單次日期區間結果過大
        5. 與 V3.5 單一股票 get_mops_history() 完全分離
    """

    import json as _json
    import time as _time
    import re as _re
    from urllib.parse import urljoin as _urljoin

    import requests as _requests
    import pandas as _pd

    # --------------------------------------------------------
    # 固定輸出欄位
    # --------------------------------------------------------

    output_columns = [
        "日期",
        "日期_dt",
        "股票代號",
        "股票名稱",
        "市場",
        "事件等級",
        "情緒",
        "事件類型",
        "事件分數",
        "正面關鍵字",
        "負面關鍵字",
        "主旨",
        "說明",
        "完整訊息",
        "來源",
        "公告代碼",
        "公告類別",
        "公告時間",
        "明細網址",
    ]

    # --------------------------------------------------------
    # 日期
    # --------------------------------------------------------

    start_ts = _pd.Timestamp(start_date).normalize()
    end_ts = _pd.Timestamp(end_date).normalize()

    if start_ts > end_ts:
        start_ts, end_ts = end_ts, start_ts

    # --------------------------------------------------------
    # 股票代號過濾
    # --------------------------------------------------------

    code_filter = None

    if stock_codes is not None:

        if isinstance(stock_codes, str):
            stock_codes = [stock_codes]

        code_filter = {
            str(x).strip()
            for x in stock_codes
            if str(x).strip()
        }

    # --------------------------------------------------------
    # MOPS
    # --------------------------------------------------------

    PAGE_URL = (
        "https://mopsov.twse.com.tw/"
        "mops/web/ezsearch"
    )

    QUERY_URL = (
        "https://mopsov.twse.com.tw/"
        "mops/web/ezsearch_query"
    )

    session = _requests.Session()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/153.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "zh-TW,zh;q=0.9",
        "Content-Type": (
            "application/x-www-form-urlencoded;"
            "charset=UTF-8"
        ),
        "Origin": "https://mopsov.twse.com.tw",
        "Referer": PAGE_URL,
    }

    # --------------------------------------------------------
    # 建立 MOPS Session
    # --------------------------------------------------------

    try:

        session.get(
            PAGE_URL,
            headers=headers,
            timeout=20
        )

    except Exception:
        pass

    # --------------------------------------------------------
    # JSON 安全解析
    # MOPS 回應前有時有 BOM / 空白
    # --------------------------------------------------------

    def _parse_json(response):

        text = response.content.decode(
            "utf-8-sig",
            errors="replace"
        ).strip()

        start = text.find("{")
        end = text.rfind("}")

        if start < 0 or end < start:
            raise ValueError(
                "MOPS 回應找不到 JSON"
            )

        text = text[start:end + 1]

        return _json.loads(text)

    # --------------------------------------------------------
    # 民國日期 → Timestamp
    #
    # 例如：
    # 115/09/01
    # --------------------------------------------------------

    def _parse_roc_date(value):

        value = str(value or "").strip()

        if not value:
            return _pd.NaT

        nums = _re.findall(
            r"\d+",
            value
        )

        try:

            if len(nums) >= 3:

                year = int(nums[0])
                month = int(nums[1])
                day = int(nums[2])

                if year < 1911:
                    year += 1911

                return _pd.Timestamp(
                    year=year,
                    month=month,
                    day=day
                )

            # YYYYMMDD
            digits = _re.sub(
                r"\D",
                "",
                value
            )

            if len(digits) == 8:

                return _pd.to_datetime(
                    digits,
                    format="%Y%m%d",
                    errors="coerce"
                )

            # 民國 YYYMMDD
            if len(digits) == 7:

                year = int(digits[:3]) + 1911
                month = int(digits[3:5])
                day = int(digits[5:7])

                return _pd.Timestamp(
                    year=year,
                    month=month,
                    day=day
                )

        except Exception:
            pass

        return _pd.NaT

    # --------------------------------------------------------
    # Streamlit / 外部 progress callback 相容
    # --------------------------------------------------------

    def _emit_progress(done, total, message):

        if progress_callback is None:
            return

        ratio = (
            done / total
            if total
            else 1.0
        )

        try:
            progress_callback(
                ratio,
                message
            )
            return
        except TypeError:
            pass
        except Exception:
            return

        try:
            progress_callback(ratio)
        except Exception:
            pass

    # --------------------------------------------------------
    # 單一市場 / 單日查詢
    # --------------------------------------------------------

    def _query_market(
        query_date,
        typek,
        market_name
    ):

        date_string = query_date.strftime(
            "%Y%m%d"
        )

        payload = {
            "step": "00",

            # 1 = 市場別
            "RADIO_CM": "1",

            # sii / otc
            "TYPEK": typek,

            # 全產業
            "CO_MARKET": "",

            # 不指定公司
            "CO_ID": "",

            # M00 = 全部重大訊息
            "PRO_ITEM": "M00",

            # 不限主旨
            "SUBJECT": "",

            "SDATE": date_string,
            "EDATE": date_string,

            "lang": "TW",
            "AN": "",
        }

        # 最多重試 4 次
        for attempt in range(4):

            try:

                response = session.post(
                    QUERY_URL,
                    data=payload,
                    headers=headers,
                    timeout=35
                )

                raw_text = (
                    response.content.decode(
                        "utf-8-sig",
                        errors="replace"
                    )
                )

                # MOPS 防止查詢過於頻繁
                if "查詢過於頻繁" in raw_text:

                    _time.sleep(
                        2.0 * (attempt + 1)
                    )

                    continue

                data = _parse_json(
                    response
                )

                status = data.get(
                    "status"
                )

                rows = data.get(
                    "data",
                    []
                )

                if (
                    status == "success"
                    and isinstance(rows, list)
                ):
                    return rows

                # 無資料屬正常情況
                message = data.get(
                    "message",
                    []
                )

                message_text = str(
                    message
                )

                if (
                    "查無公告資料"
                    in message_text
                ):
                    return []

                return []

            except Exception:

                if attempt < 3:

                    _time.sleep(
                        1.5 * (attempt + 1)
                    )

                    continue

                return []

        return []

    # --------------------------------------------------------
    # 開始逐日抓取
    # --------------------------------------------------------

    dates = _pd.date_range(
        start=start_ts,
        end=end_ts,
        freq="D"
    )

    total_steps = (
        len(dates) * 2
    )

    done_steps = 0

    result_rows = []

    markets = [
        (
            "sii",
            "上市"
        ),
        (
            "otc",
            "上櫃"
        ),
    ]

    for current_date in dates:

        for typek, market_name in markets:

            done_steps += 1

            _emit_progress(
                done_steps,
                total_steps,
                (
                    "官方重大訊息："
                    f"{current_date:%Y-%m-%d} "
                    f"{market_name}"
                )
            )

            rows = _query_market(
                current_date,
                typek,
                market_name
            )

            for item in rows:

                code = str(
                    item.get(
                        "COMPANY_ID",
                        ""
                    )
                ).strip()

                if not code:
                    continue

                # 如果有指定股票代號才過濾
                if (
                    code_filter is not None
                    and code not in code_filter
                ):
                    continue

                company_name = str(
                    item.get(
                        "COMPANY_NAME",
                        ""
                    )
                    or ""
                ).strip()

                cdate = item.get(
                    "CDATE",
                    ""
                )

                date_dt = _parse_roc_date(
                    cdate
                )

                # 保險：
                # API 日期解析異常時使用查詢日期
                if _pd.isna(date_dt):
                    date_dt = current_date

                # 只保留指定日期區間
                if (
                    date_dt < start_ts
                    or date_dt > end_ts
                ):
                    continue

                subject = str(
                    item.get(
                        "SUBJECT",
                        ""
                    )
                    or ""
                ).strip()

                an_code = str(
                    item.get(
                        "AN_CODE",
                        ""
                    )
                    or ""
                ).strip()

                an_name = str(
                    item.get(
                        "AN_NAME",
                        ""
                    )
                    or ""
                ).strip()

                ctime = str(
                    item.get(
                        "CTIME",
                        ""
                    )
                    or ""
                ).strip()

                hyperlink = str(
                    item.get(
                        "HYPERLINK",
                        ""
                    )
                    or ""
                ).strip()

                if hyperlink:
                    hyperlink = _urljoin(
                        "https://mopsov.twse.com.tw",
                        hyperlink
                    )

                api_market = str(
                    item.get(
                        "TYPEK",
                        ""
                    )
                    or ""
                ).strip()

                final_market = (
                    api_market
                    if api_market
                    else market_name
                )

                description_parts = []

                if an_code:
                    description_parts.append(
                        an_code
                    )

                if an_name:
                    description_parts.append(
                        an_name
                    )

                description = " ".join(
                    description_parts
                ).strip()

                full_message = "\n".join(
                    x
                    for x in [
                        subject,
                        description
                    ]
                    if x
                ).strip()

                result_rows.append({
                    "日期":
                        date_dt.strftime(
                            "%Y-%m-%d"
                        ),

                    "日期_dt":
                        date_dt,

                    "股票代號":
                        code,

                    "股票名稱":
                        company_name,

                    "市場":
                        final_market,

                    "主旨":
                        subject,

                    "說明":
                        description,

                    "完整訊息":
                        full_message,

                    "來源":
                        "MOPS ezSearch",

                    "公告代碼":
                        an_code,

                    "公告類別":
                        an_name,

                    "公告時間":
                        ctime,

                    "明細網址":
                        hyperlink,
                })

            # 避免 MOPS 過度頻繁查詢
            _time.sleep(0.35)

    # --------------------------------------------------------
    # DataFrame
    # --------------------------------------------------------

    if not result_rows:

        return _pd.DataFrame(
            columns=output_columns
        )

    df = _pd.DataFrame(
        result_rows
    )

    # --------------------------------------------------------
    # 清理股票代號
    # --------------------------------------------------------

    df["股票代號"] = (
        df["股票代號"]
        .astype(str)
        .str.strip()
    )

    # --------------------------------------------------------
    # 去除重複事件
    #
    # 同一家公司、同日期、同時間、同主旨
    # 視為同一事件
    # --------------------------------------------------------

    df = (
        df
        .drop_duplicates(
            subset=[
                "日期_dt",
                "股票代號",
                "公告時間",
                "主旨",
            ],
            keep="first"
        )
        .sort_values(
            by=[
                "日期_dt",
                "公告時間",
                "股票代號",
            ],
            ascending=[
                False,
                False,
                True,
            ]
        )
        .reset_index(
            drop=True
        )
    )

    # --------------------------------------------------------
    # V3.5_EVENT_CLASSIFICATION_FIX
    # 使用原本 classify_event() 恢復事件分類 / S-A-B-C
    # --------------------------------------------------------

    classification_results = []

    for _, row in df.iterrows():

        classify_text = " ".join(
            str(x).strip()
            for x in [
                row.get("主旨", ""),
                row.get("公告類別", ""),
                row.get("說明", ""),
                row.get("完整訊息", ""),
            ]
            if str(x).strip()
        )

        try:

            event_info = classify_event(
                classify_text
            )

            if not isinstance(
                event_info,
                dict
            ):
                event_info = {}

        except Exception:

            event_info = {}

        classification_results.append({
            "事件等級":
                event_info.get(
                    "事件等級",
                    "C"
                ),

            "情緒":
                event_info.get(
                    "情緒",
                    "中性"
                ),

            "事件類型":
                event_info.get(
                    "事件類型",
                    "其他重大訊息"
                ),

            "事件分數":
                event_info.get(
                    "事件分數",
                    0
                ),

            "正面關鍵字":
                event_info.get(
                    "正面關鍵字",
                    ""
                ),

            "負面關鍵字":
                event_info.get(
                    "負面關鍵字",
                    ""
                ),
        })

    if classification_results:

        classification_df = _pd.DataFrame(
            classification_results,
            index=df.index
        )

        for col in [
            "事件等級",
            "情緒",
            "事件類型",
            "事件分數",
            "正面關鍵字",
            "負面關鍵字",
        ]:
            df[col] = classification_df[col]

    # --------------------------------------------------------
    # 保證欄位完整
    # --------------------------------------------------------

    for col in output_columns:

        if col not in df.columns:
            df[col] = ""

    return df[output_columns]


def search_news(stock_code, stock_name="", max_items=10):

    queries = []

    if stock_code:
        queries.append(stock_code)

    if stock_name:
        queries.append(stock_name)

    results = []

    for query in queries:

        if not query:
            continue

        try:

            url = GOOGLE_NEWS_URL.format(
                query=requests.utils.quote(query)
            )

            feed = feedparser.parse(url)

            for entry in feed.entries[:max_items]:

                title = clean_text(
                    getattr(entry, "title", "")
                )

                summary = clean_text(
                    getattr(entry, "summary", "")
                )

                published = clean_text(
                    getattr(entry, "published", "")
                )

                link = getattr(
                    entry,
                    "link",
                    ""
                )

                results.append({
                    "股票代號": stock_code,
                    "股票名稱": stock_name,
                    "新聞標題": title,
                    "摘要": summary,
                    "發布時間": published,
                    "連結": link,
                })

        except Exception:
            continue

    if not results:
        return pd.DataFrame(
            columns=[
                "股票代號",
                "股票名稱",
                "新聞標題",
                "摘要",
                "發布時間",
                "連結",
            ]
        )

    df = pd.DataFrame(results)

    return df.drop_duplicates(
        subset=["新聞標題"]
    ).head(max_items)


# ==============================================================================
# Yahoo 股價
# ==============================================================================

@st.cache_data(ttl=600)
def get_price_data(yahoo_symbol, start_date, end_date):

    try:

        start = pd.Timestamp(start_date) - pd.Timedelta(days=60)
        end = pd.Timestamp(end_date) + pd.Timedelta(days=35)

        df = yf.download(
            yahoo_symbol,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=False,
            progress=False,
            threads=False,
        )

        if df is None or df.empty:
            return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()

        if "Date" not in df.columns:
            return pd.DataFrame()

        df["Date"] = pd.to_datetime(
            df["Date"],
            errors="coerce"
        )

        return df

    except Exception:
        return pd.DataFrame()


# ==============================================================================
# 事件研究
# ==============================================================================

def calculate_event_study(
    yahoo_symbol,
    event_date,
    start_date,
    end_date,
    price_df=None
):

    # ========================================================
    # V3.5_SPEEDUP
    #
    # price_df 如果已提供，
    # 直接使用既有股價資料。
    #
    # 避免每一筆事件都重新下載 Yahoo 股價。
    # ========================================================

    if price_df is None:

        df = get_price_data(
            yahoo_symbol,
            start_date,
            end_date
        )

    else:

        df = price_df.copy()

    if df is None or df.empty:
        return {}

    required = [
        "Date",
        "Close",
        "Volume"
    ]

    if not all(
        c in df.columns
        for c in required
    ):
        return {}

    df = df.dropna(
        subset=[
            "Date",
            "Close"
        ]
    ).copy()

    df = df.sort_values(
        "Date"
    ).reset_index(
        drop=True
    )

    if df.empty:
        return {}

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce"
    )

    event_date = pd.Timestamp(
        event_date
    )

    # --------------------------------------------------------
    # 找事件日前最近一個交易日
    # --------------------------------------------------------

    before = df[
        df["Date"] <= event_date
    ]

    if before.empty:
        return {}

    event_idx = before.index[-1]

    event_close = float(
        df.loc[
            event_idx,
            "Close"
        ]
    )

    result = {

        "事件日前1日報酬":
            np.nan,

        "事件日前5日報酬":
            np.nan,

        "事件日報酬":
            np.nan,

        "+1日報酬":
            np.nan,

        "+3日報酬":
            np.nan,

        "+5日報酬":
            np.nan,

        "+10日報酬":
            np.nan,

        "+20日報酬":
            np.nan,

        "事件日成交量":
            np.nan,

        "20日均量":
            np.nan,

        "成交量倍數":
            np.nan,

        "AR_事件日":
            np.nan,

        "AR_+1":
            np.nan,

        "AR_+3":
            np.nan,

        "AR_+5":
            np.nan,

        "AR_+10":
            np.nan,

        "AR_+20":
            np.nan,

        "CAR_+1_+5":
            np.nan,

        "CAR_+1_+10":
            np.nan,

        "CAR_+1_+20":
            np.nan,
    }


    # ========================================================
    # 相對事件日報酬
    # ========================================================

    def ret_at(offset):

        idx = (
            event_idx
            + offset
        )

        if (
            idx < 0
            or idx >= len(df)
        ):
            return np.nan

        close = float(
            df.loc[
                idx,
                "Close"
            ]
        )

        if event_close == 0:
            return np.nan

        return (
            close
            / event_close
            - 1
        ) * 100


    # ========================================================
    # 事件前報酬
    # ========================================================

    if event_idx >= 1:

        result[
            "事件日前1日報酬"
        ] = (
            df.loc[
                event_idx,
                "Close"
            ]
            /
            df.loc[
                event_idx - 1,
                "Close"
            ]
            - 1
        ) * 100


    if event_idx >= 5:

        result[
            "事件日前5日報酬"
        ] = (
            df.loc[
                event_idx,
                "Close"
            ]
            /
            df.loc[
                event_idx - 5,
                "Close"
            ]
            - 1
        ) * 100


    # ========================================================
    # 事件後報酬
    # ========================================================

    result[
        "事件日報酬"
    ] = 0.0

    result[
        "+1日報酬"
    ] = ret_at(1)

    result[
        "+3日報酬"
    ] = ret_at(3)

    result[
        "+5日報酬"
    ] = ret_at(5)

    result[
        "+10日報酬"
    ] = ret_at(10)

    result[
        "+20日報酬"
    ] = ret_at(20)


    # ========================================================
    # 成交量
    # ========================================================

    try:

        event_volume = float(
            df.loc[
                event_idx,
                "Volume"
            ]
        )

        result[
            "事件日成交量"
        ] = event_volume

        start_idx = max(
            0,
            event_idx - 20
        )

        volume_base = df.loc[
            start_idx:
            event_idx - 1,
            "Volume"
        ]

        if len(
            volume_base
        ) > 0:

            avg_volume = float(
                volume_base.mean()
            )

            result[
                "20日均量"
            ] = avg_volume

            if avg_volume > 0:

                result[
                    "成交量倍數"
                ] = (
                    event_volume
                    /
                    avg_volume
                )

    except Exception:
        pass


    # ========================================================
    # AR / CAR
    #
    # 維持 V3.5 原本邏輯：
    # 事件前20交易日平均報酬
    # 作為簡化市場模型基準
    # ========================================================

    df[
        "Return"
    ] = (
        df[
            "Close"
        ].pct_change()
    )

    estimation = df.loc[
        max(
            1,
            event_idx - 20
        ):
        event_idx - 1,
        "Return"
    ].dropna()

    expected_return = (
        float(
            estimation.mean()
        )
        if len(
            estimation
        )
        else 0.0
    )

    ar = {}

    for offset, key in [

        (
            0,
            "AR_事件日"
        ),

        (
            1,
            "AR_+1"
        ),

        (
            3,
            "AR_+3"
        ),

        (
            5,
            "AR_+5"
        ),

        (
            10,
            "AR_+10"
        ),

        (
            20,
            "AR_+20"
        ),

    ]:

        idx = (
            event_idx
            + offset
        )

        if idx >= len(df):

            ar[
                key
            ] = np.nan

            continue

        daily_return = df.loc[
            idx,
            "Return"
        ]

        if pd.isna(
            daily_return
        ):

            ar[
                key
            ] = np.nan

        else:

            ar[
                key
            ] = (
                daily_return
                - expected_return
            ) * 100

    result.update(
        ar
    )


    # ========================================================
    # CAR
    # ========================================================

    def calculate_car(
        max_offset
    ):

        values = []

        for i in range(
            1,
            max_offset + 1
        ):

            idx = (
                event_idx
                + i
            )

            if idx >= len(df):
                break

            daily_return = df.loc[
                idx,
                "Return"
            ]

            if pd.isna(
                daily_return
            ):
                continue

            values.append(
                (
                    daily_return
                    - expected_return
                ) * 100
            )

        if not values:
            return np.nan

        return sum(
            values
        )


    result[
        "CAR_+1_+5"
    ] = calculate_car(
        5
    )

    result[
        "CAR_+1_+10"
    ] = calculate_car(
        10
    )

    result[
        "CAR_+1_+20"
    ] = calculate_car(
        20
    )

    return result


# ==============================================================================
# 單一股票分析
# ==============================================================================

def analyze_single_stock(
    stock_code,
    start_date,
    end_date
):

    universe = get_stock_universe()

    stock_code = normalize_code(
        stock_code
    )

    stock_info = universe[
        universe["股票代號"] == stock_code
    ]

    if stock_info.empty:

        stock_name = ""
        yahoo_symbol = stock_code + ".TW"
        market = ""
    else:

        row = stock_info.iloc[0]

        stock_name = row["股票名稱"]
        yahoo_symbol = row["Yahoo"]
        market = row["市場"]

    events = get_historical_official_events(
        start_date,
        end_date,
        stock_codes={stock_code}
    )

    # --------------------------------------------------------------------------
    # 如果官方 API 找不到，再嘗試 MOPS
    # --------------------------------------------------------------------------

    if events.empty:

        mops = get_mops_history(
            stock_code,
            start_date,
            end_date
        )

        if not mops.empty:

            info = mops[
                "完整訊息"
            ].fillna("").map(
                classify_event
            )

            info_df = pd.DataFrame(
                list(info)
            )

            events = pd.concat(
                [
                    mops.reset_index(drop=True),
                    info_df.reset_index(drop=True),
                ],
                axis=1
            )

    # --------------------------------------------------------------------------
    # 新聞
    # --------------------------------------------------------------------------

    news = search_news(
        stock_code,
        stock_name,
        max_items=15
    )

    # --------------------------------------------------------------------------
    # 股價事件研究
    # --------------------------------------------------------------------------

    event_rows = []

    if not events.empty:

        for _, event in events.iterrows():

            event_date = event.get(
                "日期_dt",
                pd.NaT
            )

            if pd.isna(event_date):
                continue

            study = calculate_event_study(
                yahoo_symbol,
                event_date,
                start_date,
                end_date
            )

            row = event.to_dict()
            row.update(study)

            event_rows.append(row)

    if event_rows:

        events_result = pd.DataFrame(
            event_rows
        )

    else:

        events_result = events.copy()

    return {
        "股票代號": stock_code,
        "股票名稱": stock_name,
        "市場": market,
        "events": events_result,
        "news": news,
    }


# ==============================================================================
# 全市場分析
# ==============================================================================

def analyze_market(
    start_date,
    end_date,
    progress_callback=None,
    deep_grades=("S", "A", "B")
):

    # ========================================================
    # V3.5_SPEEDUP
    # ========================================================

    universe = get_stock_universe()

    if universe.empty:

        return {
            "universe":
                universe,

            "events":
                pd.DataFrame(),

            "news":
                pd.DataFrame(),
        }


    # ========================================================
    # 第一步
    # 全市場官方重大訊息
    # ========================================================

    events = get_historical_official_events(
        start_date,
        end_date,
        stock_codes=None,
        progress_callback=
            progress_callback
    )

    if events.empty:

        return {
            "universe":
                universe,

            "events":
                events,

            "news":
                pd.DataFrame(),
        }


    # ========================================================
    # 股票基本資料 Map
    # ========================================================

    name_map = dict(
        zip(
            universe[
                "股票代號"
            ],
            universe[
                "股票名稱"
            ]
        )
    )

    market_map = dict(
        zip(
            universe[
                "股票代號"
            ],
            universe[
                "市場"
            ]
        )
    )

    yahoo_map = dict(
        zip(
            universe[
                "股票代號"
            ],
            universe[
                "Yahoo"
            ]
        )
    )


    # ========================================================
    # 股票名稱補充
    # ========================================================

    events[
        "股票名稱"
    ] = events[
        "股票名稱"
    ].replace(
        "",
        np.nan
    )

    events[
        "股票名稱"
    ] = events[
        "股票名稱"
    ].fillna(
        events[
            "股票代號"
        ].map(
            name_map
        )
    )


    # ========================================================
    # 市場補充
    # ========================================================

    events[
        "市場"
    ] = events[
        "市場"
    ].replace(
        "",
        np.nan
    )

    events[
        "市場"
    ] = events[
        "市場"
    ].fillna(
        events[
            "股票代號"
        ].map(
            market_map
        )
    )


    # ========================================================
    # 確認事件等級存在
    # ========================================================

    if (
        "事件等級"
        not in events.columns
    ):

        raise RuntimeError(
            "重大訊息缺少「事件等級」欄位，"
            "無法進行高速分級分析。"
        )


    # ========================================================
    # 預先建立事件研究欄位
    #
    # B/C 即使不進行事件研究，
    # 表格仍然有相同欄位，
    # 只是值為 NaN。
    # ========================================================

    study_columns = [

        "事件日前1日報酬",
        "事件日前5日報酬",
        "事件日報酬",

        "+1日報酬",
        "+3日報酬",
        "+5日報酬",
        "+10日報酬",
        "+20日報酬",

        "事件日成交量",
        "20日均量",
        "成交量倍數",

        "AR_事件日",
        "AR_+1",
        "AR_+3",
        "AR_+5",
        "AR_+10",
        "AR_+20",

        "CAR_+1_+5",
        "CAR_+1_+10",
        "CAR_+1_+20",
    ]

    for col in study_columns:

        if col not in events.columns:

            events[
                col
            ] = np.nan


    # ========================================================
    # 深度分析等級
    #
    # 預設：
    # S + A
    # ========================================================

    deep_grades = tuple(
        str(
            grade
        ).upper()
        for grade
        in deep_grades
    )

    deep_mask = events[
        "事件等級"
    ].astype(
        str
    ).str.upper().isin(
        deep_grades
    )


    # ========================================================
    # 加入分析狀態
    # ========================================================

    events[
        "深度分析狀態"
    ] = np.where(
        deep_mask,
        "完整分析",
        "略過重度分析"
    )


    # ========================================================
    # 只從 S/A 事件找股票
    # ========================================================

    deep_events = events[
        deep_mask
    ].copy()

    unique_codes = (
        deep_events[
            "股票代號"
        ]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )


    # ========================================================
    # 新聞結果
    # ========================================================

    news_rows = []


    # ========================================================
    # 如果完全沒有 S/A
    # ========================================================

    if not unique_codes:

        return {
            "universe":
                universe,

            "events":
                events,

            "news":
                pd.DataFrame(),
        }


    # ========================================================
    # Streamlit Progress
    # ========================================================

    grade_text = "/".join(
        deep_grades
    )

    progress = st.progress(
        0,
        text=(
            f"正在深度分析 "
            f"{grade_text} 級事件股票..."
        )
    )

    total = len(
        unique_codes
    )


    # ========================================================
    # V3.5_PRICE_DATE_BUFFER
    #
    # 事件研究需要：
    # - 事件前至少 20 個交易日
    # - 事件後最多 20 個交易日
    #
    # 因此背景股價資料自動向前、向後各延伸 60 天。
    # 使用者畫面上的查詢日期不會改變。
    # ========================================================

    query_start_ts = pd.Timestamp(
        start_date
    )

    query_end_ts = pd.Timestamp(
        end_date
    )

    price_start_date = (
        query_start_ts
        - pd.Timedelta(days=60)
    ).strftime(
        "%Y-%m-%d"
    )

    price_end_date = (
        query_end_ts
        + pd.Timedelta(days=60)
    ).strftime(
        "%Y-%m-%d"
    )


    # ========================================================
    # 股價 Cache
    #
    # 每檔股票只下載一次
    # ========================================================

    price_cache = {}


    # ========================================================
    # 每一檔 S/A 股票
    # ========================================================

    for i, code in enumerate(
        unique_codes
    ):

        stock_name = name_map.get(
            code,
            ""
        )

        yahoo_symbol = yahoo_map.get(
            code,
            code + ".TW"
        )


        # ====================================================
        # 新聞
        #
        # 每檔股票只搜尋一次
        # ====================================================

        try:

            news = search_news(
                code,
                stock_name,
                max_items=5
            )

            if (
                news is not None
                and not news.empty
            ):

                news_rows.extend(
                    news.to_dict(
                        "records"
                    )
                )

        except Exception:
            pass


        # ====================================================
        # 股價
        #
        # 每檔股票只下載一次
        # ====================================================

        if (
            yahoo_symbol
            not in price_cache
        ):

            try:

                price_cache[
                    yahoo_symbol
                ] = get_price_data(
                    yahoo_symbol,
                    price_start_date,
                    price_end_date
                )

            except Exception:

                price_cache[
                    yahoo_symbol
                ] = pd.DataFrame()


        price_df = price_cache.get(
            yahoo_symbol,
            pd.DataFrame()
        )


        # ====================================================
        # 只抓該股票 S/A 事件
        # ====================================================

        code_mask = (
            (
                events[
                    "股票代號"
                ].astype(str)
                == str(code)
            )
            &
            (
                events[
                    "事件等級"
                ].astype(str)
                .str.upper()
                .isin(
                    deep_grades
                )
            )
        )

        indices = events.index[
            code_mask
        ].tolist()


        # ====================================================
        # 日期 Cache
        #
        # 同一股票同一天若有多筆公告，
        # 股價事件研究結果相同，
        # 所以只計算一次。
        # ====================================================

        event_date_cache = {}


        for idx in indices:

            event_date = events.loc[
                idx,
                "日期_dt"
            ]

            if pd.isna(
                event_date
            ):
                continue


            # 日期統一
            date_key = pd.Timestamp(
                event_date
            ).normalize()


            # ================================================
            # 同一天第一次才計算
            # ================================================

            if (
                date_key
                not in event_date_cache
            ):

                try:

                    study = (
                        calculate_event_study(
                            yahoo_symbol,
                            event_date,
                            start_date,
                            end_date,
                            price_df=
                                price_df
                        )
                    )

                except Exception:

                    study = {}

                event_date_cache[
                    date_key
                ] = study


            # ================================================
            # 後續同日公告直接共用
            # ================================================

            study = event_date_cache.get(
                date_key,
                {}
            )

            for key, value in study.items():

                events.loc[
                    idx,
                    key
                ] = value


        # ====================================================
        # Progress
        # ====================================================

        progress.progress(
            int(
                (
                    (i + 1)
                    /
                    max(
                        total,
                        1
                    )
                )
                * 100
            ),
            text=(
                f"正在深度分析 "
                f"{grade_text} 級事件股票 "
                f"{i + 1}/{total}："
                f"{code} {stock_name}"
            )
        )


    # ========================================================
    # 清除 Progress
    # ========================================================

    progress.empty()


    # ========================================================
    # 新聞 DataFrame
    # ========================================================

    news_df = pd.DataFrame(
        news_rows
    )


    # ========================================================
    # 回傳
    #
    # 注意：
    # events 還是包含全部 S/A/B/C
    # ========================================================

    return {

        "universe":
            universe,

        "events":
            events,

        "news":
            news_df,
    }


# ==============================================================================
# Excel
# ==============================================================================

def create_excel(
    events,
    news,
    universe
):

    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        if universe is not None:
            universe.to_excel(
                writer,
                sheet_name="股票清單",
                index=False
            )

        if events is not None:
            events.to_excel(
                writer,
                sheet_name="重大訊息",
                index=False
            )

        if news is not None:
            news.to_excel(
                writer,
                sheet_name="新聞",
                index=False
            )

    output.seek(0)

    return output.getvalue()


# ==============================================================================
# Streamlit UI
# ==============================================================================

st.title(
    "📊 台股重大公開資訊新聞分析 V3.5"
)

st.caption(
    "官方重大訊息 × 新聞 × 事件研究 × AR/CAR × 全市場掃描"
)

st.divider()

# ------------------------------------------------------------------------------
# 側邊欄
# ------------------------------------------------------------------------------

with st.sidebar:

    st.header("⚙️ 查詢設定")

    mode = st.radio(
        "分析模式",
        [
            "🔎 單一股票",
            "🌐 全市場掃描",
        ]
    )

    today = datetime.now().date()

    start_date = st.date_input(
        "開始日期",
        value=today - timedelta(days=30)
    )

    end_date = st.date_input(
        "結束日期",
        value=today
    )

    if mode == "🔎 單一股票":

        stock_code = st.text_input(
            "股票代號",
            value="2330",
            placeholder="例如：2330、5351"
        )

    else:

        stock_code = ""

    st.divider()



# ==============================================================================
# 股票清單預覽
# ==============================================================================

universe = get_stock_universe()

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "目前掃描股票數",
        f"{len(universe):,}"
    )

with col2:

    listed_count = (
        len(
            universe[
                universe["市場"] == "上市"
            ]
        )
        if not universe.empty
        else 0
    )

    st.metric(
        "上市",
        f"{listed_count:,}"
    )

with col3:

    otc_count = (
        len(
            universe[
                universe["市場"] == "上櫃"
            ]
        )
        if not universe.empty
        else 0
    )

    st.metric(
        "上櫃",
        f"{otc_count:,}"
    )


# ==============================================================================
# 開始分析
# ==============================================================================

run = st.button(
    "🚀 開始分析",
    type="primary",
    use_container_width=True
)

if run:

    if start_date > end_date:

        st.error(
            "❌ 開始日期不能晚於結束日期。"
        )

        st.stop()

    # ==========================================================================
    # 單一股票
    # ==========================================================================

    if mode == "🔎 單一股票":

        code = normalize_code(
            stock_code
        )

        if not re.fullmatch(
            r"\d{4}",
            code
        ):

            st.error(
                "❌ 請輸入 4 碼股票代號，例如 2330。"
            )

            st.stop()

        with st.spinner(
            f"正在分析 {code}..."
        ):

            result = analyze_single_stock(
                code,
                start_date,
                end_date
            )

        events = result["events"]
        news = result["news"]

        st.success(
            f"✅ {code} 分析完成"
        )

        # ----------------------------------------------------------------------
        # 摘要
        # ----------------------------------------------------------------------

        if events.empty:

            st.warning(
                "目前查詢期間沒有抓到官方重大訊息。"
            )

        else:

            st.subheader(
                "📢 官方重大訊息"
            )

            st.dataframe(
                events,
                use_container_width=True,
                hide_index=True
            )

        st.subheader(
            "📰 相關新聞"
        )

        if news.empty:

            st.info(
                "目前沒有抓到相關新聞。"
            )

        else:

            st.dataframe(
                news,
                use_container_width=True,
                hide_index=True
            )

    # ==========================================================================
    # 全市場
    # ==========================================================================

    else:

        st.info(
            "🌐 全市場模式：先掃描官方重大訊息，"
            "再針對有事件的股票搜尋新聞與股價。"
        )

        with st.spinner(
            "正在掃描全市場官方重大訊息..."
        ):

            result = analyze_market(
                start_date,
                end_date
            )

        universe = result["universe"]
        events = result["events"]
        news = result["news"]

        # ----------------------------------------------------------------------
        # 統計
        # ----------------------------------------------------------------------

        if events.empty:

            st.warning(
                "目前查詢期間沒有抓到官方重大訊息。"
            )

            st.markdown(
                """
### 🔍 資料來源檢查

請注意：

- TWSE API：每日重大訊息
- TPEx API：每日重大訊息
- MOPS：歷史重大訊息查詢
- 若查詢日期不是最近交易日，TWSE / TPEx 每日 API
  不一定能直接提供整段歷史資料。

因此本版本會先顯示實際取得結果，
避免把「API 沒抓到」誤認成「市場沒有重大訊息」。
"""
            )

        else:

            st.success(
                f"✅ 找到 {len(events):,} 筆官方重大訊息"
            )

            unique_stock_count = (
                events["股票代號"]
                .nunique()
            )

            st.write(
                f"涉及股票：**{unique_stock_count:,} 檔**"
            )

            # ------------------------------------------------------------------
            # 等級統計
            # ------------------------------------------------------------------


            # V3.5_SCORE_GRADE_HELP_V2
            st.markdown(
                "### 📊 事件分數與 S／A／B／C 分級標準"
            )

            st.info(
                """
**① 關鍵字計分方式**

- 🟢 **強利多關鍵字**：每命中 1 個，正面分數 **+3**
- 🟢 **一般利多關鍵字**：每命中 1 個，正面分數 **+1**
- 🔴 **強利空關鍵字**：每命中 1 個，負面分數 **+3**
- 🔴 **一般利空關鍵字**：每命中 1 個，負面分數 **+1**

**事件分數 = 正面總分 − 負面總分**

例如：

- 正面 6 分、負面 1 分 → 事件分數 **+5**
- 正面 1 分、負面 4 分 → 事件分數 **-3**
- 正面 3 分、負面 3 分 → 事件分數 **0**

---

**② 情緒判斷**

- **事件分數 ≥ +3** → 🟢 正面
- **事件分數 ≤ -3** → 🔴 負面
- **事件分數為 -2、-1、+1、+2** → 🟡 混合
- **事件分數 = 0** → ⚪ 中性

---

**③ 重要度分數計算**

S／A／B／C 使用的是「重要度分數」，不是直接使用事件分數。

**重要度分數 = |事件分數|**

如果公告內有命中任何一個：

- 強利多關鍵字
- 強利空關鍵字

則：

**重要度分數再 +5**

---

**④ S／A／B／C 分級**

- 🔴 **S級：重要度分數 ≥ 8**
- 🟠 **A級：重要度分數 5～7**
- 🟡 **B級：重要度分數 2～4**
- ⚪ **C級：重要度分數 0～1**

---

**⑤ 事件等級與利多／利空不是同一件事**

- **事件分數正負** → 判斷利多或利空方向
- **情緒** → 正面／負面／混合／中性
- **事件等級** → 判斷事件的重要程度

因此：

**S級不代表一定利多。**

重大利空事件一樣可能是 S級。

例如「重大損失」：

- 命中強利空 → 負面分數 +3
- 事件分數 = **-3**
- 情緒 = **負面**
- 重要度分數 = `|-3| + 5 = 8`
- 最終 = **S級負面事件**
                """
            )

            c1, c2, c3, c4 = st.columns(4)

            with c1:
                st.metric(
                    "S級",
                    int(
                        (
                            events["事件等級"] == "S"
                        ).sum()
                    )
                )

            with c2:
                st.metric(
                    "A級",
                    int(
                        (
                            events["事件等級"] == "A"
                        ).sum()
                    )
                )

            with c3:
                st.metric(
                    "B級",
                    int(
                        (
                            events["事件等級"] == "B"
                        ).sum()
                    )
                )

            with c4:
                st.metric(
                    "C級",
                    int(
                        (
                            events["事件等級"] == "C"
                        ).sum()
                    )
                )

            # ------------------------------------------------------------------
            # 事件表
            # ------------------------------------------------------------------

            st.subheader(
                "📢 官方重大訊息分析"
            )

            display_cols = [
                "股票代號",
                "股票名稱",
                "市場",
                "日期",
                "事件等級",
                "情緒",
                "事件類型",
                "事件分數",
                "主旨",
                "來源",
                "+1日報酬",
                "+3日報酬",
                "+5日報酬",
                "+10日報酬",
                "+20日報酬",
                "成交量倍數",
                "AR_事件日",
                "AR_+1",
                "AR_+3",
                "AR_+5",
                "AR_+10",
                "AR_+20",
                "CAR_+1_+5",
                "CAR_+1_+10",
                "CAR_+1_+20",
            ]

            available_cols = [
                c
                for c in display_cols
                if c in events.columns
            ]

            st.dataframe(
                events[
                    available_cols
                ],
                use_container_width=True,
                hide_index=True
            )

            # ------------------------------------------------------------------
            # 新聞
            # ------------------------------------------------------------------

            st.subheader(
                "📰 事件股票新聞"
            )

            if news.empty:

                st.info(
                    "有官方重大訊息，但目前沒有抓到相關新聞。"
                )

            else:

                st.dataframe(
                    news,
                    use_container_width=True,
                    hide_index=True
                )

            # ------------------------------------------------------------------
            # 匯出
            # ------------------------------------------------------------------

            st.subheader(
                "📥 匯出"
            )

            excel_data = create_excel(
                events,
                news,
                universe
            )

            st.download_button(
                "📊 下載 Excel",
                data=excel_data,
                file_name=(
                    "台股重大公開資訊分析_V3.5.xlsx"
                ),
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                use_container_width=True
            )

            csv_data = events.to_csv(
                index=False,
                encoding="utf-8-sig"
            )

            st.download_button(
                "📄 下載重大訊息 CSV",
                data=csv_data,
                file_name=(
                    "台股重大訊息_V3.5.csv"
                ),
                mime="text/csv",
                use_container_width=True
            )


# ==============================================================================
# 頁尾
# ==============================================================================

st.divider()

st.caption(
    "台股重大公開資訊新聞分析 V3.5"
)


