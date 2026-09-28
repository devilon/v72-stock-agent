import os
from datetime import datetime
import baostock as bs
import yfinance as yf
import pandas as pd
import requests
from dotenv import load_dotenv

try:
    from lark_oapi import Client, ACCESS_TOKEN_TYPE_TENANT
    LARK_SDK_AVAILABLE = True
except ImportError:
    LARK_SDK_AVAILABLE = False

load_dotenv()
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
FOLDER_TOKEN = os.getenv("FEISHU_DRIVE_FOLDER_TOKEN")
HTTP_TIMEOUT = 20
_http = requests.Session()

# 待处理标的
stock_list = [
    {"name": "长江电力", "code": "600900.SH"},
    {"name": "招商银行", "code": "600036.SH"},
    {"name": "美高梅中国", "code": "2282.HK"},
    {"name": "埃克森美孚", "code": "XOM"},
]

def send_feishu_text(content: str):
    if not FEISHU_WEBHOOK:
        print("⚠️ 未配置FEISHU_WEBHOOK")
        return
    payload = {"msg_type": "text", "content": {"text": content}}
    try:
        r = _http.post(FEISHU_WEBHOOK, json=payload, timeout=HTTP_TIMEOUT)
        print(f"飞书推送返回：{r.json()}")
    except Exception as e:
        print(f"飞书推送异常：{str(e)}")

def upload_csv_to_feishu_drive(file_path: str, file_name: str):
    if not LARK_SDK_AVAILABLE or not APP_ID or not APP_SECRET or not FOLDER_TOKEN:
        print("ℹ️ 缺少飞书云盘配置，跳过文件上传")
        return None
    client = Client.builder(APP_ID, APP_SECRET).tenant_access_token(True).build()
    with open(file_path, "rb") as f:
        resp = client.drive.v1.file.create(
            request_body={"name": file_name, "folder_token": FOLDER_TOKEN},
            files={"file": f}
        )
    if not resp.success():
        print(f"飞书云盘上传失败：{resp.code}, {resp.msg}")
        return None
    file_token = resp.data.get("file_token")
    preview_url = f"https://my.feishu.cn/drive/f/{file_token}/"
    return preview_url

def fetch_stock_data(name, code):
    df_row = {"标的": name, "代码": code}
    try:
        if code.endswith(".SH") or code.endswith(".SZ"):
            bs.login()
            rs = bs.query_history_k_data_plus(code,
                "date,close,volume",
                start_date='2025-01-01', end_date=datetime.now().strftime("%Y-%m-%d"),
                frequency="d", adjust="qfq")
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            bs.logout()
            if len(data_list) > 0:
                latest = data_list[-1]
                df_row["最新日期"] = latest[0]
                df_row["收盘价"] = latest[1]
                df_row["成交量"] = latest[2]
        else:
            ticker = yf.Ticker(code)
            hist = ticker.history(period="5d")
            if not hist.empty:
                latest = hist.iloc[-1]
                df_row["最新日期"] = str(latest.name.date())
                df_row["收盘价"] = round(latest.Close, 2)
                df_row["成交量"] = int(latest.Volume)
        return df_row
    except Exception as e:
        print(f"{name}({code}) 处理失败：{str(e)}")
        return None

def run_stock_task():
    print("===== V7.2增强版选股AI Agent启动【双数据源】 =====")
    result_rows = []
    for item in stock_list:
        name = item["name"]
        code = item["code"]
        print(f"==== 正在处理：{name} | {code} ====")
        row = fetch_stock_data(name, code)
        if row:
            result_rows.append(row)
    csv_filename = "v72_daily_result.csv"
    df = pd.DataFrame(result_rows)
    df.to_csv(csv_filename, index=False, encoding="utf-8-sig")
    print("✅ CSV文件生成完成")

    preview_link = upload_csv_to_feishu_drive(csv_filename, f"V72选股结果_{datetime.now().strftime('%Y%m%d')}.csv")
    if preview_link:
        msg = (f"【V7.2选股完成】\n"
               f"标的总数：{len(stock_list)}，成功拉取：{len(result_rows)}个\n"
               f"📊 在线表格：{preview_link}")
    else:
        msg = (f"【V7.2选股完成】\n"
               f"标的总数：{len(stock_list)}，成功拉取：{len(result_rows)}个\n"
               f"⚠️ CSV未上传飞书云盘")
    send_feishu_text(msg)
    print("==== 本次选股任务全部结束 ====")

if __name__ == '__main__':
    week_day = datetime.now().weekday()
    if week_day >= 5:
        print("📅 周末，跳过选股")
        send_feishu_text("【V7.2通知】今日周末，不执行选股任务")
    else:
        run_stock_task()
