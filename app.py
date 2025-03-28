
from flask import Flask, render_template_string, request
import pandas as pd
import re
import matplotlib.pyplot as plt
import base64
from io import TextIOWrapper, BytesIO
import os

app = Flask(__name__)

HTML_TEMPLATE = """...（省略：與 canvas 相同 HTML 模板）"""

@app.route('/', methods=['GET', 'POST'])
def index():
    table_html = ""
    plot_url = None
    error = None

    if request.method == 'POST':
        try:
            file = request.files['asc_file']
            clamps = int(request.form['clamps'])
            screw_size = int(request.form['screw_size'])
            default_torque = float(request.form['default_torque'])

            if file:
                content = TextIOWrapper(file.stream, encoding='latin1').readlines()
                position_line = next((line for line in content if len(re.findall(r"\d+", line)) > 10), None)
                offset_line = next((line for line in content if re.match(r"^0 +0 +\d+", line)), None)

                if not position_line:
                    raise ValueError("找不到位置資料（數字行）")
                if not offset_line:
                    raise ValueError("找不到偏移量資料（以 0 開頭的數字行）")

                positions = list(map(int, re.findall(r"\d+", position_line)))
                offsets = list(map(int, re.findall(r"-?\d+", offset_line)))
                if len(positions) > len(offsets):
                    positions = positions[:len(offsets)]

                df = pd.DataFrame({"位置 (mm)": positions, "偏移量": offsets})
                df["平均偏移"] = df["偏移量"]
                max_offset = df["平均偏移"].abs().max()
                df["建議調整磅數"] = df["平均偏移"] / max_offset * 10
                df["建議新磅數"] = (default_torque - df["建議調整磅數"]).apply(lambda x: max(0, round(x, 2)))
                df["調整建議"] = df["建議調整磅數"].apply(
                    lambda x: f"減少 {abs(round(x,1))} 磅" if x > 0 else f"增加 {abs(round(x,1))} 磅" if x < 0 else "不需調整")
                df["預測修正後偏移"] = df["平均偏移"] * 0.1

                fig, ax = plt.subplots(figsize=(8, 4))
                ax.plot(df["位置 (mm)"], df["偏移量"], label='原始偏移', marker='o')
                ax.plot(df["位置 (mm)"], df["預測修正後偏移"], label='預測修正後偏移', marker='x')
                ax.plot(df["位置 (mm)"], df["建議新磅數"], label='建議新磅數', marker='s')
                ax.set_xlabel("位置 (mm)")
                ax.set_ylabel("偏移 / 磅數")
                ax.set_title("偏移分析圖")
                ax.grid(True)
                ax.legend()

                buf = BytesIO()
                plt.tight_layout()
                fig.savefig(buf, format="png")
                buf.seek(0)
                plot_url = base64.b64encode(buf.read()).decode('utf-8')
                buf.close()

                table_html = df.to_html(index=False)
        except Exception as e:
            error = str(e)

    return render_template_string(HTML_TEMPLATE, table=table_html, plot_url=plot_url, error=error)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
