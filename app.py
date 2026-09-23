
# ==============================================================================
# 台股重大公開資訊新聞分析 V2
# 上市 + 上櫃 + 興櫃
# ==============================================================================

import streamlit as st
import pandas as pd
import numpy as np
import requests
import feedparser
import urllib.parse
import re
import json
import io
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

# ==============================================================================
# 基本設定
# ==============================================================================

st.set_page_config(
    page_title="台股重大公開資訊新聞分析 V2",
    page_icon="📊",
    layout="wide"
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = BASE_DIR / "cache"
EXPORT_DIR = BASE_DIR / "exports"

DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


# ==============================================================================
# CSS
# ==============================================================================

st.markdown("""
<style>
.main-title {
    font-size: 30px;
    font-weight: 700;
}

.market-box {
    padding: 10px;
    border-radius: 8px;
    border: 1px solid #ddd;
    margin-bottom: 10px;
}

.small-text {
    color: #666;
    font-size: 13px;
}

.metric-title {
    font-size: 13px;
    color: #666;
}
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# 一、關鍵字
# ==============================================================================

IMPORTANT_KEYWORDS = {
    "重大訂單": [
        "大單",
        "重大訂單",
        "取得訂單",
        "接獲訂單",
        "訂單",
        "長約",
        "供貨合約",
        "供應合約",
        "大客戶",
        "核心客戶",
        "策略合作",
    ],

    "營收": [
        "營收",
        "營收創高",
        "營收新高",
        "營收成長",
        "營收增加",
        "營收衰退",
        "營收下降",
        "月增",
        "年增",
        "年減",
    ],

    "財報": [
        "財報",
        "財務報告",
        "毛利率",
        "營業利益",
        "營業利益率",
        "淨利",
        "獲利",
        "EPS",
        "每股盈餘",
        "盈餘",
        "虧損",
        "轉盈",
        "轉虧",
    ],

    "併購投資": [
        "併購",
        "收購",
        "合併",
        "投資",
        "參股",
        "入股",
        "策略投資",
        "轉投資",
        "出售持股",
    ],

    "產能擴充": [
        "擴廠",
        "擴產",
        "擴充產能",
        "新廠",
        "建廠",
        "產能",
        "資本支出",
        "CAPEX",
    ],

    "新產品": [
        "新產品",
        "新品",
        "產品上市",
        "量產",
        "量產出貨",
        "新技術",
        "技術突破",
        "研發成功",
    ],

    "法規監管": [
        "法規",
        "監管",
        "政策",
        "政府",
        "主管機關",
        "金管會",
        "證交所",
        "櫃買中心",
        "許可",
        "核准",
        "禁令",
    ],

    "訴訟法律": [
        "訴訟",
        "官司",
        "起訴",
        "判決",
        "裁罰",
        "罰款",
        "侵權",
        "專利訴訟",
        "法律",
    ],

    "人事變動": [
        "董事長",
        "總經理",
        "執行長",
        "CEO",
        "CFO",
        "高階主管",
        "人事異動",
        "董座",
        "辭任",
        "解任",
    ],

    "供應鏈": [
        "供應鏈",
        "供應商",
        "客戶",
        "缺料",
        "斷鏈",
        "供貨",
        "供應",
        "產業鏈",
    ],

    "產業趨勢": [
        "AI",
        "人工智慧",
        "半導體",
        "晶片",
        "伺服器",
        "資料中心",
        "電動車",
        "車用",
        "面板",
        "記憶體",
        "封裝",
        "IC設計",
    ],

    "重大風險": [
        "停工",
        "停產",
        "火災",
        "爆炸",
        "事故",
        "災害",
        "資安",
        "駭客",
        "勒索",
        "違約",
        "倒閉",
        "破產",
    ],
}

POSITIVE_KEYWORDS = [
    "創新高",
    "創高",
    "新高",
    "成長",
    "增加",
    "上升",
    "大增",
    "暴增",
    "獲利",
    "轉盈",
    "接單",
    "大單",
    "取得訂單",
    "擴產",
    "擴廠",
    "量產",
    "突破",
    "併購",
    "投資",
    "核准",
    "通過",
    "看好",
    "需求強勁",
    "強勁",
]

NEGATIVE_KEYWORDS = [
    "下跌",
    "下降",
    "衰退",
    "減少",
    "大減",
    "暴跌",
    "虧損",
    "轉虧",
    "裁員",
    "停工",
    "停產",
    "火災",
    "爆炸",
    "事故",
    "違約",
    "訴訟",
    "遭罰",
    "裁罰",
    "起訴",
    "破產",
    "倒閉",
    "資安事件",
    "駭客",
    "勒索",
    "禁令",
    "下修",
    "砍單",
    "缺料",
]


# ==============================================================================
# 二、上市股票資料
# ==============================================================================

@st.cache_data(ttl=86400)
def get_twse_stocks():

    urls = [
        "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
        "https://openapi.twse.com.tw/v1/opendata/t187ap03_L_Margin",
    ]

    rows = []

    for url in urls:
        try:
            r = requests.get(
                url,
                timeout=20,
                headers={"User-Agent": "Mozilla/5.0"}
            )

            if r.status_code != 200:
                continue

            data = r.json()

            if isinstance(data, list):
                for item in data:
                    code = str(
                        item.get("公司代號")
                        or item.get("證券代號")
                        or ""
                    ).strip()

                    name = str(
                        item.get("公司簡稱")
                        or item.get("證券名稱")
                        or ""
                    ).strip()

                    if (
                        code
                        and code.isdigit()
                        and len(code) == 4
                        and name
                    ):
                        rows.append({
                            "股票代號": code,
                            "公司名稱": name,
                            "市場": "上市",
                            "Yahoo代號": f"{code}.TW",
                        })

        except Exception:
            continue

    if not rows:
        return pd.DataFrame(
            columns=[
                "股票代號",
                "公司名稱",
                "市場",
                "Yahoo代號"
            ]
        )

    df = pd.DataFrame(rows)

    df = df.drop_duplicates(
        subset=["股票代號"],
        keep="first"
    )

    return df.reset_index(drop=True)


# ==============================================================================
# 三、上櫃股票
# ==============================================================================

@st.cache_data(ttl=86400)
def get_tpex_stocks():

    possible_urls = [
        "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis",
        "https://www.tpex.org.tw/openapi/v1/tpex_daily_market_value",
    ]

    rows = []

    for url in possible_urls:

        try:

            r = requests.get(
                url,
                timeout=20,
                headers={"User-Agent": "Mozilla/5.0"}
            )

            if r.status_code != 200:
                continue

            data = r.json()

            if not isinstance(data, list):
                continue

            for item in data:

                code = str(
                    item.get("SecuritiesCompanyCode")
                    or item.get("SecuritiesCompanyCode")
                    or item.get("代號")
                    or ""
                ).strip()

                name = str(
                    item.get("CompanyName")
                    or item.get("名稱")
                    or ""
                ).strip()

                if (
                    code
                    and code.isdigit()
                    and len(code) == 4
                    and name
                ):

                    rows.append({
                        "股票代號": code,
                        "公司名稱": name,
                        "市場": "上櫃",
                        "Yahoo代號": f"{code}.TWO",
                    })

        except Exception:
            continue

    if not rows:
        return pd.DataFrame(
            columns=[
                "股票代號",
                "公司名稱",
                "市場",
                "Yahoo代號"
            ]
        )

    df = pd.DataFrame(rows)

    df = df.drop_duplicates(
        subset=["股票代號"],
        keep="first"
    )

    return df.reset_index(drop=True)


# ==============================================================================
# 四、興櫃股票
# ==============================================================================

@st.cache_data(ttl=86400)
def get_esb_stocks():

    urls = [
        "https://www.tpex.org.tw/openapi/v1/tpex_esb_basic_info",
        "https://www.tpex.org.tw/openapi/v1/tpex_esb_company",
        "https://www.tpex.org.tw/openapi/v1/tpex_esb_latest_statistics",
    ]

    rows = []

    for url in urls:

        try:

            r = requests.get(
                url,
                timeout=20,
                headers={"User-Agent": "Mozilla/5.0"}
            )

            if r.status_code != 200:
                continue

            data = r.json()

            if not isinstance(data, list):
                continue

            for item in data:

                code = str(
                    item.get("SecuritiesCompanyCode")
                    or item.get("SecuritiesCompanyCode")
                    or item.get("代號")
                    or item.get("公司代號")
                    or ""
                ).strip()

                name = str(
                    item.get("CompanyName")
                    or item.get("公司簡稱")
                    or item.get("名稱")
                    or ""
                ).strip()

                if (
                    code
                    and code.isdigit()
                    and len(code) == 4
                    and name
                ):

                    rows.append({
                        "股票代號": code,
                        "公司名稱": name,
                        "市場": "興櫃",
                        "Yahoo代號": f"{code}.TWO",
                    })

        except Exception:
            continue

    if not rows:

        return pd.DataFrame(
            columns=[
                "股票代號",
                "公司名稱",
                "市場",
                "Yahoo代號"
            ]
        )

    df = pd.DataFrame(rows)

    df = df.drop_duplicates(
        subset=["股票代號"],
        keep="first"
    )

    return df.reset_index(drop=True)


# ==============================================================================
# 五、全部市場股票
# ==============================================================================

@st.cache_data(ttl=86400)
def get_all_stocks():

    twse = get_twse_stocks()
    tpex = get_tpex_stocks()
    esb = get_esb_stocks()

    frames = []

    for df in [twse, tpex, esb]:

        if df is not None and not df.empty:
            frames.append(df)

    if not frames:

        return pd.DataFrame(
            columns=[
                "股票代號",
                "公司名稱",
                "市場",
                "Yahoo代號"
            ]
        )

    df = pd.concat(
        frames,
        ignore_index=True
    )

    df = df.drop_duplicates(
        subset=["股票代號"],
        keep="first"
    )

    df = df.sort_values(
        ["市場", "股票代號"]
    )

    return df.reset_index(drop=True)


# ==============================================================================
# 六、新聞搜尋
# ==============================================================================

@st.cache_data(ttl=300)
def search_google_news(keyword, days=7):

    keyword = str(keyword).strip()

    if not keyword:
        return pd.DataFrame(
            columns=[
                "標題",
                "連結",
                "來源",
                "時間",
                "摘要",
                "搜尋關鍵字"
            ]
        )

    queries = [
        keyword,
        f'"{keyword}" 台股',
        f'"{keyword}" 股票',
        f'"{keyword}" 公司',
    ]

    if keyword.isdigit():

        queries.extend([
            f"{keyword} 台股",
            f"{keyword} 股票",
            f"{keyword} 上市",
            f"{keyword} 上櫃",
            f"{keyword} 興櫃",
        ])

    queries = list(
        dict.fromkeys(queries)
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/140.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "application/rss+xml, application/xml, "
            "text/xml, */*;q=0.8"
        ),
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    }

    now = datetime.now(timezone.utc)

    try:
        days_int = int(days)
    except Exception:
        days_int = 7

    cutoff = now - timedelta(days=days_int)

    all_rows = []
    errors = []

    for query in queries:

        try:

            encoded = urllib.parse.quote(query)

            url = (
                "https://news.google.com/rss/search"
                f"?q={encoded}"
                "&hl=zh-TW"
                "&gl=TW"
                "&ceid=TW:zh-Hant"
            )

            response = requests.get(
                url,
                headers=headers,
                timeout=20
            )

            if response.status_code != 200:

                errors.append(
                    f"{query}: HTTP {response.status_code}"
                )

                continue

            feed = feedparser.parse(
                response.content
            )

            for entry in feed.entries:

                title = str(
                    getattr(
                        entry,
                        "title",
                        ""
                    )
                ).strip()

                link = str(
                    getattr(
                        entry,
                        "link",
                        ""
                    )
                ).strip()

                if not title:
                    continue

                summary = str(
                    getattr(
                        entry,
                        "summary",
                        ""
                    )
                )

                summary = re.sub(
                    r"<[^>]+>",
                    "",
                    summary
                ).strip()

                published_dt = None

                try:

                    if getattr(
                        entry,
                        "published_parsed",
                        None
                    ):

                        import calendar

                        timestamp = calendar.timegm(
                            entry.published_parsed
                        )

                        published_dt = datetime.fromtimestamp(
                            timestamp,
                            tz=timezone.utc
                        )

                except Exception:
                    published_dt = None

                if published_dt is None:

                    try:

                        if getattr(
                            entry,
                            "updated_parsed",
                            None
                        ):

                            import calendar

                            timestamp = calendar.timegm(
                                entry.updated_parsed
                            )

                            published_dt = datetime.fromtimestamp(
                                timestamp,
                                tz=timezone.utc
                            )

                    except Exception:
                        published_dt = None

                if published_dt is None:
                    published_dt = now

                if published_dt < cutoff:
                    continue

                source = ""

                try:
                    source = str(
                        entry.source.get("title", "")
                    ).strip()
                except Exception:
                    source = ""

                if not source:
                    source = "Google News"

                all_rows.append({
                    "標題": title,
                    "連結": link,
                    "來源": source,
                    "時間": (
                        published_dt
                        .astimezone()
                        .replace(tzinfo=None)
                    ),
                    "摘要": summary,
                    "搜尋關鍵字": query,
                })

        except Exception as e:

            errors.append(
                f"{query}: {type(e).__name__} - {str(e)}"
            )

    if not all_rows:

        return pd.DataFrame(
            columns=[
                "標題",
                "連結",
                "來源",
                "時間",
                "摘要",
                "搜尋關鍵字"
            ]
        )

    news_df = pd.DataFrame(
        all_rows
    )

    if "連結" in news_df.columns:
        news_df = news_df.drop_duplicates(
            subset=["連結"],
            keep="first"
        )

    news_df = news_df.drop_duplicates(
        subset=["標題"],
        keep="first"
    )

    news_df = news_df.sort_values(
        "時間",
        ascending=False
    ).reset_index(drop=True)

    return news_df


# ==============================================================================
# 七、新聞分類
# ==============================================================================

def classify_news(title, summary=""):

    text = (
        str(title)
        + " "
        + str(summary)
    )

    category_scores = {}

    for category, keywords in IMPORTANT_KEYWORDS.items():

        score = 0

        for keyword in keywords:

            if keyword.lower() in text.lower():
                score += 1

        category_scores[category] = score

    if category_scores:

        category = max(
            category_scores,
            key=category_scores.get
        )

        score = category_scores[category]

    else:

        category = "一般新聞"
        score = 0

    positive = sum(
        1
        for keyword in POSITIVE_KEYWORDS
        if keyword.lower() in text.lower()
    )

    negative = sum(
        1
        for keyword in NEGATIVE_KEYWORDS
        if keyword.lower() in text.lower()
    )

    if positive > negative:
        direction = "偏正面"

    elif negative > positive:
        direction = "偏負面"

    else:
        direction = "中性／不明確"

    return (
        category,
        score,
        direction,
        positive,
        negative
    )


# ==============================================================================
# 八、股票辨識
# ==============================================================================

def identify_stock(keyword, stock_df):

    if stock_df is None or stock_df.empty:
        return None

    keyword = str(keyword).strip()

    # 股票代號
    exact_code = stock_df[
        stock_df["股票代號"].astype(str) == keyword
    ]

    if not exact_code.empty:
        return exact_code.iloc[0]

    # 完整公司名稱
    exact_name = stock_df[
        stock_df["公司名稱"].astype(str) == keyword
    ]

    if not exact_name.empty:
        return exact_name.iloc[0]

    # 部分名稱
    contains_name = stock_df[
        stock_df["公司名稱"].astype(str).str.contains(
            keyword,
            case=False,
            na=False
        )
    ]

    if not contains_name.empty:
        return contains_name.iloc[0]

    return None


# ==============================================================================
# 九、價格資料
# ==============================================================================

@st.cache_data(ttl=3600)
def download_price(
    yahoo_symbol,
    years=5
):

    try:

        import yfinance as yf

        end = datetime.now()

        start = end - timedelta(
            days=int(years) * 365
        )

        df = yf.download(
            yahoo_symbol,
            start=start.strftime("%Y-%m-%d"),
            end=(end + timedelta(days=1)).strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=False,
            threads=False,
        )

        if df is None or df.empty:
            return pd.DataFrame()

        if isinstance(
            df.columns,
            pd.MultiIndex
        ):

            try:
                df.columns = df.columns.get_level_values(0)
            except Exception:
                pass

        df = df.reset_index()

        if "Date" not in df.columns:
            return pd.DataFrame()

        if "Close" not in df.columns:
            return pd.DataFrame()

        df["Date"] = pd.to_datetime(
            df["Date"]
        ).dt.tz_localize(None)

        df["Close"] = pd.to_numeric(
            df["Close"],
            errors="coerce"
        )

        df = df[
            ["Date", "Close"]
        ].dropna()

        return df.reset_index(
            drop=True
        )

    except Exception:

        return pd.DataFrame()


# ==============================================================================
# 十、事件報酬計算
# ==============================================================================

def calculate_event_returns(
    price_df,
    event_date
):

    result = {
        "+1交易日": np.nan,
        "+3交易日": np.nan,
        "+5交易日": np.nan,
        "+10交易日": np.nan,
        "+20交易日": np.nan,
    }

    if price_df is None or price_df.empty:
        return result

    df = price_df.copy()

    df["Date"] = pd.to_datetime(
        df["Date"]
    ).dt.normalize()

    event_date = pd.to_datetime(
        event_date
    ).normalize()

    # 找到事件日當天或之後第一個交易日
    candidates = df[
        df["Date"] >= event_date
    ]

    if candidates.empty:
        return result

    event_index = candidates.index[0]

    base_price = df.loc[
        event_index,
        "Close"
    ]

    if (
        pd.isna(base_price)
        or base_price == 0
    ):
        return result

    horizons = {
        "+1交易日": 1,
        "+3交易日": 3,
        "+5交易日": 5,
        "+10交易日": 10,
        "+20交易日": 20,
    }

    for label, offset in horizons.items():

        target_index = event_index + offset

        if target_index >= len(df):
            continue

        target_price = df.iloc[
            target_index
        ]["Close"]

        if pd.isna(target_price):
            continue

        result[label] = (
            float(target_price)
            / float(base_price)
            - 1
        ) * 100

    return result


# ==============================================================================
# 十一、統計摘要
# ==============================================================================

def build_statistics(event_df):

    horizons = [
        "+1交易日",
        "+3交易日",
        "+5交易日",
        "+10交易日",
        "+20交易日",
    ]

    rows = []

    for horizon in horizons:

        if horizon not in event_df.columns:
            continue

        series = pd.to_numeric(
            event_df[horizon],
            errors="coerce"
        ).dropna()

        if series.empty:

            rows.append({
                "期間": horizon,
                "樣本數": 0,
                "平均": np.nan,
                "中位數": np.nan,
                "上漲比例": np.nan,
                "最大漲幅": np.nan,
                "最大跌幅": np.nan,
                "Q25": np.nan,
                "Q75": np.nan,
            })

            continue

        rows.append({
            "期間": horizon,
            "樣本數": len(series),
            "平均": series.mean(),
            "中位數": series.median(),
            "上漲比例": (
                (series > 0).mean() * 100
            ),
            "最大漲幅": series.max(),
            "最大跌幅": series.min(),
            "Q25": series.quantile(0.25),
            "Q75": series.quantile(0.75),
        })

    return pd.DataFrame(rows)


# ==============================================================================
# 十二、Excel 匯出
# ==============================================================================

def create_excel(
    news_df,
    event_df,
    stats_df,
    stock_info
):

    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        if stock_info is not None:
            pd.DataFrame(
                [stock_info]
            ).to_excel(
                writer,
                index=False,
                sheet_name="股票資訊"
            )

        if news_df is not None:
            news_df.to_excel(
                writer,
                index=False,
                sheet_name="新聞"
            )

        if event_df is not None:
            event_df.to_excel(
                writer,
                index=False,
                sheet_name="事件分析"
            )

        if stats_df is not None:
            stats_df.to_excel(
                writer,
                index=False,
                sheet_name="統計摘要"
            )

    output.seek(0)

    return output.getvalue()


# ==============================================================================
# 十三、標題
# ==============================================================================

st.markdown(
    '<div class="main-title">'
    '📊 台股重大公開資訊新聞分析 V2'
    '</div>',
    unsafe_allow_html=True
)

st.caption(
    "上市＋上櫃＋興櫃｜新聞事件研究｜歷史報酬統計"
)

st.divider()


# ==============================================================================
# 十四、取得股票清單
# ==============================================================================

with st.spinner("正在更新上市／上櫃／興櫃股票清單..."):

    stock_df = get_all_stocks()

market_counts = {}

if not stock_df.empty:

    market_counts = (
        stock_df["市場"]
        .value_counts()
        .to_dict()
    )

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "股票總數",
        f"{len(stock_df):,}"
    )

with col2:
    st.metric(
        "上市",
        f"{market_counts.get('上市', 0):,}"
    )

with col3:
    st.metric(
        "上櫃",
        f"{market_counts.get('上櫃', 0):,}"
    )

with col4:
    st.metric(
        "興櫃",
        f"{market_counts.get('興櫃', 0):,}"
    )


# ==============================================================================
# 十五、側邊欄
# ==============================================================================

st.sidebar.header("⚙️ 分析設定")

market_option = st.sidebar.selectbox(
    "市場",
    [
        "全部",
        "上市",
        "上櫃",
        "興櫃",
    ]
)

keyword = st.sidebar.text_input(
    "公司名稱／股票代號",
    value="台積電",
    placeholder="例如：台積電、2330"
)

news_days = st.sidebar.slider(
    "新聞搜尋天數",
    min_value=1,
    max_value=30,
    value=7
)

history_years = st.sidebar.slider(
    "歷史價格年數",
    min_value=1,
    max_value=10,
    value=5
)

news_limit = st.sidebar.slider(
    "最多分析新聞數",
    min_value=5,
    max_value=100,
    value=30
)


# ==============================================================================
# 十六、搜尋股票
# ==============================================================================

if stock_df.empty:

    st.error(
        "目前沒有成功取得市場股票清單。"
    )

    st.info(
        "請確認網路連線，或稍後重新整理頁面。"
    )

    st.stop()


filtered_stocks = stock_df.copy()

if market_option != "全部":

    filtered_stocks = filtered_stocks[
        filtered_stocks["市場"] == market_option
    ]

matched_stock = identify_stock(
    keyword,
    filtered_stocks
)


# ==============================================================================
# 十七、股票資訊
# ==============================================================================

if matched_stock is not None:

    stock_info = matched_stock.to_dict()

    st.subheader("🏢 股票資訊")

    info1, info2, info3, info4 = st.columns(4)

    with info1:
        st.metric(
            "股票代號",
            stock_info["股票代號"]
        )

    with info2:
        st.metric(
            "公司名稱",
            stock_info["公司名稱"]
        )

    with info3:
        st.metric(
            "市場",
            stock_info["市場"]
        )

    with info4:
        st.metric(
            "Yahoo代號",
            stock_info["Yahoo代號"]
        )

else:

    stock_info = None

    st.warning(
        f"找不到「{keyword}」對應的股票。"
    )

    st.info(
        "可以輸入股票代號，例如 2330，"
        "或輸入公司名稱，例如 台積電。"
    )

    with st.expander("查看目前股票清單"):

        search_list = filtered_stocks[
            filtered_stocks["公司名稱"].str.contains(
                keyword,
                case=False,
                na=False
            )
            |
            filtered_stocks["股票代號"].str.contains(
                keyword,
                case=False,
                na=False
            )
        ]

        if search_list.empty:
            st.dataframe(
                filtered_stocks.head(100),
                use_container_width=True
            )
        else:
            st.dataframe(
                search_list.head(100),
                use_container_width=True
            )


# ==============================================================================
# 十八、開始分析
# ==============================================================================

start_analysis = st.button(
    "🔍 開始重大新聞分析",
    type="primary",
    use_container_width=True
)

if start_analysis:

    if matched_stock is None:

        st.error(
            "請先輸入正確的上市、上櫃或興櫃股票。"
        )

        st.stop()

    company_name = stock_info["公司名稱"]
    stock_code = stock_info["股票代號"]
    market = stock_info["市場"]
    yahoo_symbol = stock_info["Yahoo代號"]

    st.subheader(
        f"📰 {stock_code} {company_name} 重大新聞"
    )

    # --------------------------------------------------------------------------
    # 新聞
    # --------------------------------------------------------------------------

    with st.spinner("正在搜尋 Google News..."):

        news_df = search_google_news(
            company_name,
            news_days
        )

    if news_df.empty:

        st.warning(
            "目前沒有抓到符合條件的新聞。"
        )

        st.stop()

    # 限制數量
    news_df = news_df.head(
        news_limit
    ).copy()

    # --------------------------------------------------------------------------
    # 新聞分類
    # --------------------------------------------------------------------------

    categories = []
    scores = []
    directions = []
    positives = []
    negatives = []

    for _, row in news_df.iterrows():

        category, score, direction, positive, negative = classify_news(
            row["標題"],
            row["摘要"]
        )

        categories.append(category)
        scores.append(score)
        directions.append(direction)
        positives.append(positive)
        negatives.append(negative)

    news_df["重大類型"] = categories
    news_df["關鍵字分數"] = scores
    news_df["影響方向"] = directions
    news_df["正面關鍵字數"] = positives
    news_df["負面關鍵字數"] = negatives

    # --------------------------------------------------------------------------
    # 顯示新聞
    # --------------------------------------------------------------------------

    st.success(
        f"成功取得 {len(news_df)} 則新聞"
    )

    display_news = news_df[
        [
            "時間",
            "來源",
            "標題",
            "重大類型",
            "影響方向",
            "關鍵字分數",
        ]
    ].copy()

    st.dataframe(
        display_news,
        use_container_width=True,
        hide_index=True
    )

    # --------------------------------------------------------------------------
    # 歷史價格
    # --------------------------------------------------------------------------

    st.subheader("📈 歷史事件報酬分析")

    with st.spinner(
        f"正在取得 {market} 歷史價格資料..."
    ):

        price_df = download_price(
            yahoo_symbol,
            history_years
        )

    if price_df.empty:

        st.warning(
            f"目前無法取得 {market}「{company_name}」"
            "的歷史價格資料。"
        )

        st.info(
            "新聞分析仍可使用；"
            "但目前無法計算 +1／+3／+5／+10／+20 "
            "交易日歷史報酬。"
        )

        event_df = news_df.copy()

    else:

        # --------------------------------------------------------------
        # 建立事件報酬
        # --------------------------------------------------------------

        event_rows = []

        for _, row in news_df.iterrows():

            returns = calculate_event_returns(
                price_df,
                row["時間"]
            )

            event_row = row.to_dict()

            event_row.update(
                returns
            )

            event_rows.append(
                event_row
            )

        event_df = pd.DataFrame(
            event_rows
        )

        # --------------------------------------------------------------
        # 統計
        # --------------------------------------------------------------

        stats_df = build_statistics(
            event_df
        )

        # --------------------------------------------------------------
        # 顯示統計
        # --------------------------------------------------------------

        st.subheader(
            "📊 歷史事件統計"
        )

        if not stats_df.empty:

            formatted_stats = stats_df.copy()

            percentage_columns = [
                "平均",
                "中位數",
                "上漲比例",
                "最大漲幅",
                "最大跌幅",
                "Q25",
                "Q75",
            ]

            for col in percentage_columns:

                if col in formatted_stats.columns:

                    formatted_stats[col] = (
                        pd.to_numeric(
                            formatted_stats[col],
                            errors="coerce"
                        )
                        .round(2)
                    )

            st.dataframe(
                formatted_stats,
                use_container_width=True,
                hide_index=True
            )

        # --------------------------------------------------------------
        # 主要指標
        # --------------------------------------------------------------

        st.subheader(
            "📌 歷史事件主要指標"
        )

        metric_columns = [
            "+1交易日",
            "+3交易日",
            "+5交易日",
            "+10交易日",
            "+20交易日",
        ]

        cols = st.columns(5)

        for i, horizon in enumerate(
            metric_columns
        ):

            if horizon not in event_df.columns:
                continue

            values = pd.to_numeric(
                event_df[horizon],
                errors="coerce"
            ).dropna()

            with cols[i]:

                if values.empty:

                    st.metric(
                        horizon,
                        "無資料"
                    )

                else:

                    st.metric(
                        horizon,
                        f"{values.mean():.2f}%"
                    )

        # --------------------------------------------------------------
        # 報酬圖
        # --------------------------------------------------------------

        chart_data = []

        for horizon in metric_columns:

            if horizon not in event_df.columns:
                continue

            values = pd.to_numeric(
                event_df[horizon],
                errors="coerce"
            ).dropna()

            if not values.empty:

                chart_data.append({
                    "期間": horizon,
                    "平均報酬": values.mean()
                })

        if chart_data:

            chart_df = pd.DataFrame(
                chart_data
            ).set_index("期間")

            st.bar_chart(
                chart_df["平均報酬"]
            )

    # --------------------------------------------------------------------------
    # 完整事件資料
    # --------------------------------------------------------------------------

    st.subheader(
        "🔎 完整事件分析"
    )

    st.dataframe(
        event_df,
        use_container_width=True,
        hide_index=True
    )

    # --------------------------------------------------------------------------
    # 下載
    # --------------------------------------------------------------------------

    st.subheader(
        "📥 匯出資料"
    )

    csv_data = event_df.to_csv(
        index=False,
        encoding="utf-8-sig"
    )

    st.download_button(
        "下載 CSV",
        data=csv_data,
        file_name=(
            f"{stock_code}_{company_name}_"
            "重大新聞分析.csv"
        ),
        mime="text/csv"
    )

    if price_df.empty:

        stats_for_export = pd.DataFrame()

    else:

        stats_for_export = build_statistics(
            event_df
        )

    excel_data = create_excel(
        news_df,
        event_df,
        stats_for_export,
        stock_info
    )

    st.download_button(
        "下載 Excel",
        data=excel_data,
        file_name=(
            f"{stock_code}_{company_name}_"
            "重大新聞分析.xlsx"
        ),
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )


# ==============================================================================
# 十九、全部股票清單
# ==============================================================================

with st.expander(
    "📋 查看上市／上櫃／興櫃股票清單"
):

    st.caption(
        f"目前取得 {len(stock_df):,} 檔股票"
    )

    st.dataframe(
        stock_df,
        use_container_width=True,
        hide_index=True
    )


# ==============================================================================
# 二十、說明
# ==============================================================================

st.divider()

st.caption(
    "V2｜上市＋上櫃＋興櫃"
)

st.caption(
    "本系統的歷史報酬屬於事件研究統計，"
    "不代表未來一定會出現相同報酬。"
)

st.caption(
    "新聞資料來自公開新聞 RSS；"
    "市場股票名單優先採用官方公開資料。"
)
