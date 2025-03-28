from flask import Flask, render_template_string, request
import pandas as pd
import re
import matplotlib.pyplot as plt
import base64
from io import TextIOWrapper, BytesIO

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>線軌打準直分析工具</title>
</head>
<body>
    <h1>線軌打準直分析工具</h1>
    <form method="POST" enctype="multipart/form-data">
        <p>請上傳 ASC 檔案: <input type="file" name="asc_file"></p>
        <p>迫緊塊數量: <input type="number" name="clamps" value="10"></p>
        <p>螺絲大小 (mm): <input type="number" name="screw_size" value="6"></p>
        <p>螺絲預設磅數: <input type="number" name="default_torque" value="5"></p>
        <p><input type="submit" value="分析"></p>
    </form>
    {% if plot_url %}
        <h2>偏移視覺化圖表</h2>
        <img src="data:image/png;base64,{{ plot_url }}">
    {% endif %}
    {% if table %}
        <h2>分析結果</h2>
        {{ table | safe }}
    {% endif %}
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    table_html = ""
    plot_url = None

    if request.method == 'POST':
        file = request.files['asc_file']
        clamps = int(request.form['clamps'])
        screw_size = int(request.form['screw_size'])
        default_torque = float(request.form['default_torque'])

        if file:
            content = TextIOWrapper(file.stream, encoding='latin1').readlines()
            position_line = next((line for line in content if line.strip().startswith("0 ") and "," in line), None)
            offset_line = next((line for line in content if re.match(r"^0 +0 +\d+", line)), None)

            if position_line and offset_line:
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

    return render_template_string(HTML_TEMPLATE, table=table_html, plot_url=plot_url)

if __name__ == '__main__':
    app.run(debug=True)
