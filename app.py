import json

import pandas as pd
import requests
import yaml
from flask import Flask, render_template, request, jsonify

from pyecharts import options as opts
from pyecharts.charts import Bar, Line, Grid, Pie, Tab
from pyecharts.commons.utils import JsCode
from bs4 import BeautifulSoup
from datetime import datetime
from flask_cors import CORS

app = Flask(__name__, template_folder='templates', static_folder='resource', static_url_path="/")

CORS(app, supports_credentials=True)

filepath = "/Users/bethestar/Downloads/myFiscoBcos/fisco/nodes/127.0.0.1/node0/log_record"
config_server = "127.0.0.1:9530"
# 把pyecharts自动生成的完整html文件转化成能嵌入到展示小模块的代码
def parse_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    chart_id = soup.find("div", {"class": "chart-container"}).get("id")
    chart_js = soup.find_all("script")[1]
    chart = "<div class=\"panel-draw d-flex flex-column justify-content-center align-items-center\" id=\"" + chart_id + "\"></div>"
    return chart, chart_js

# 【针对有多个tab的情况】把pyecharts自动生成的完整html文件转化成能嵌入到展示小模块的代码
def parse_html_tab(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    chart = soup.body
    return chart, ""

# 截短过长的哈希值
def shorten_id(node_id):
    return "0x" + node_id[:8] + "..."

# 根据格式化好的时间计算duration（返回的时间不带's'结尾）
def calculate_duration(end_time, start_time):
    formatted_time = "%Y-%m-%d %H:%M:%S.%f"
    end_time = datetime.strptime(end_time, formatted_time)
    start_time = datetime.strptime(start_time, formatted_time)
    return (end_time - start_time).total_seconds()

# ---统计分段及占比--
def construct_bar_hist(df,num_bins,title_name):
    # str转float
    df = df.astype(float).round(6)
    df = df[df >= 0]
    # 对数据进行分段
    bin_edges = pd.cut(df, bins=num_bins, include_lowest=False)
    # 统计每个分段的数量
    value_counts = bin_edges.value_counts(sort=False)
    bar_hist = (
        Bar()
        .add_xaxis(value_counts.index.astype(str).tolist())
        .add_yaxis(series_name="频数", y_axis=value_counts.tolist())
        .set_global_opts(title_opts=opts.TitleOpts(title=title_name+"频数统计"),
                         toolbox_opts=opts.ToolboxOpts(),
                         datazoom_opts=[
                             opts.DataZoomOpts(range_start=0, range_end=100),
                         ],
                         xaxis_opts=opts.AxisOpts(name=title_name+"区间"),
                         yaxis_opts=opts.AxisOpts(name="频数"),
        )
    )
    return bar_hist

@app.route('/')
def bigBoard():
    return render_template("board.html")

# 修改记录文件夹路径
@app.route('/changeFilepath', methods = ["POST"])
def change_filepath():
    input_path = request.get_data()
    global filepath
    filepath =input_path.decode('utf-8')
    print("new_path",filepath)
    return "success"

# 更新开关状态
@app.route('/changeSwitch', methods = ["POST","GET","PUT"])
def change_switch():
    info = request.get_json()
    global config_server
    config_server = info["server"]
    url ='http://' +  config_server + '/config/accessconfig'
    data = info["new_yaml"]
    headers = {'Content-Type': 'application/x-yaml'}
    response = requests.put(url, data=data, headers=headers)

    if response.status_code == 200:
        return jsonify({'status': 'success', 'data': yaml.safe_load(response.text)})
    else:
        return jsonify({'status': 'error'})

# 获取最新的开关状态
@app.route('/updateSwitch', methods = ["POST","GET","PUT"])
def update_switch():
    url ='http://' +  config_server + '/config/accessconfig'
    response = requests.get(url)
    if response.status_code == 200:
        return jsonify({'status': 'success', 'data': yaml.safe_load(response.text)})
    else:
        return jsonify({'status': 'error'})


# --网络层--
# 节点收发消息总量
@app.route("/PeerMessageThroughput")
def get_peer_message_throughput():
    filename = "/peer_message_throughput.csv"
    # 读取csv文件
    df = pd.read_csv(filepath + filename)
    if len(df) <= 0:
        return render_template('draw.html', chart="<h2>当前文件尚无数据</h2>")

    # 获取message_size中的最大值最小值
    min_value = float(min(df["message_size"].tolist()))
    max_value = float(max(df["message_size"].tolist()))

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
        .add_yaxis(series_name="P2P消息", y_axis=received_p2p["message_size"].tolist(), is_smooth=True)
        .add_yaxis(series_name="Channel消息", y_axis=received_channel["message_size"].tolist(), is_smooth=True)
        .set_global_opts(title_opts=opts.TitleOpts(title="节点收发消息总量-接收"),
                         toolbox_opts=opts.ToolboxOpts(),
                         visualmap_opts=opts.VisualMapOpts(
                             min_ = min_value,
                             max_ = max_value
                         ),
                         datazoom_opts=[
                             opts.DataZoomOpts(range_start=45, range_end=55),
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
        .set_global_opts(title_opts=opts.TitleOpts(title="节点收发消息总量-发送", pos_top="50%"),
                         toolbox_opts=opts.ToolboxOpts(),
                         datazoom_opts=[
                             opts.DataZoomOpts(range_start=0, range_end=100),
                         ],
                         xaxis_opts=opts.AxisOpts(name="测量时刻"),
                         yaxis_opts=opts.AxisOpts(name="消息大小"),
                         legend_opts=opts.LegendOpts(pos_left="center", pos_top="50%"),
                         )
    )

    grid = (
        Grid()
        .add(chart=line1, grid_opts=opts.GridOpts(pos_bottom="60%"))
        .add(chart=line2, grid_opts=opts.GridOpts(pos_top="60%"))
    )

    chart, chart_js = parse_html(grid.render_embed())
    return render_template('draw.html', chart=chart, chart_js=chart_js)


# P2P网络平均传输时延
@app.route("/NetP2PTransmissionLatency")
def get_net_p2p_transmission_latency():
    filename = "/net_p2p_transmission_latency.csv"
    # 读取csv文件
    df = pd.read_csv(filepath + filename)
    if len(df) <= 0:
        return render_template('draw.html', chart="<h2>当前文件尚无数据</h2>")
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
    # 获取duration_list中的最大值最小值
    min_value = float(min(duration_list))
    max_value = float(max(duration_list))
    bar = (
        Bar()
        .add_xaxis(shortened_receive_id_list)
        .add_yaxis(series_name="平均传输时间", y_axis=duration_list)
        .set_global_opts(title_opts=opts.TitleOpts(title="从" + shorten_id(send_id) + "发出消息计算结果"),
                         toolbox_opts=opts.ToolboxOpts(),
                         visualmap_opts=opts.VisualMapOpts(
                             min_=min_value,
                             max_=max_value
                         ),
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
    filename = "/db_state_write_rate.csv"
    # 读取csv文件
    df = pd.read_csv(filepath + filename)
    if len(df) <= 0:
        return render_template('draw.html', chart="<h2>当前文件尚无数据</h2>")

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
    # 获取value中的最大值最小值
    min_value, max_value = 0, 100
    if len(data) != 0:
        min_value = float(min(data, key=lambda x: x['value'])['value'])
        max_value = float(max(data, key=lambda x: x['value'])['value'])
    bar = (
        Bar()
        .add_xaxis(new_df['block_height'].tolist())
        .add_yaxis(series_name="写入耗时", y_axis=data)
        .set_global_opts(title_opts=opts.TitleOpts(title="数据库写入速率"),
                         toolbox_opts=opts.ToolboxOpts(),
                         visualmap_opts=opts.VisualMapOpts(
                             min_=min_value,
                             max_=max_value
                         ),
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
                                     return '区块哈希:'+ params.data.block_hash+ '</br>' +
                                            '写入耗时:'+ params.data.value+ 's' ;
                                 }
                                 """
                             )
                         ),
                         )
    )

    chart, chart_js = parse_html(bar.render_embed())
    return render_template('draw.html', chart=chart, chart_js=chart_js)


# 数据库读取速率
@app.route("/DBStateReadRate")
def get_db_state_read_rate():
    filename = "/db_state_read_rate.csv"
    # 读取csv文件
    df = pd.read_csv(filepath + filename)
    if len(df) <= 0:
        return render_template('draw.html', chart="<h2>当前文件尚无数据</h2>")

    # 使用loc选择特定列
    new_df = df.loc[:, ['block_hash', 'read_duration','type']]
    # 去掉'read_duration'列中的's'
    new_df.loc[:, 'read_duration'] = new_df.loc[:, 'read_duration'].str.replace('s', '')
    # 在'block_hash'列前添加'0x'
    new_df.loc[:, 'block_hash'] = new_df.loc[:, 'block_hash'].apply(lambda x: '0x' + str(x))
    # 重命名'read_duration'列为'value'
    new_df.rename(columns={'read_duration': 'value'}, inplace=True)
    # 将新的DataFrame转换为字典列表
    data = new_df.to_dict('records')
    # 获取value中的最大值最小值
    min_value, max_value = 0, 100
    if len(data) != 0:
        min_value = float(min(data, key=lambda x: x['value'])['value'])
        max_value = float(max(data, key=lambda x: x['value'])['value'])
    bar = (
        Bar()
        .add_xaxis(df["measure_time"].tolist())
        .add_yaxis(series_name="读取耗时", y_axis=data)
        .set_global_opts(title_opts=opts.TitleOpts(title="数据库读取速率"),
                         toolbox_opts=opts.ToolboxOpts(),
                         visualmap_opts=opts.VisualMapOpts(
                             min_=min_value,
                             max_=max_value
                         ),
                         datazoom_opts=[
                             opts.DataZoomOpts(range_start=45, range_end=55),
                         ],
                         xaxis_opts=opts.AxisOpts(name="开始读取时刻"),
                         yaxis_opts=opts.AxisOpts(name="读取耗时/s"),
                         legend_opts=opts.LegendOpts(pos_left="center"),
                         tooltip_opts=opts.TooltipOpts(
                             formatter=JsCode(
                                 """
                                 function (params) {
                                     console.log(params);
                                     return '区块哈希:'+ params.data.block_hash + '</br>' +
                                            '读取位置:'+ params.data.type + '</br>' +
                                            '读取耗时:'+ params.data.value+ 's';
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
            series_name="读取位置",
            data_pair=[list(i) for i in type_counts.items()],  # 将Series转换为列表
            center=["80%", "25%"],
            radius="15%",
        )
        .set_series_opts(
            tooltip_opts=opts.TooltipOpts(
                trigger="item", formatter="{a} <br/>{b}: {c} ({d}%)"
            ),
        )
    )

    bar_hist = construct_bar_hist(new_df['value'], 3, "数据库读取耗时")

    tab = Tab()
    tab.add(bar.overlap(pie), "按时刻查看")
    tab.add(bar_hist, "按频数查看")
    chart, chart_js = parse_html_tab(tab.render_embed())
    return render_template('draw.html', chart=chart, chart_js=chart_js)

# --共识层--
# 每轮PBFT共识耗时
@app.route("/ConsensusPBFTCost")
def get_consensus_pbft_cost():
    filename = "/consensus_pbft_cost.csv"
    # 读取csv文件
    df = pd.read_csv(filepath + filename)
    if len(df) <= 0:
        return render_template('draw.html', chart="<h2>当前文件尚无数据</h2>")

    # 使用loc选择特定列
    new_df = df.loc[:, ['block_height', 'type', 'pbft_cost']]
    # 去掉'pbft_cost'列中的's'
    new_df.loc[:, 'pbft_cost'] = new_df.loc[:, 'pbft_cost'].str.replace('s', '')
    # 重命名'pbft_cost'列为'value'
    new_df.rename(columns={'pbft_cost': 'value'}, inplace=True)
    # 将新的DataFrame转换为字典列表
    data = new_df.to_dict('records')
    # 获取value中的最大值最小值
    min_value, max_value = 0, 100
    if len(data) != 0:
        min_value = float(min(data, key=lambda x: x['value'])['value'])
        max_value = float(max(data, key=lambda x: x['value'])['value'])
    bar = (
        Bar()
        .add_xaxis(new_df['block_height'].tolist())
        .add_yaxis(series_name="共识耗时", y_axis=data)
        .set_global_opts(title_opts=opts.TitleOpts(title="每轮PBFT共识耗时"),
                         toolbox_opts=opts.ToolboxOpts(),
                         visualmap_opts=opts.VisualMapOpts(
                             min_=min_value,
                             max_=max_value
                         ),
                         datazoom_opts=[
                             opts.DataZoomOpts(range_start=40, range_end=60),
                         ],
                         xaxis_opts=opts.AxisOpts(name="区块高度"),
                         yaxis_opts=opts.AxisOpts(name="共识耗时/s"),
                         legend_opts=opts.LegendOpts(pos_left="center"),
                         tooltip_opts=opts.TooltipOpts(
                             formatter=JsCode(
                                 """
                                 function (params) {
                                     console.log(params);
                                     return '区块高度:'+ params.data.block_height+ '</br>' +
                                            '共识类型:'+ params.data.type+ '</br>' +
                                            '共识耗时:'+ params.data.value+ 's' ;
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
            series_name="共识类型",
            data_pair=[list(i) for i in type_counts.items()],  # 将Series转换为列表
            center=["80%", "25%"],
            radius="15%",
        )
        .set_series_opts(
            tooltip_opts=opts.TooltipOpts(
                trigger="item", formatter="{a} <br/>{b}: {c} ({d}%)"
            ),
        )
    )

    chart, chart_js = parse_html(bar.overlap(pie).render_embed())
    return render_template('draw.html', chart=chart, chart_js=chart_js)

# 每轮Raft共识耗时
@app.route("/ConsensusRaftCost")
def get_consensus_raft_cost():
    filename = "/consensus_raft_cost.csv"
    # 读取csv文件
    df = pd.read_csv(filepath + filename)
    if len(df) <= 0:
        return render_template('draw.html', chart="<h2>当前文件尚无数据</h2>")

    # 使用loc选择特定列
    new_df = df.loc[:, ['block_height', 'raft_cost']]
    # 去掉'raft_cost'列中的's'
    new_df.loc[:, 'raft_cost'] = new_df.loc[:, 'raft_cost'].str.replace('s', '')
    # 重命名'raft_cost'列为'value'
    new_df.rename(columns={'raft_cost': 'value'}, inplace=True)
    # 将新的DataFrame转换为字典列表
    data = new_df.to_dict('records')
    # 获取value中的最大值最小值
    min_value , max_value = 0 , 100
    if len(data) != 0:
        min_value = float(min(data, key=lambda x: x['value'])['value'])
        max_value = float(max(data, key=lambda x: x['value'])['value'])
    bar = (
        Bar()
        .add_xaxis(new_df['block_height'].tolist())
        .add_yaxis(series_name="共识耗时", y_axis=data)
        .set_global_opts(title_opts=opts.TitleOpts(title="每轮Raft共识耗时"),
                         toolbox_opts=opts.ToolboxOpts(),
                         visualmap_opts=opts.VisualMapOpts(
                             min_=min_value,
                             max_=max_value
                         ),
                         datazoom_opts=[
                             opts.DataZoomOpts(range_start=40, range_end=60),
                         ],
                         xaxis_opts=opts.AxisOpts(name="区块高度"),
                         yaxis_opts=opts.AxisOpts(name="共识耗时/s"),
                         legend_opts=opts.LegendOpts(pos_left="center"),
                         tooltip_opts=opts.TooltipOpts(
                             formatter=JsCode(
                                 """
                                 function (params) {
                                     console.log(params);
                                     return '区块高度:'+ params.data.block_height+ '</br>' +
                                            '共识类型:'+ 'Raft' + '</br>' +
                                            '共识耗时:'+ params.data.value+ 's' ;
                                 }
                                 """
                             )
                         ),
                         )
    )

    chart, chart_js = parse_html(bar.render_embed())
    return render_template('draw.html', chart=chart, chart_js=chart_js)
# --合约层--
# 合约执行时间
@app.route("/ContractTime")
def get_contract_time():
    filename = "/contract_time.csv"
    # 读取csv文件
    df = pd.read_csv(filepath + filename)
    if len(df) <= 0:
        return render_template('draw.html', chart="<h2>当前文件尚无数据</h2>")

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
    # 获取value中的最大值最小值
    min_value, max_value = 0, 100
    if len(data) != 0:
        min_value = float(min(data, key=lambda x: x['value'])['value'])
        max_value = float(max(data, key=lambda x: x['value'])['value'])
    bar = (
        Bar()
        .add_xaxis(df["start_time"].tolist())
        .add_yaxis(series_name="执行时间", y_axis=data)
        .set_global_opts(title_opts=opts.TitleOpts(title="合约执行时间"),
                         toolbox_opts=opts.ToolboxOpts(),
                         visualmap_opts=opts.VisualMapOpts(
                             min_ = min_value,
                             max_ = max_value
                         ),
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
                                             '交易哈希:'+ params.data.tx_hash  + '</br>' +
                                             '执行时间:'+ params.data.value+ 's' ;
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
            center=["80%", "25%"],
            radius="15%",
        )
        .set_series_opts(
            tooltip_opts=opts.TooltipOpts(
                trigger="item", formatter="{a} <br/>{b}: {c} ({d}%)"
            ),
        )
    )
    bar_hist = construct_bar_hist(new_df['value'], 5, "合约执行时间")

    tab = Tab()
    tab.add(bar.overlap(pie), "按时刻查看")
    tab.add(bar_hist, "按频数查看")
    chart, chart_js = parse_html_tab(tab.render_embed())
    return render_template('draw.html', chart=chart, chart_js=chart_js)


# --交易生命周期--
# 交易延迟
@app.route("/TxDelay")
def get_tx_delay():
    # 读取csv文件
    df_start = pd.read_csv(filepath + '/tx_delay_start.csv')
    df_end = pd.read_csv(filepath + '/tx_delay_end.csv')
    if len(df_start) <= 0 or len(df_end) <= 0:
        return render_template('draw.html', chart="<h2>当前文件尚无数据</h2>")
    # 重命名列
    df_start = df_start.rename(columns={'measure_time': 'start_time'})
    df_end = df_end.rename(columns={'measure_time': 'end_time'})
    # 合并df_start和df_end
    df = pd.merge(df_start, df_end, on='tx_hash')
    # 计算时间差
    df['duration'] = df.apply(lambda row: calculate_duration(row['end_time'], row['start_time']), axis=1)
    df = df[df['duration'] >= 0]

    # 在'tx_hash'列前添加'0x'
    df.loc[:, 'tx_hash'] = df.loc[:, 'tx_hash'].apply(lambda x: '0x' + str(x))
    # 重命名'duration'列为'value'
    df.rename(columns={'duration': 'value'}, inplace=True)
    # 将新的DataFrame转换为字典列表
    data = df.to_dict('records')
    # 获取value中的最大值最小值
    min_value, max_value = 0, 100
    if len(data) != 0:
        min_value = float(min(data, key=lambda x: x['value'])['value'])
        max_value = float(max(data, key=lambda x: x['value'])['value'])
    bar = (
        Bar()
        .add_xaxis(df["start_time"].tolist())
        .add_yaxis(series_name="交易延迟", y_axis=data)
        .set_global_opts(title_opts=opts.TitleOpts(title="交易延迟"),
                         toolbox_opts=opts.ToolboxOpts(),
                         visualmap_opts=opts.VisualMapOpts(
                             min_ = min_value,
                             max_ = max_value
                         ),
                         datazoom_opts=[
                             opts.DataZoomOpts(range_start=45, range_end=55),
                         ],
                         xaxis_opts=opts.AxisOpts(name="进入交易池时刻"),
                         yaxis_opts=opts.AxisOpts(name="交易延迟/s"),
                         tooltip_opts=opts.TooltipOpts(
                             formatter=JsCode(
                                 """
                                 function (params) {
                                     console.log(params);
                                     return '区块高度:'+ params.data.block_height + '</br>' +
                                             '交易哈希:'+ params.data.tx_hash  + '</br>' +
                                             '交易延迟:'+ params.data.value+ 's' ;
                                 }
                                 """
                             )
                         ),
                         )

    )
    bar_hist = construct_bar_hist(df['value'], 10, "交易延迟")

    tab = Tab()
    tab.add(bar, "按时刻查看")
    tab.add(bar_hist, "按频数查看")
    chart, chart_js = parse_html_tab(tab.render_embed())
    return render_template('draw.html', chart=chart, chart_js=chart_js)

# 交易排队时延
@app.route("/TxQueueDelay")
def get_tx_queue_delay():
    # 读取csv文件
    df = pd.read_csv(filepath + '/tx_queue_delay.csv')
    if len(df) <= 0:
        return render_template('draw.html', chart="<h2>当前文件尚无数据</h2>")
    # 根据"in/outFlag"列的值选择行，并分别赋值给df_in和df_out
    df_in = df.loc[df['in/outFlag'] == 'in']
    df_out = df.loc[df['in/outFlag'] == 'out']
    # 重命名列
    df_in = df_in.rename(columns={'measure_time': 'start_time'})
    df_out = df_out.rename(columns={'measure_time': 'end_time'})
    # 合并df_in和df_out
    df = pd.merge(df_in, df_out, on='tx_hash')
    # 计算时间差
    df['duration'] = df.apply(lambda row: calculate_duration(row['end_time'], row['start_time']), axis=1)
    df = df[df['duration'] >= 0]

    # 在'tx_hash'列前添加'0x'
    df.loc[:, 'tx_hash'] = df.loc[:, 'tx_hash'].apply(lambda x: '0x' + str(x))
    # 重命名'duration'列为'value'
    df.rename(columns={'duration': 'value'}, inplace=True)
    # 将新的DataFrame转换为字典列表
    data = df.to_dict('records')
    # 获取value中的最大值最小值
    min_value, max_value = 0, 100
    if len(data) != 0:
        min_value = float(min(data, key=lambda x: x['value'])['value'])
        max_value = float(max(data, key=lambda x: x['value'])['value'])
    bar = (
        Bar()
        .add_xaxis(df["start_time"].tolist())
        .add_yaxis(series_name="交易排队时延", y_axis=data)
        .set_global_opts(title_opts=opts.TitleOpts(title="交易排队时延"),
                         toolbox_opts=opts.ToolboxOpts(),
                         visualmap_opts=opts.VisualMapOpts(
                             min_ = min_value,
                             max_ = max_value
                         ),
                         datazoom_opts=[
                             opts.DataZoomOpts(range_start=45, range_end=55),
                         ],
                         xaxis_opts=opts.AxisOpts(name="进入交易池时刻"),
                         yaxis_opts=opts.AxisOpts(name="交易排队时延/s"),
                         tooltip_opts=opts.TooltipOpts(
                             formatter=JsCode(
                                 """
                                 function (params) {
                                     console.log(params);
                                     return  '交易哈希:'+ params.data.tx_hash  + '</br>' +
                                             '交易排队时延:'+ params.data.value+ 's' ;
                                 }
                                 """
                             )
                         ),
                         )

    )
    bar_hist = construct_bar_hist(df['value'], 10, "交易排队时延")

    tab = Tab()
    tab.add(bar, "按时刻查看")
    tab.add(bar_hist, "按频数查看")
    chart, chart_js = parse_html_tab(tab.render_embed())
    return render_template('draw.html', chart=chart, chart_js=chart_js)

# 交易池输入通量
@app.route("/TransactionPoolInputThroughput")
def get_transaction_pool_input_throughput():
    filename = "/transaction_pool_input_throughput.csv"
    # 读取csv文件
    df = pd.read_csv(filepath + filename)
    if len(df) <= 0:
        return render_template('draw.html', chart="<h2>当前文件尚无数据</h2>")

    sum_txs = df.shape[0]  # 当前记录的交易数
    start_time = str(df.iloc[0]['measure_time'])  # 第一条的时间
    end_time = str(df.iloc[-1]['measure_time'])  # 最后一条的时间
    duration = calculate_duration(end_time, start_time)  # 总记录时间
    txpool_input_throughput = sum_txs / duration  # 交易池输入通量

    # 把1修改为local 2修改为rpc
    df['source'] = df['source'].replace({1: 'local', 2: 'rpc'})

    # 拼接标注字符串
    JsStr = "['开始时间: " + start_time + "','结束时间: "+ end_time + "','总记录时间: "+ str(duration) + "s" "','交易数: "+ str(sum_txs) +"','交易池输入通量: " +str(txpool_input_throughput)+"'].join('\\n')"
    type_counts = df["source"].value_counts()
    pie = (
        Pie()
        .add(
            series_name="交易来源",
            data_pair=[list(i) for i in type_counts.items()],  # 将Series转换为列表
            # center=["80%", "25%"],
            # radius="15%",
        )
        .set_global_opts(graphic_opts=[
            opts.GraphicGroup(
                graphic_item=opts.GraphicItem(left="1%", top="15%"),
                children=[
                    opts.GraphicRect(
                        graphic_item=opts.GraphicItem(
                            z=100, left="center", top="middle"
                        ),
                        graphic_shape_opts=opts.GraphicShapeOpts(width=260, height=90),
                        graphic_basicstyle_opts=opts.GraphicBasicStyleOpts(
                            fill="#0b3a8a30",
                            shadow_blur=8,
                            shadow_offset_x=3,
                            shadow_offset_y=3,
                            shadow_color="rgba(0,0,0,0.3)",
                        ),
                    ),
                    opts.GraphicText(
                        graphic_item=opts.GraphicItem(
                            left="center", top="middle", z=100
                        ),
                        graphic_textstyle_opts=opts.GraphicTextStyleOpts(
                            text=JsCode(
                                JsStr
                            ),
                            font="14px Microsoft YaHei",
                            graphic_basicstyle_opts=opts.GraphicBasicStyleOpts(
                                fill="#333"
                            ),
                        ),
                    ),
                ],
            )
        ],)
        .set_series_opts(
            tooltip_opts=opts.TooltipOpts(
                trigger="item", formatter="{a} <br/>{b}: {c} ({d}%)"
            ),
        )
    )


    chart, chart_js = parse_html(pie.render_embed())
    return render_template('draw.html', chart=chart, chart_js=chart_js)

# 出块耗时
@app.route("/BlockCommitDuration")
def get_block_commit_duration():
    # 读取csv文件
    df_start = pd.read_csv(filepath + '/block_commit_duration_start.csv')
    df_end = pd.read_csv(filepath + '/block_commit_duration_end.csv')
    if len(df_start) <= 0 or len(df_end) <= 0:
        return render_template('draw.html', chart="<h2>当前文件尚无数据</h2>")

    # 重命名列
    df_start = df_start.rename(columns={'measure_time': 'start_time'})
    df_end = df_end.rename(columns={'measure_time': 'end_time'})
    # 合并df_start和df_end
    df = pd.merge(df_start, df_end, on='block_height')
    # 对于相同高度的区块，可能多次触发该节点准备打包，只保留最后一次记录时间
    df.drop_duplicates(subset='block_height', keep='last', inplace=True)
    # 计算时间差
    df['duration'] = df.apply(lambda row: calculate_duration(row['end_time'], row['start_time']), axis=1)
    df = df[df['duration'] >= 0]

    # 在'block_hash'和'block_txsroot'列前添加'0x'
    df.loc[:, 'block_hash'] = df.loc[:, 'block_hash'].apply(lambda x: '0x' + str(x))
    df.loc[:, 'block_txsroot'] = df.loc[:, 'block_txsroot'].apply(lambda x: '0x' + str(x))
    # 重命名'duration'列为'value'
    df.rename(columns={'duration': 'value'}, inplace=True)
    # 将新的DataFrame转换为字典列表
    data = df.to_dict('records')
    # 获取value中的最大值最小值
    min_value, max_value = 0, 100
    if len(data) != 0:
        min_value = float(min(data, key=lambda x: x['value'])['value'])
        max_value = float(max(data, key=lambda x: x['value'])['value'])
    bar = (
        Bar()
        .add_xaxis(df["block_height"].tolist())
        .add_yaxis(series_name="当前节点出块耗时", y_axis=data)
        .set_global_opts(title_opts=opts.TitleOpts(title="当前节点出块耗时"),
                         toolbox_opts=opts.ToolboxOpts(),
                         visualmap_opts=opts.VisualMapOpts(
                             min_ = min_value,
                             max_ = max_value
                         ),
                         datazoom_opts=[
                             opts.DataZoomOpts(range_start=45, range_end=55),
                         ],
                         xaxis_opts=opts.AxisOpts(name="区块高度"),
                         yaxis_opts=opts.AxisOpts(name="出块耗时/s"),
                         tooltip_opts=opts.TooltipOpts(
                             formatter=JsCode(
                                 """
                                 function (params) {
                                     console.log(params);
                                     return '区块高度:'+ params.data.block_height + '</br>' +
                                             '区块哈希:'+ params.data.block_hash  + '</br>' +
                                             '块内交易数量:'+ params.data.block_tx_count  + '</br>' +
                                             '块内交易树根:'+ params.data.block_txsroot  + '</br>' +
                                             '出块耗时:'+ params.data.value+ 's' ;
                                 }
                                 """
                             )
                         ),
                         )

    )
    chart, chart_js = parse_html(bar.render_embed())
    return render_template('draw.html', chart=chart, chart_js=chart_js)

# 块内交易吞吐量
@app.route("/TxInBlockTps")
def get_tx_in_block_tps():
    # 读取csv文件
    df_start = pd.read_csv(filepath + '/tx_in_block_tps.csv')  # 打包完成时刻
    df_end = pd.read_csv(filepath + '/block_commit_duration_end.csv')  # 区块落库时刻
    if len(df_start) <= 0 or len(df_end) <= 0:
        return render_template('draw.html', chart="<h2>当前文件尚无数据</h2>")
    # 重命名列
    df_start = df_start.rename(columns={'measure_time': 'start_time'})
    df_end = df_end.rename(columns={'measure_time': 'end_time'})
    # 按照block_txsroot合并df_start和df_end
    df = pd.merge(df_start, df_end, on='block_txsroot')
    # 计算时间差
    df['duration'] = df.apply(lambda row: calculate_duration(row['end_time'], row['start_time']), axis=1)
    df = df[df['duration'] >= 0]
    # 计算块内吞吐量 = 块内交易数 / 耗时
    df['block_tps'] = df['block_tx_count_x'] / df['duration']

    # 在'block_hash'和'block_txsroot'列前添加'0x'
    df.loc[:, 'block_hash'] = df.loc[:, 'block_hash'].apply(lambda x: '0x' + str(x))
    df.loc[:, 'block_txsroot'] = df.loc[:, 'block_txsroot'].apply(lambda x: '0x' + str(x))
    # 重命名'block_tps'列为'value'
    df.rename(columns={'block_tps': 'value'}, inplace=True)
    # 将新的DataFrame转换为字典列表
    data = df.to_dict('records')
    # 获取value中的最大值最小值
    min_value, max_value = 0, 100
    if len(data) != 0:
        min_value = float(min(data, key=lambda x: x['value'])['value'])
        max_value = float(max(data, key=lambda x: x['value'])['value'])
    bar = (
        Bar()
        .add_xaxis(df["block_height_x"].tolist())
        .add_yaxis(series_name="块内交易吞吐量", y_axis=data)
        .set_global_opts(title_opts=opts.TitleOpts(title="块内交易吞吐量"),
                         toolbox_opts=opts.ToolboxOpts(),
                         visualmap_opts=opts.VisualMapOpts(
                             min_ = min_value,
                             max_ = max_value
                         ),
                         datazoom_opts=[
                             opts.DataZoomOpts(range_start=45, range_end=55),
                         ],
                         xaxis_opts=opts.AxisOpts(name="区块高度"),
                         yaxis_opts=opts.AxisOpts(name="块内交易吞吐量(笔/s)"),
                         tooltip_opts=opts.TooltipOpts(
                             formatter=JsCode(
                                 """
                                 function (params) {
                                     console.log(params);
                                     return '区块高度:'+ params.data.block_height_x + '</br>' +
                                             '区块哈希:'+ params.data.block_hash  + '</br>' +
                                             '块内交易数量:'+ params.data.block_tx_count_x  + '</br>' +
                                             '块内交易树根:'+ params.data.block_txsroot  + '</br>' +
                                             '打包到落库耗时:'+ params.data.duration+ 's'+ '</br>' +
                                             '块内交易吞吐量:'+ params.data.value+ '笔/s' ;
                                 }
                                 """
                             )
                         ),
                         )

    )
    chart, chart_js = parse_html(bar.render_embed())
    return render_template('draw.html', chart=chart, chart_js=chart_js)

# 块内交易冲突率
@app.route("/BlockTxConflictRate")
def get_block_tx_conflict_rate():
    # 读取csv文件
    df = pd.read_csv(filepath + '/block_tx_conflict_rate.csv')
    if len(df) <= 0:
        return render_template('draw.html', chart="<h2>当前文件尚无数据</h2>")
    # 按block_height分组
    grouped = df.groupby('block_height')
    # 创建一个新的DataFrame来存储结果
    new_df = pd.DataFrame(columns=['block_height', 'duration', 'cft_cnt', 'conflict_rate', 'block_tx_count'])
    # 对于每个group
    for name, group in grouped:
        # 计算duration
        duration = calculate_duration(group['measure_time'].max(), group['measure_time'].min())
        # 计算cft_cnt(直接取最大值，如果最大值超过了块内交易数，设置为块内交易数)
        cft_cnt = max(group['conflict_count'])
        block_tx_count = max(group['block_tx_count'])
        if cft_cnt > block_tx_count:
            cft_cnt = block_tx_count
        # 计算conflict_rate
        conflict_rate = cft_cnt / block_tx_count
        # 将结果添加到新的DataFrame中
        new_row = pd.DataFrame(
            {'block_height': [name], 'duration': [duration], 'cft_cnt': [cft_cnt], 'conflict_rate': [conflict_rate],
             'block_tx_count': [block_tx_count]})
        new_df = pd.concat([new_df, new_row], ignore_index=True)

    # 重命名'conflict_rate'列为'value'
    new_df.rename(columns={'conflict_rate': 'value'}, inplace=True)
    # 将新的DataFrame转换为字典列表
    data = new_df.to_dict('records')
    # 获取value中的最大值最小值
    min_value, max_value = 0, 100
    if len(data) != 0:
        min_value = float(min(data, key=lambda x: x['value'])['value'])
        max_value = float(max(data, key=lambda x: x['value'])['value'])
    bar = (
        Bar()
        .add_xaxis(new_df["block_height"].tolist())
        .add_yaxis(series_name="块内交易冲突率", y_axis=data)
        .set_global_opts(title_opts=opts.TitleOpts(title="块内交易冲突率"),
                         toolbox_opts=opts.ToolboxOpts(),
                         visualmap_opts=opts.VisualMapOpts(
                             min_ = min_value,
                             max_ = max_value
                         ),
                         datazoom_opts=[
                             opts.DataZoomOpts(range_start=45, range_end=55),
                         ],
                         xaxis_opts=opts.AxisOpts(name="区块高度"),
                         yaxis_opts=opts.AxisOpts(name="块内交易冲突率"),
                         tooltip_opts=opts.TooltipOpts(
                             formatter=JsCode(
                                 """
                                 function (params) {
                                     console.log(params);
                                     return '区块高度:'+ params.data.block_height + '</br>' +
                                             '块内交易数量:'+ params.data.block_tx_count  + '</br>' +
                                             '块内冲突交易数量:'+ params.data.cft_cnt  + '</br>' +
                                             '构造DAG耗时:'+ params.data.duration+ 's'+ '</br>' +
                                             '块内交易冲突率:'+ params.data.value*100+ '%' ;
                                 }
                                 """
                             )
                         ),
                         )

    )
    chart, chart_js = parse_html(bar.render_embed())
    return render_template('draw.html', chart=chart, chart_js=chart_js)

# 区块验证效率
@app.route("/BlockValidationEfficiency")
def get_block_validation_efficiency():
    # 读取csv文件
    df = pd.read_csv(filepath + '/block_validation_efficiency.csv')  # 打包完成时刻
    if len(df) <= 0:
        return render_template('draw.html', chart="<h2>当前文件尚无数据</h2>")
    # 计算时间差
    df['duration'] = df.apply(lambda row: calculate_duration(row['end_time'], row['start_time']), axis=1)
    df = df[df['duration'] >= 0]
    # 计算区块验证效率 = 块内交易数 / 验证耗时
    df['valid_efficiency'] = df['block_tx_count'] / df['duration']
    # 重命名'valid_efficiency'列为'value'
    df.rename(columns={'valid_efficiency': 'value'}, inplace=True)
    # 将新的DataFrame转换为字典列表
    data = df.to_dict('records')
    # 获取value中的最大值最小值
    min_value, max_value = 0, 100
    if len(data) != 0:
        min_value = float(min(data, key=lambda x: x['value'])['value'])
        max_value = float(max(data, key=lambda x: x['value'])['value'])
    bar = (
        Bar()
        .add_xaxis(df["block_height"].tolist())
        .add_yaxis(series_name="区块验证效率", y_axis=data)
        .set_global_opts(title_opts=opts.TitleOpts(title="区块验证效率"),
                         toolbox_opts=opts.ToolboxOpts(),
                         visualmap_opts=opts.VisualMapOpts(
                             min_ = min_value,
                             max_ = max_value
                         ),
                         datazoom_opts=[
                             opts.DataZoomOpts(range_start=45, range_end=55),
                         ],
                         xaxis_opts=opts.AxisOpts(name="区块高度"),
                         yaxis_opts=opts.AxisOpts(name="区块验证效率(笔/s)"),
                         tooltip_opts=opts.TooltipOpts(
                             formatter=JsCode(
                                 """
                                 function (params) {
                                     console.log(params);
                                     return '区块高度:'+ params.data.block_height + '</br>' +
                                             '块内交易数量:'+ params.data.block_tx_count  + '</br>' +
                                             '区块验证耗时:'+ params.data.duration+ 's'+ '</br>' +
                                             '区块验证效率:'+ params.data.value+ '笔/s' ;
                                 }
                                 """
                             )
                         ),
                         )

    )
    chart, chart_js = parse_html(bar.render_embed())
    return render_template('draw.html', chart=chart, chart_js=chart_js)


# 增加分布---交易排队时延
@app.route("/Try")
def get_try():
    # 读取csv文件
    df = pd.read_csv(filepath + '/tx_queue_delay.csv')
    if len(df) <= 0:
        return render_template('draw.html', chart="<h2>当前文件尚无数据</h2>")
    # 根据"in/outFlag"列的值选择行，并分别赋值给df_in和df_out
    df_in = df.loc[df['in/outFlag'] == 'in']
    df_out = df.loc[df['in/outFlag'] == 'out']
    # 重命名列
    df_in = df_in.rename(columns={'measure_time': 'start_time'})
    df_out = df_out.rename(columns={'measure_time': 'end_time'})
    # 合并df_in和df_out
    df = pd.merge(df_in, df_out, on='tx_hash')
    # 计算时间差
    df['duration'] = df.apply(lambda row: calculate_duration(row['end_time'], row['start_time']), axis=1)
    df = df[df['duration'] >= 0]

    # 在'tx_hash'列前添加'0x'
    df.loc[:, 'tx_hash'] = df.loc[:, 'tx_hash'].apply(lambda x: '0x' + str(x))
    # 重命名'duration'列为'value'
    df.rename(columns={'duration': 'value'}, inplace=True)
    # 将新的DataFrame转换为字典列表
    data = df.to_dict('records')
    # 获取value中的最大值最小值
    min_value, max_value = 0, 100
    if len(data) != 0:
        min_value = float(min(data, key=lambda x: x['value'])['value'])
        max_value = float(max(data, key=lambda x: x['value'])['value'])
    bar = (
        Bar()
        .add_xaxis(df["start_time"].tolist())
        .add_yaxis(series_name="交易排队时延", y_axis=data)
        .set_global_opts(title_opts=opts.TitleOpts(title="交易排队时延"),
                         toolbox_opts=opts.ToolboxOpts(),
                         visualmap_opts=opts.VisualMapOpts(
                             min_ = min_value,
                             max_ = max_value
                         ),
                         datazoom_opts=[
                             opts.DataZoomOpts(range_start=45, range_end=55),
                         ],
                         xaxis_opts=opts.AxisOpts(name="进入交易池时刻"),
                         yaxis_opts=opts.AxisOpts(name="交易排队时延/s"),
                         tooltip_opts=opts.TooltipOpts(
                             formatter=JsCode(
                                 """
                                 function (params) {
                                     console.log(params);
                                     return  '交易哈希:'+ params.data.tx_hash  + '</br>' +
                                             '交易排队时延:'+ params.data.value+ 's' ;
                                 }
                                 """
                             )
                         ),
        )

    )

    bar_hist = construct_bar_hist(df['value'],10,"交易排队时延")

    tab = Tab()
    tab.add(bar, "按时刻查看")
    tab.add(bar_hist, "按频数查看")
    chart, chart_js = parse_html_tab(tab.render_embed())
    return render_template('draw.html', chart=chart, chart_js=chart_js)

if __name__ == "__main__":
    app.run(debug=True)
