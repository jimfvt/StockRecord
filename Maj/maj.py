#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import csv
import re
import json
from datetime import datetime
from urllib.request import Request, urlopen

def get_quanta_ultimate_perfect_data():
    print("正在啟動廣達 (2382) 【證交所盤價 + Yahoo籌碼】終極整合程序...")
    ticker_num = "2382"
    ticker_tw = "2382.TW"

    # 獲取目前系統時間與預設西元日期
    current_date_str = datetime.now().strftime('%Y%m%d')
    trade_date = datetime.now().strftime('%Y-%m-%d')

    # 建立更高防禦規格的瀏覽器偽裝 Header，防止被證交所阻擋
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.twse.com.tw/zh/trading/historical/stock-day.html'
    }

    open_p = high_p = low_p = close_p = "0.0"

    # ==========================================
    # 項目一：從台灣證交所 (TWSE) 穩定接口抓取四大盤價
    # ==========================================
    print(" 📡 [步驟 1/3] 正在從證交所官方開放接口獲取最新四大盤價...")

    # 更換為最不容易被擋的證交所歷史日收盤行情網址
    twse_url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date={current_date_str}&stockNo={ticker_num}"
    req_twse = Request(twse_url, headers=headers)

    try:
        with urlopen(req_twse, timeout=15) as response:
            response_content = response.read().decode('utf-8')
            twse_json = json.loads(response_content)

        if twse_json.get('stat') == 'OK' and 'data' in twse_json and twse_json['data']:
            # data 陣列內最後一筆資料即為最新一個交易日的行情
            last_trade_day = twse_json['data'][-1]

            # 欄位定義：0=日期, 3=開盤價, 4=最高價, 5=最低價, 6=收盤價
            raw_date = last_trade_day[0]  # 格式如 "115/05/27"
            open_p = last_trade_day[3].replace(',', '').strip()
            high_p = last_trade_day[4].replace(',', '').strip()
            low_p = last_trade_day[5].replace(',', '').strip()
            close_p = last_trade_day[6].replace(',', '').strip()

            # 將民國年轉換成西元年 (例如 115/05/27 -> 2026-05-27)
            try:
                year_part, month_part, day_part = raw_date.split('/')
                ad_year = str(int(year_part) + 1911)
                trade_date = f"{ad_year}-{month_part}-{day_part}"
            except:
                pass

            print(f" ✅ 證交所盤價讀取成功！交易日期: {trade_date} | 開盤: {open_p} | 收盤: {close_p}")
        else:
            print(" ⚠️ 提示：證交所今日回傳格式不符或尚未收盤，採用預設市價格式。")

    except Exception as e:
        print(f" ⚠️ 警告：連線證交所 API 失敗 ({e})，採用今日系統日期與預設 0.0 數據繼續執行。")

    # ==========================================
    # 項目二：延續 Yahoo 網頁 HTML 區塊切割法抓取籌碼
    # ==========================================
    print(" 📡 [步驟 2/3] 正在獲取 Yahoo 股市主力籌碼分點明細...")
    yahoo_url = f"https://tw.stock.yahoo.com/quote/{ticker_tw}/broker-trading"
    req_yahoo = Request(yahoo_url, headers=headers)

    try:
        with urlopen(req_yahoo, timeout=15) as response:
            html_content = response.read().decode('utf-8')
    except Exception as e:
        print(f"❌ 錯誤：Yahoo 網頁請求失敗: {e}")
        return

    blocks = html_content.split('券商</span>')
    if len(blocks) < 3:
        print("💡 貼心提醒：今日盤後籌碼分點資料尚未釋出（通常於 15:30-16:00 更新）。")
        return

    buy_block = blocks[1]
    sell_block = blocks[2]

    all_records = []

    # 提取【買超券商】明細
    buy_items = re.findall(r' Ta\(s\)">([^<]+)</span>.*?C\(\$c-trend-up\)">([^<]+)</span>', buy_block)
    for item in buy_items:
        broker_name = item[0].strip()
        volume = item[1].replace(',', '').strip()

        if "買進" in broker_name or "賣出" in broker_name or not volume.isdigit():
            continue

        all_records.append({
            '日期': trade_date,
            '買超/賣超': '買超',
            '券商': broker_name,
            '張數': volume,
            '開盤價': open_p,
            '收盤價': close_p,
            '最高價': high_p,
            '最低價': low_p
        })

    # 提取【賣超券商】明細
    sell_items = re.findall(r' Ta\(s\)">([^<]+)</span>.*?C\(\$c-trend-down\)">([^<]+)</span>', sell_block)
    for item in sell_items:
        broker_name = item[0].strip()
        volume = item[1].replace(',', '').replace('-', '').strip()

        if "買進" in broker_name or "賣出" in broker_name or not volume.isdigit():
            continue

        all_records.append({
            '日期': trade_date,
            '買超/賣超': '賣超',
            '券商': broker_name,
            '張數': volume,
            '開盤價': open_p,
            '收盤價': close_p,
            '最高價': high_p,
            '最低價': low_p
        })

    # ==========================================
    # 項目三：將完美資料寫入 CSV
    # ==========================================
    print(" 💾 [步驟 3/3] 正在將整合資料追加至歷史 CSV 紀錄檔案...")
    if not all_records:
        print("❌ 錯誤：未能提取到任何有效的券商主力數據。")
        return

    csv_file = "quanta_2382_trading_log.csv"
    file_exists = os.path.isfile(csv_file)
    fieldnames = ['日期', '買超/賣超', '券商', '張數', '開盤價', '收盤價', '最高價', '最低價']

    try:
        with open(csv_file, mode='a', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerows(all_records)
        print(f"🎉 [終極大功告成] 已成功整合證交所數據！CSV 檔案更新完成，本次共新增 {len(all_records)} 筆主力紀錄。")
    except Exception as e:
        print(f"❌ 寫入 CSV 檔案時發生錯誤: {e}")

if __name__ == "__main__":
    get_quanta_ultimate_perfect_data()
