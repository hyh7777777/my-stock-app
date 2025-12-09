import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="미국 주식 분석기 Pro")

# --- [기능] 파일 저장/불러오기 ---
CSV_FILE = 'my_portfolio.csv'

def load_portfolio_from_csv():
    if os.path.exists(CSV_FILE):
        try:
            df = pd.read_csv(CSV_FILE)
            return df.to_dict('records')
        except: return []
    return []

def save_portfolio_to_csv(portfolio_data):
    if portfolio_data:
        df = pd.DataFrame(portfolio_data)
        df.to_csv(CSV_FILE, index=False)

# --- [기능] 세션 초기화 ---
if 'search_history' not in st.session_state: st.session_state.search_history = []
if 'portfolio' not in st.session_state: st.session_state.portfolio = load_portfolio_from_csv()

def set_ticker(t): st.session_state.ticker_input = t

# --- [함수] 캐싱된 데이터 가져오기 ---
@st.cache_data(ttl=300) 
def fetch_stock_history(ticker, period, interval):
    try: return yf.Ticker(ticker).history(period=period, interval=interval)
    except: return pd.DataFrame()

@st.cache_data(ttl=600)
def fetch_stock_info(ticker):
    try: return yf.Ticker(ticker).info
    except: return {}
        
@st.cache_data(ttl=600)
def fetch_stock_news(ticker):
    try: return yf.Ticker(ticker).news
    except: return []

# --- [함수] 뉴스 파싱 헬퍼 함수 (에러 방지용) ---
def get_safe_news_data(news_item):
    """복잡한 뉴스 데이터에서 제목과 링크를 안전하게 추출"""
    content = news_item.get('content', {})
    
    # 제목 찾기
    title = news_item.get('title')
    if not title: title = content.get('title', '제목 없음')
    
    # 링크 찾기
    link = news_item.get('link')
    if not link: link = news_item.get('clickThroughUrl', {}).get('url')
    if not link: link = content.get('clickThroughUrl', {}).get('url')
    if not link: link = content.get('canonicalUrl', {}).get('url')
    
    return title, link

# --- [함수] 분석 함수들 ---
def get_stock_info_str(info):
    try:
        sector = info.get('sector', '기타'); industry = info.get('industry', '기타')
        mkt_cap = info.get('marketCap', 0); pe_ratio = info.get('trailingPE', 0)
        size = "대형" if mkt_cap >= 10000000000 else "중형" if mkt_cap >= 2000000000 else "소형"
        style = "성장" if pe_ratio > 30 else "가치" if pe_ratio > 0 else "복합"
        return f"{sector} > {industry} ({size}{style})"
    except: return "분석 데이터 없음"

def add_technical_indicators(df):
    if len(df) < 20: return df
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = df['EMA12'] - df['EMA26']
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['STD'] = df['Close'].rolling(window=20).std()
    df['Upper'] = df['MA20'] + (df['STD'] * 2)
    df['Lower'] = df['MA20'] - (df['STD'] * 2)
    return df

def analyze_stock(df):
    score = 0; reasons = []
    if len(df) < 60: return 0, "C", ["데이터 부족"]
    df = add_technical_indicators(df)
    current = df.iloc[-1]; prev = df.iloc[-2]
    ma20 = current['MA20']; ma60 = df['Close'].rolling(window=60).mean().iloc[-1]
    if current['Close'] > ma20: score += 20; reasons.append("주가 > 20일선 (상승세)")
    if ma20 > ma60: score += 20; reasons.append("20일선 > 60일선 (정배열)")
    vol_ma20 = df['Volume'].rolling(window=20).mean().iloc[-1]
    if current['Volume'] > vol_ma20: score += 10; reasons.append("거래량 급증")
    if current['Close'] > prev['Close'] and current['Volume'] > prev['Volume']: score += 10; reasons.append("거래량 실린 상승")
    if current['RSI'] > 50: score += 10; reasons.append("RSI 매수 우위")
    if current['RSI'] >= 70: reasons.append("⚠️ RSI 과매수")
    else: score += 10
    if current['MACD'] > current['Signal']: score += 20; reasons.append("MACD 골든크로스")
    elif current['MACD'] > 0: score += 10; reasons.append("MACD 상승 추세")
    if score >= 90: grade = "S (강력매수)"
    elif score >= 70: grade = "A (매수)"
    elif score >= 50: grade = "B (중립)"
    else: grade = "C (관망)"
    return score, grade, reasons

# ==========================================
# [사이드바]
# ==========================================
st.sidebar.title("🔍 검색 옵션")
ticker = st.sidebar.text_input("종목 코드", "AAPL", key="ticker_input")
st.sidebar.markdown("---")
chart_type = st.sidebar.selectbox("차트 선택", ["일봉 (Daily)", "주봉 (Weekly)", "월봉 (Monthly)", "분봉 (Intraday)"])
st.sidebar.subheader("📈 차트 보조지표")
show_bb = st.sidebar.checkbox("볼린저 밴드", value=True)
show_ma = st.sidebar.checkbox("이동평균선", value=True)
st.sidebar.markdown("---")
st.sidebar.subheader("🤖 AI 분석 대상")
default_tickers = "NVDA, TSLA, AAPL, MSFT, GOOGL, AMZN, META, AMD, PLTR, COIN, NFLX, INTC"
user_tickers = st.sidebar.text_area("분석 리스트", value=default_tickers, height=100)
target_tickers = [t.strip().upper() for t in user_tickers.split(',') if t.strip()]

if st.session_state.search_history:
    st.sidebar.markdown("---")
    for past_ticker in st.session_state.search_history[:5]:
        if st.sidebar.button(f"📌 {past_ticker}", key=f"hist_{past_ticker}", use_container_width=True):
            set_ticker(past_ticker); st.rerun()
    if st.sidebar.button("🗑️ 기록 삭제"): st.session_state.search_history = []; st.rerun()

# ==========================================
# [메인] 시장 지수
# ==========================================
st.title("🌎 글로벌 시장 현황")
indices = {"S&P 500": "^GSPC", "나스닥": "^IXIC", "다우존스": "^DJI", "원/달러": "KRW=X"}
cols = st.columns(4)
for col, (name, symbol) in zip(cols, indices.items()):
    try:
        data = fetch_stock_history(symbol, "5d", "1d")
        if len(data) >= 2:
            cur = data['Close'].iloc[-1]; pre = data['Close'].iloc[-2]
            d_pct = ((cur - pre) / pre) * 100
            col.metric(name, f"{cur:,.2f}", f"{d_pct:.2f}%")
    except: col.metric(name, "Loading...")
st.markdown("---")

# ==========================================
# [탭 구성]
# ==========================================
tab1, tab2, tab3 = st.tabs(["🚀 종목 상세 분석", "🏆 AI 유망 종목", "💰 내 포트폴리오 (저장/불러오기)"])

# TAB 1: 상세 분석
with tab1:
    if ticker:
        ticker = ticker.upper().strip()
        if ticker not in st.session_state.search_history:
            st.session_state.search_history.insert(0, ticker)
            if len(st.session_state.search_history) > 20: st.session_state.search_history.pop()

        info = fetch_stock_info(ticker)
        if info:
            stock_desc = get_stock_info_str(info)
            cur_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
            prev_close = info.get('previousClose', 0)
            chg = cur_price - prev_close
            chg_pct = (chg / prev_close) * 100 if prev_close else 0
            color = "red" if chg > 0 else "blue" if chg < 0 else "gray"

            col_i, col_b = st.columns([3, 1])
            with col_i:
                st.markdown(f"""
                <div style="padding:15px; border-radius:10px; background-color:#262730; margin-bottom:10px;">
                    <div style="display:flex; align-items:center; gap:10px;">
                        <h2 style="margin:0; color:white;">{ticker}: ${cur_price:,.2f}</h2>
                        <span style="background-color:#444; color:#00E676; padding:2px 8px; border-radius:5px; font-size:0.8em;">{stock_desc}</span>
                    </div>
                    <h3 style="margin:5px 0 0 0; color:{color};">({chg:+.2f}, {chg_pct:+.2f}%)</h3>
                </div>""", unsafe_allow_html=True)
            with col_b:
                st.write(""); st.write("")
                if st.button(f"➕ 가상 매수", use_container_width=True):
                    st.session_state.portfolio.append({"ticker": ticker, "buy_price": cur_price, "qty": 1, "date": datetime.now().strftime("%Y-%m-%d")})
                    save_portfolio_to_csv(st.session_state.portfolio)
                    st.toast("포트폴리오에 추가하고 저장했습니다!", icon="💾")

            # 차트
            period = "max"; interval = "1d"; end = datetime.now()
            if chart_type == "일봉 (Daily)": interval="1d"; period="2y"; start=end-timedelta(days=150)
            elif chart_type == "주봉 (Weekly)": interval="1wk"; period="5y"; start=end-timedelta(days=365*2)
            elif chart_type == "월봉 (Monthly)": interval="1mo"; period="max"; start=end-timedelta(days=365*5)
            elif chart_type == "분봉 (Intraday)":
                opt = st.sidebar.selectbox("시간", ["1분", "15분", "30분", "60분"]); mapping={"1분":"1m","15분":"15m","30분":"30m","60분":"60m"}
                interval=mapping[opt]; period="5d"; start=end-timedelta(days=2)

            df = fetch_stock_history(ticker, period, interval)
            if len(df) > 0:
                df = add_technical_indicators(df)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], increasing_line_color='#ef3636', decreasing_line_color='#1d5cff', name="캔들"), row=1, col=1)
                if show_bb and chart_type in ["일봉 (Daily)", "주봉 (Weekly)"]:
                    fig.add_trace(go.Scatter(x=df.index, y=df['Upper'], line=dict(color='gray', width=1, dash='dot'), name='BB 상단'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df.index, y=df['Lower'], line=dict(color='gray', width=1, dash='dot'), name='BB 하단', fill='tonexty', fillcolor='rgba(255,255,255,0.05)'), row=1, col=1)
                if show_ma and chart_type != "분봉 (Intraday)":
                    for ma, c in zip(['MA20', 'MA60'], ['#FFD700', 'blue']):
                        if ma in df.columns: fig.add_trace(go.Scatter(x=df.index, y=df[ma], line=dict(color=c, width=1), name=ma), row=1, col=1)
                colors = ['#ef3636' if r['Close']>=r['Open'] else '#1d5cff' for _, r in df.iterrows()]
                fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name="거래량"), row=2, col=1)
                fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10,t=30,r=10,b=10), legend=dict(orientation="h", y=1.02, x=1))
                fig.update_yaxes(side="right")
                if chart_type != "분봉 (Intraday)": fig.update_xaxes(range=[start, end], row=1, col=1); fig.update_xaxes(range=[start, end], row=2, col=1)
                st.plotly_chart(fig, use_container_width=True)

            st_t1, st_t2, st_t3 = st.tabs(["🤖 AI 분석", "📰 뉴스", "📊 재무/주주"])
            with st_t1:
                if chart_type == "일봉 (Daily)":
                    score, grade, reasons = analyze_stock(df)
                    c = "#FF4B4B" if score>=70 else "#FFA500" if score>=50 else "#1d5cff"
                    c1, c2 = st.columns([1,2])
                    with c1: st.markdown(f"<div style='text-align:center; padding:15px; border:2px solid {c}; border-radius:10px;'><h1 style='color:{c}; margin:0;'>{score}점</h1><h3>{grade}</h3></div>", unsafe_allow_html=True)
                    with c2: 
                        for r in reasons: st.write(r)
                else: st.info("일봉 차트에서만 AI 분석이 가능합니다.")
            
            # [수정된 부분] 안전하게 뉴스 표시
            with st_t2:
                news_list = fetch_stock_news(ticker)
                if news_list:
                    for n in news_list[:5]: 
                        title, link = get_safe_news_data(n) # 안전 함수 사용
                        if title and link: st.markdown(f"- [{title}]({link})")
                else: st.info("뉴스 없음")
            
            with st_t3:
                yahoo_url = f"https://finance.yahoo.com/quote/{ticker}"
                st.markdown(f"[👉 야후 파이낸스 더보기]({yahoo_url})")
                try:
                    c1, c2 = st.columns(2)
                    c1.metric("시가총액", f"${info.get('marketCap',0):,.0f}")
                    c2.metric("PER", f"{info.get('trailingPE',0):.2f}")
                except: pass
        else: st.error("종목 정보를 불러올 수 없습니다.")

# TAB 2: AI 추천
with tab2:
    st.header("🏆 AI 유망 종목 발굴")
    if st.button("🚀 분석 시작"):
        if not target_tickers: st.error("종목 없음")
        else:
            res = []; bar = st.progress(0)
            for i, t in enumerate(target_tickers):
                d = fetch_stock_history(t, "3mo", "1d")
                if len(d)>0:
                    sc, gr, re = analyze_stock(d)
                    res.append({"종목": t, "점수": sc, "등급": gr, "이유": ", ".join(re[:2])})
                bar.progress((i+1)/len(target_tickers))
            bar.empty()
            if res:
                df = pd.DataFrame(res).sort_values("점수", ascending=False)
                st.dataframe(df, use_container_width=True)

# TAB 3: 포트폴리오
with tab3:
    st.header("💰 내 포트폴리오 (영구 저장)")
    col_save, col_load = st.columns(2)
    with col_save:
        if st.session_state.portfolio:
            csv = pd.DataFrame(st.session_state.portfolio).to_csv(index=False).encode('utf-8')
            st.download_button("💾 내 컴퓨터에 백업", csv, f"portfolio_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
    with col_load:
        uploaded_file = st.file_uploader("📂 불러오기", type="csv")
        if uploaded_file is not None:
            try:
                df_load = pd.read_csv(uploaded_file)
                st.session_state.portfolio = df_load.to_dict('records')
                save_portfolio_to_csv(st.session_state.portfolio)
                st.success("완료!"); st.rerun()
            except: st.error("파일 오류")

    st.markdown("---")
    if not st.session_state.portfolio: st.info("종목 없음")
    else:
        pf_df = pd.DataFrame(st.session_state.portfolio)
        edited = st.data_editor(pf_df, num_rows="dynamic", key="pf_edit", use_container_width=True)
        if not edited.equals(pf_df):
            st.session_state.portfolio = edited.to_dict('records')
            save_portfolio_to_csv(st.session_state.portfolio)
            st.rerun()
        
        total_buy=0; total_eval=0
        for p in st.session_state.portfolio:
            try:
                cur = yf.Ticker(p['ticker']).fast_info.last_price
                total_buy += float(p['buy_price']) * int(p['qty'])
                total_eval += cur * int(p['qty'])
            except: pass
            
        profit = total_eval - total_buy
        pct = (profit/total_buy)*100 if total_buy>0 else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("총 매수", f"${total_buy:,.2f}")
        c2.metric("총 평가", f"${total_eval:,.2f}")
        c3.metric("수익", f"${profit:,.2f}", f"{pct:+.2f}%")
