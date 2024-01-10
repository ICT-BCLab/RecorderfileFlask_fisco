import pandas as pd
from flask import Flask, render_template

from pyecharts import options as opts
from pyecharts.charts import Bar,Line,Grid,Pie
from pyecharts.commons.utils import JsCode
from markupsafe import Markup
from bs4 import BeautifulSoup

app = Flask(__name__, template_folder='templates', static_folder='resource',static_url_path="/")

filepath="/Users/bethestar/Downloads/myFiscoBcos/fisco/nodes/127.0.0.1/node0/log_record/"

def parse_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    chart_id = soup.find("div", {"class": "chart-container"}).get("id")
    chart_js = soup.find_all("script")[1]
    chart = "<div class=\"panel-draw d-flex flex-column justify-content-center align-items-center\" id=\"" + chart_id + "\"></div>"
    return chart, chart_js

def shorten_id(node_id):
    return "0x"+node_id[:8]+"..."

@app.route('/')
def bigBoard():
    return render_template("base.html")

# --网络层--
# 节点收发消息总量
@app.route("/PeerMessageThroughput")
def get_peer_message_throughput():
    filename = "peer_message_throughput.csv"
    # 读取csv文件
    df = pd.read_csv(filepath + filename)

    # 按照action_type拆分数据
    received_df = df.loc[df['action_type'] == 'Received']
    sent_df = df.loc[df['action_type'] == 'Sent']

    # 按照action_type和message_type拆分数据
    received_p2p = received_df.loc[received_df['message_type'] == 'P2P']
    received_channel = received_df.loc[received_df['message_type'] == 'Channel']
    sent_p2p = sent_df.loc[sent_df['message_type'] == 'P2P']
    sent_channel = sent_df.loc[sent_df['message_type'] == 'Channel']

    line1 = (
        Line()
        .add_xaxis(received_df['measure_time'].tolist())
        .add_yaxis(series_name="P2P消息", y_axis=received_p2p["message_size"].tolist(),is_smooth=True)
        .add_yaxis(series_name="Channel消息", y_axis=received_channel["message_size"].tolist(),is_smooth=True)
        .set_global_opts(title_opts=opts.TitleOpts(title="节点收发消息总量-接收"),
                         toolbox_opts=opts.ToolboxOpts(),
                         visualmap_opts=opts.VisualMapOpts(),
                         datazoom_opts=[
                             opts.DataZoomOpts(range_start=0, range_end=100),
                         ],
                         xaxis_opts=opts.AxisOpts(name="测量时刻"),
                         yaxis_opts=opts.AxisOpts(name="消息大小"),
                         legend_opts=opts.LegendOpts(pos_left="center"),
                         )
    )

    line2 = (
        Line()
        .add_xaxis(sent_df['measure_time'].tolist())
        .add_yaxis(series_name="P2P消息", y_axis=sent_p2p["message_size"].tolist(), is_smooth=True)
        .add_yaxis(series_name="Channel消息", y_axis=sent_channel["message_size"].tolist(), is_smooth=True)
        .set_global_opts(title_opts=opts.TitleOpts(title="节点收发消息总量-发送",pos_top="50%"),
                         toolbox_opts=opts.ToolboxOpts(),
                         datazoom_opts=[
                             opts.DataZoomOpts(range_start=0, range_end=100),
                         ],
                         xaxis_opts=opts.AxisOpts(name="测量时刻"),
                         yaxis_opts=opts.AxisOpts(name="消息大小"),
                         legend_opts=opts.LegendOpts(pos_left="center",pos_top="50%"),
                         )
    )

    grid = (
        Grid()
        .add(chart=line1,grid_opts=opts.GridOpts(pos_bottom="60%"))
        .add(chart=line2, grid_opts=opts.GridOpts(pos_top="60%"))
    )

    chart,chart_js = parse_html(grid.render_embed())
    return render_template('draw.html', chart = chart, chart_js = chart_js)

# P2P网络平均传输时延
@app.route("/NetP2PTransmissionLatency")
def get_net_p2p_transmission_latency():
    filename = "net_p2p_transmission_latency.csv"
    # 读取csv文件
    df = pd.read_csv(filepath + filename)

    # 取出send_id列的唯一值，后续作为标题
    send_id = df['send_id'].unique()[0]

    # 取出receive_id、duration两列
    df = df[['receive_id', 'duration']]

    # 去掉duration列末尾的's'
    df['duration'] = df['duration'].str.rstrip('s')

    # 将duration列转换为浮点数
    df['duration'] = df['duration'].astype(float)

    # recorderfile中在此处设置了3秒超时重传，所以要减去超时重传带来的误差（可能不止重传了1次）
    df['duration'] = df['duration'] - 3 * (df['duration'] // 3)

    # 按receive_id分组，并计算duration的平均值
    receive_id_avg = df.groupby('receive_id')['duration'].mean()

    receive_id_list = receive_id_avg.index.tolist()
    duration_list = receive_id_avg.values.tolist()
    shortened_receive_id_list = [shorten_id(node_id) for node_id in receive_id_list]

    bar = (
        Bar()
        .add_xaxis(shortened_receive_id_list)
        .add_yaxis(series_name="平均传输时间", y_axis=duration_list)
        .set_global_opts(title_opts=opts.TitleOpts(title="从"+shorten_id(send_id)+"发出消息计算结果"),
                         toolbox_opts=opts.ToolboxOpts(),
                         visualmap_opts=opts.VisualMapOpts(),
                         datazoom_opts=[
                             opts.DataZoomOpts(range_start=0, range_end=100),
                         ],
                         xaxis_opts=opts.AxisOpts(name="接收消息节点ID"),
                         yaxis_opts=opts.AxisOpts(name="平均传输时间/s"),
                         legend_opts=opts.LegendOpts(pos_left="center"),
                         )

    )

    chart, chart_js = parse_html(bar.render_embed())
    return render_template('draw.html', chart=chart, chart_js=chart_js)

# --数据层--
# 数据库写入速率
@app.route("/DBStateWriteRate")
def get_db_state_write_rate():
    filename = "db_state_write_rate.csv"
    # 读取csv文件
    df = pd.read_csv(filepath + filename)

    # 使用loc选择特定列
    new_df = df.loc[:, ['block_height', 'block_hash', 'write_duration']]
    # 去掉'write_duration'列中的's'
    new_df.loc[:, 'write_duration'] = new_df.loc[:, 'write_duration'].str.replace('s', '')
    # 在'block_hash'列前添加'0x'
    new_df.loc[:, 'block_hash'] = new_df.loc[:, 'block_hash'].apply(lambda x: '0x' + str(x))
    # 重命名'write_duration'列为'value'
    new_df.rename(columns={'write_duration': 'value'}, inplace=True)
    # 将新的DataFrame转换为字典列表
    data = new_df.to_dict('records')

    bar = (
        Bar()
        .add_xaxis(new_df['block_height'].tolist())
        .add_yaxis(series_name="写入耗时", y_axis=data)
        .set_global_opts(title_opts=opts.TitleOpts(title="数据库写入速率"),
                         toolbox_opts=opts.ToolboxOpts(),
                         visualmap_opts=opts.VisualMapOpts(),
                         datazoom_opts=[
                             opts.DataZoomOpts(range_start=40, range_end=60),
                         ],
                         xaxis_opts=opts.AxisOpts(name="区块高度"),
                         yaxis_opts=opts.AxisOpts(name="写入耗时/s"),
                         legend_opts=opts.LegendOpts(pos_left="center"),
                         tooltip_opts=opts.TooltipOpts(
                             formatter=JsCode(
                                 """
                                 function (params) {
                                     console.log(params);
                                     return '区块哈希:'+ params.data.block_hash ;
                                 }
                                 """
                             )
                         ),
                         )
    )



    chart,chart_js = parse_html(bar.render_embed())
    return render_template('draw.html', chart = chart, chart_js = chart_js)

# 数据库读取速率

# --共识层--


# --合约层--
# 合约执行时间
@app.route("/ContractTime")
def get_contract_time():
    filename = "contract_time.csv"
    # 读取csv文件
    df = pd.read_csv(filepath + filename)

    # 使用loc选择特定列
    new_df = df.loc[:, ['tx_hash', 'contract_address', 'exec_time']]
    # 去掉'exec_time'列中的's'
    new_df.loc[:, 'exec_time'] = new_df.loc[:, 'exec_time'].str.replace('s', '')
    # 在'contract_address'和'tx_hash'列前添加'0x'
    new_df.loc[:, 'contract_address'] = new_df.loc[:, 'contract_address'].apply(lambda x: '0x' + str(x))
    new_df.loc[:, 'tx_hash'] = new_df.loc[:, 'tx_hash'].apply(lambda x: '0x' + str(x))
    # 重命名'exec_time'列为'value'
    new_df.rename(columns={'exec_time': 'value'}, inplace=True)
    # 将新的DataFrame转换为字典列表
    data = new_df.to_dict('records')
    bar = (
        Bar()
        .add_xaxis(df["start_time"].tolist())
        .add_yaxis(series_name="执行时间", y_axis=data)
        .set_global_opts(title_opts=opts.TitleOpts(title="合约执行时间"),
                         toolbox_opts=opts.ToolboxOpts(),
                         visualmap_opts=opts.VisualMapOpts(),
                         datazoom_opts=[
                             opts.DataZoomOpts(range_start=45, range_end=55),
                         ],
                         xaxis_opts=opts.AxisOpts(name="开始执行时刻"),
                         yaxis_opts=opts.AxisOpts(name="执行时间/s"),
                         legend_opts=opts.LegendOpts(pos_left="center"),
                         tooltip_opts=opts.TooltipOpts(
                             formatter=JsCode(
                                 """
                                 function (params) {
                                     console.log(params);
                                     return '合约地址:'+ params.data.contract_address + '</br>' +
                                             '交易哈希:'+ params.data.tx_hash;
                                 }
                                 """
                             )
                         ),
                         )

    )
    type_counts = df["type"].value_counts()
    pie = (
        Pie()
        .add(
            series_name="合约类型",
            data_pair=[list(i) for i in type_counts.items()],  # 将Series转换为列表
            center=["75%", "35%"],
            radius="28%",
        )
        .set_series_opts(
            tooltip_opts=opts.TooltipOpts(
                trigger="item", formatter="{a} <br/>{b}: {c} ({d}%)"
            ),
        )
    )
    chart, chart_js = parse_html(bar.overlap(pie).render_embed())
    return render_template('draw.html', chart=chart, chart_js=chart_js)


# --交易生命周期--





if __name__ == "__main__":
    app.run(debug=True)