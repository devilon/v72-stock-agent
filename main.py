from flask import Flask
import stock_agent
import os
app = Flask(__name__)

@app.route("/run")
def run_task():
    stock_agent.run_stock_task()
    return "✅ V72选股任务执行完毕，请查看飞书消息", 200

@app.route("/")
def index():
    return "V72 Stock Agent Ready，访问 /run 执行选股", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
