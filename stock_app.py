import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="미국 주식 분석기 Pro")

# --- [기능] 검색 기록 세션 관리 ---
if 'search_history' not in st.session_state:
    st.session_state.search_history = []

def set_ticker(t):
    st.session_state.ticker_input = t

# ==========================================
# [사이드바] 메뉴 구성
# ==========================================
st.sidebar.title("🔍 검색 옵션")

# 1. 종목 코드 검색
ticker = st.sidebar.text_input("종목 코드 (예: AAPL, TSLA)", "AAPL", key="ticker_input")

# 2. 차트 선택
st.sidebar.markdown("---")
chart_type = st.sidebar.selectbox(
    "차트 선택",
    ["일봉 (Daily)", "주봉 (Weekly)", "월봉 (Monthly)", "분봉 (Intraday)"]
)

# 3. 최근 검색 기록
if st.session_state.search_history:
    st.sidebar.markdown("---")
    st.sidebar.subheader(f"🕒 최근 검색 ({len(st.session_state.search_history)}/20)")
    
    for past_ticker in st.session_state.search_history:
        if st.sidebar.button(f"📌 {past_ticker}", key=f"history_{past_ticker}", use_container_width=True):
            set_ticker(past_ticker)
            st.rerun()

    if st.sidebar.button("🗑️ 기록 전체 삭제"):
        st.session_state.search_history = []
        st.rerun()

# ==========================================
# [메인] 타이틀 및 분석 로직
# ==========================================
st.title(f"🚀 {ticker} 주식 대시보드")

if ticker:
    ticker = ticker.upper().strip()
    
    if ticker in st.session_state.search_history:
        st.session_state.search_history.remove(ticker)
    st.session_state.search_history.insert(0, ticker)
    if len(st.session_state.search_history) > 20:
        st.session_state.search_history.pop()

    try:
        stock = yf.Ticker(ticker)
        
        # [1] 호가 정보
        info = stock.info
        current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
        previous_close = info.get('previousClose', 0)
        
        bid = info.get('bid', 0)
        ask = info.get('ask', 0)
        bid_size = info.get('bidSize', 0)
        ask_size = info.get('askSize', 0)
        
        change_value = current_price - previous_close
        change_rate = (change_value / previous_close) * 100 if previous_close else 0
        color = "red" if change_value > 0 else "blue" if change_value < 0 else "gray"

        st.markdown(f"""
        <div style="padding: 15px; border-radius: 10px; background-color: #262730; margin-bottom: 20px;">
            <h2 style="margin:0; color:white;">
                현재가: ${current_price:,.2f} 
                <span style="color:{color}; font-size:0.8em;">
                    ({change_value:+.2f}, {change_rate:+.2f}%)
                </span>
            </h2>
            <div style="display: flex; gap: 20px; margin-top: 10px; font-size: 1.1em;">
                <span style="color:#ff4b4b;"><b>매도(Ask):</b> ${ask:,.2f} ({ask_size})</span>
                <span style="color:#1d5cff;"><b>매수(Bid):</b> ${bid:,.2f} ({bid_size})</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # [2] 차트 데이터 다운로드
        download_period = "max"
        interval = "1d"
        end_date = datetime.now()
        start_date = end_date 
        
        if chart_type == "일봉 (Daily)":
            interval = "1d"; download_period = "2y"; start_date = end_date - timedelta(days=100)
        elif chart_type == "주봉 (Weekly)":
            interval = "1wk"; download_period = "5y"; start_date = end_date - timedelta(days=365)
        elif chart_type == "월봉 (Monthly)":
            interval = "1mo"; download_period = "max"; start_date = end_date - timedelta(days=365*3)
        elif chart_type == "분봉 (Intraday)":
            minute_option = st.sidebar.selectbox("시간 단위", ["1분", "15분", "30분", "60분", "90분"])
            mapping = {"1분":"1m", "15분":"15m", "30분":"30m", "60분":"60m", "90분":"90m"}
            interval = mapping[minute_option]
            download_period = "5d"
            start_date = end_date - timedelta(days=1)

        df = stock.history(period=download_period, interval=interval)
        
        if len(df) == 0:
            st.error("❌ 차트 데이터를 가져올 수 없습니다.")
        else:
            if chart_type != "분봉 (Intraday)":
                df['MA5'] = df['Close'].rolling(window=5).mean()
                df['MA20'] = df['Close'].rolling(window=20).mean()
                df['MA60'] = df['Close'].rolling(window=60).mean()
                df['MA120'] = df['Close'].rolling(window=120).mean()

            # 차트 생성 (2단)
            fig = make_subplots(
                rows=2, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.03, 
                row_heights=[0.7, 0.3], 
                specs=[[{"secondary_y": False}], [{"secondary_y": False}]]
            )
            
            # 캔들
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], increasing_line_color='#ef3636', decreasing_line_color='#1d5cff', name="캔들"), row=1, col=1)

            # 이평선
            if chart_type != "분봉 (Intraday)":
                for ma, color in zip(['MA5', 'MA20', 'MA60', 'MA120'], ['magenta', 'red', 'blue', 'green']):
                    fig.add_trace(go.Scatter(x=df.index, y=df[ma], line=dict(color=color, width=1), name=ma), row=1, col=1)

            # 거래량
            volume_colors = ['#ef3636' if row['Close'] >= row['Open'] else '#1d5cff' for _, row in df.iterrows()]
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=volume_colors, name="거래량"), row=2, col=1)

            # --- [수정됨] 차트 라벨 표시 로직 ---
            # 좌표 기준을 'paper'(전체)가 아닌 'x domain'(차트 내부)으로 변경하여 확실하게 표시
            label_text = f"<b>{chart_type}</b>" 
            if chart_type == "분봉 (Intraday)":
                label_text = f"<b>{minute_option}봉</b>"

            fig.add_annotation(
                text=label_text,
                xref="x domain", yref="y domain", # 좌표 기준: 첫번째 차트의 X, Y축 기준
                x=0.01, y=0.99,                   # 위치: 왼쪽(0.01) 상단(0.99)
                showarrow=False,
                font=dict(size=20, color="#FFD700"), # 노란색 큰 글씨
                bgcolor="rgba(0,0,0,0.5)",        # 반투명 배경
                borderpad=5,
                row=1, col=1                      # 반드시 첫 번째 차트(캔들)에만 표시
            )

            # 레이아웃 설정
            fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            fig.update_yaxes(side="right")
            
            if chart_type != "분봉 (Intraday)":
                fig.update_xaxes(range=[start_date, end_date], row=1, col=1)
                fig.update_xaxes(range=[start_date, end_date], row=2, col=1)

            st.plotly_chart(fig, use_container_width=True)

        # [3] 하단 탭
        st.markdown("---")
        tab1, tab2, tab3 = st.tabs(["📰 실시간 뉴스", "📊 상세 재무", "👥 주주 정보"])

        # 탭 1: 뉴스
        with tab1:
            st.subheader(f"📰 {ticker} 최신 뉴스")
            try:
                news_list = stock.news
                if news_list:
                    count = 0
                    for news in news_list:
                        content = news.get('content', {})
                        title = news.get('title') or content.get('title', '제목 없음')
                        link = news.get('link') or content.get('clickThroughUrl', {}).get('url') or content.get('canonicalUrl', {}).get('url')
                        publisher = news.get('publisher') or content.get('provider', {}).get('displayName', 'Yahoo Finance')

                        if title != '제목 없음' and link:
                            st.markdown(f"""<div style="padding:10px; border:1px solid #444; border-radius:5px; margin-bottom:8px; background-color:#222;"><div style="color:#aaa; font-size:12px;">{publisher}</div><a href="{link}" target="_blank" style="font-size:16px; color:#4da6ff; text-decoration:none;">{title}</a></div>""", unsafe_allow_html=True)
                            count += 1
                    if count == 0: st.info("표시할 뉴스가 없습니다.")
                else: st.info("뉴스가 없습니다.")
            except: st.warning("뉴스 로딩 실패")

        # 탭 2: 상세 재무
        with tab2:
            try:
                yahoo_fin_url = f"https://finance.yahoo.com/quote/{ticker}/financials"
                st.markdown(f"""<a href="{yahoo_fin_url}" target="_blank" style="display:inline-block; padding:10px 20px; background-color:#1d5cff; color:white; text-decoration:none; border-radius:5px; margin-bottom:20px;">👉 야후 파이낸스 [상세 재무표] 보러가기</a>""", unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns(3)
                col1.metric("시가총액", f"${info.get('marketCap', 0):,.0f}")
                col2.metric("PER (주가수익비율)", f"{info.get('trailingPE', 0):.2f}")
                col3.metric("PBR (주가순자산비율)", f"{info.get('priceToBook', 0):.2f}")
                st.write("---")
                col4, col5, col6 = st.columns(3)
                col4.metric("52주 최고가", f"${info.get('fiftyTwoWeekHigh', 0):,.2f}")
                col5.metric("52주 최저가", f"${info.get('fiftyTwoWeekLow', 0):,.2f}")
                col6.metric("배당 수익률", f"{info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "없음")
            except: st.warning("재무 정보 없음")

        # 탭 3: 주주 정보
        with tab3:
            yahoo_holder_url = f"https://finance.yahoo.com/quote/{ticker}/holders"
            st.markdown(f"""<a href="{yahoo_holder_url}" target="_blank" style="display:inline-block; padding:10px 20px; background-color:#1d5cff; color:white; text-decoration:none; border-radius:5px; margin-bottom:20px;">👉 야후 파이낸스 [상세 주주 정보] 보러가기</a>""", unsafe_allow_html=True)

            st.subheader("👥 주주 구성")
            try:
                major = stock.major_holders
                if major is not None and not major.empty:
                    st.write("📌 주요 주주 비중")
                    st.dataframe(major, use_container_width=True) 
                else: st.write("주요 주주 데이터가 없습니다.")

                inst = stock.institutional_holders
                if inst is not None and not inst.empty:
                    st.write("🏢 기관 투자자 보유 현황")
                    st.dataframe(inst, use_container_width=True)
                else: st.info("상세 기관 리스트 정보가 없습니다.")     
            except Exception as e: st.warning(f"주주 정보 오류: {e}")

    except Exception as e:
        st.error(f"오류 발생: {e}")