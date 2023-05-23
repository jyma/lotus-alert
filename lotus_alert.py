#!/usr/bin/env python3
#########################################################################
# 本脚本用于FileCoin日常巡检，及时告警通知到企业微信。
# 我们致力于提供开箱即用的Fil挖矿技术解决方案
# 如有问题联系脚本作者「mje」：
# WeChat：Mjy_Dream
#########################################################################

from __future__ import print_function
import time
import json
import re
import sys
import traceback
import subprocess as sp
from datetime import datetime, timedelta
import requests

# Server酱SendKey「必填，填写为自己的SendKey」
send_key = "SCT42628TJaSsasadfasfdsfdfghevwVfft"
# 可配置Server酱推送到企业微信中特定人或多个人「选填，具体可参考文档」
openid = "yingtaoxiaowanzi|jyma"
# 脚本运行所在的机器类型
# lotus（一）、Seal-Miner（二）、Wining-Miner（三）、WindowPost-Miner（四）、存储机（五）
# 现做出约定，直接填写一、二、三、四来表示对应的机器类型，可写入多个类型
check_machine = "一二三四"
# 机器别名，告警信息中进行展示，可以快速定位是哪台机器发出的告警信息
machine_name = "Miner_6_11"
# 需要进行服务器宕机/网络不可达检验的内网ip，以|号分割
server_ip = "192.168.7.11|192.168.7.12"
# 需要进行网络不可达检验的公网ip及端口号，多个以|号分割)
net_ip = "221.10.215.218 8080|115.228.39.103 22"
# 存储挂载路径及磁盘剩余空间监测，填写需要监测的磁盘挂载目录，若为根目录挂载可以直接填写`/`，多个挂载目录使用`|`进行分隔
file_mount = "/ipfsdata|/|/data1"
# 阵列卡磁盘个数
raid_disk_num = 36
# 剩余磁盘空间监测，默认是单位是G，监测的目录为`file_mount`中填写的路径
disk_avail_alert = 150
# 是否开启每日简报，每日简报默认运行在Wining-Miner机器上，默认每天上午12点进行推送，同时该功能需要获取其他运行告警脚本机器上的日志信息
daily_summary = True
# 每日简报准点发送时间，如12即每天上午12时发送
daily_summary_time = "12"
# 所有运行该告警脚本的机器内网ip，以|号分割，用来收集所有机器告警脚本日志中的信息
collection_ip = "192.168.7.11|192.168.7.12|192.168.7.13|192.168.6.11|192.168.2.11"
# 所有运行该脚本的机器的告警日志路径（建议所有机器告警日志在同一目录下）
alert_log_path = "/home/ps/alert.log"
# WindowPost—Miner日志路径「选填，在WindowPost-Miner上运行时需要填写」
wdpost_log_path = "/home/ps/miner.log"
# fil_account 为你的Miner节点号「必填，用于爆块检测」
fil_account = "f01761579"
# 最长时间任务告警，p1默认是小时，p2默认是分钟，c默认是分钟，「选填」
p1_job_time_alert = 5
p2_job_time_alert = 40
c2_job_time_alert = 25
# Default钱包余额告警阈值「选填，默认50」
default_wallet_balance = 20
# check_interval 程序循环检查间隔默认300秒
check_interval = 300
# ssh 登录授权IP地址,以|号分割，如果登录IP不在列表中，将发出告警消息。
ssh_white_ip_list = "192.168.85.10|221.10.1.1"


def print(s, end="\n", file=sys.stdout):
    file.write(s + end)
    file.flush()


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        pass

    try:
        import unicodedata

        unicodedata.numeric(s)
        return True
    except (TypeError, ValueError):
        pass
    return False


def is_valid_date(strdate):
    try:
        time.strptime(strdate, "%a %b %d %H:%M:%S %Y")
        return True
    except:
        return False


def today_anytime_tsp(hour):
    minute = 0
    second = 0
    now = datetime.now()
    today_0 = now - timedelta(hours=now.hour, minutes=now.minute, seconds=now.second)
    today_anytime = today_0 + timedelta(hours=hour, minutes=minute, seconds=second)
    tsp = today_anytime.timestamp()
    return tsp


def server_post(title="", content="默认正文"):
    global send_key
    global fil_account
    global openid
    global daily_summary
    api = "https://sctapi.ftqq.com/" + send_key + ".send"
    title = fil_account + ":" + title
    data = {"text": title, "desp": content, "openid": openid}
    try:
        req = requests.post(api, data=data)
        req_json = json.loads(req.text)
        if req_json.get("data").get("errno") == 0:
            print("server message sent successfully: " + machine_name + " | " + content)
            return True
        else:
            # print("server message sent failed: " + req.text)
            return False
    except requests.exceptions.RequestException as req_error:
        return False
        print("Request error: " + req_error)
    except Exception as e:
        return False
        print("Fail to send message: " + e)


# 高度同步检查
def chain_check():
    try:
        out = sp.getoutput("timeout 36s lotus sync wait")
        print("chain_check:")
        print(out)
        if out.endswith("Done!"):
            print("true")
            return True
        server_post(machine_name, "节点同步出错，请及时排查！")
        return False
    except Exception as e:
        print("Fail to send message: " + e)


# 显卡驱动检查


def nvidia_check():
    out = sp.getoutput("timeout 30s echo $(nvidia-smi | grep GeForce)")
    print("nvidia_check:")
    print(out)
    if out.find("GeForce") >= 0:
        print("true")
        return True
    server_post(machine_name, "显卡驱动故障，请及时排查！")
    return False


# miner进程检查


def minerprocess_check():
    time.sleep(5)
    out = sp.getoutput("timeout 30s echo $(pidof lotus-miner)")
    print("minerprocess_check:")
    print(out)
    if out.strip():
        print("true")
        return True
    server_post(machine_name, "Miner进程丢失，请及时排查！")
    return False


# lotus进程检查


def lotusprocess_check():
    out = sp.getoutput("timeout 30s echo $(pidof lotus)")
    print("lotusprocess_check:")
    print(out)
    if out.strip():
        print("true")
        return True
    server_post(machine_name, "Lotus进程丢失，请及时排查！")
    print("false")
    return False


# 消息堵塞检查


def mpool_check():
    out = sp.getoutput("lotus mpool pending --local | wc -l")
    print("mpool_check:")
    print(out)
    if is_number(out):
        if int(out) <= 240:
            print("true")
            return True
        server_post(machine_name, "消息堵塞，请及时清理！")
    return False


# 存储文件挂载检查，磁盘容量剩余检查


def fm_check(check_type=""):
    global file_mount
    is_fm_correct = True
    fs = file_mount.split("|")
    for str in fs:
        out = sp.getoutput(
            "timeout 30s echo $(df -h |awk '{print $6,$4}'|grep -w "
            + str
            + " |awk '{print $2}'"
            + ")"
        )
        print("fm_check:")
        print(out)
        if not out.strip():
            print("false")
            server_post(machine_name, "未发现存储挂载目录，请及时排查！")
            is_fm_correct = False
        if out.find("G") >= 0 and int(out[0 : out.find("G")]) <= disk_avail_alert:
            print("false")
            server_post(machine_name, "磁盘空间不足，请及时排查！")
            is_fm_correct = False
    return is_fm_correct


# WindowPost—Miner日志报错检查


def wdpost_log_check():
    out = sp.getoutput("cat " + wdpost_log_path + "| grep 'running window post failed'")
    print("wdpost_log_check:")
    print(out)
    if not out.strip():
        print("true")
        return True
    server_post(machine_name, "Wdpost报错，请及时处理！")
    return False


# WiningPost—Miner爆块检查


def mined_block_check(chain_time):
    mined_block_cmd = "lotus chain list --count {0} |grep {1} |wc -l".format(
        int(chain_time / 30), fil_account
    )
    out = sp.getoutput(mined_block_cmd)
    print("mined_block_check:")
    print(out)
    block_count = int(out)
    if block_count > 0 and not daily_summary:
        server_post(
            machine_name, "{0}又爆了{1}个块".format(fil_account, block_count) + "，大吉大利，今晚吃鸡"
        )
    return out


# P1任务超时检查


def p1_overtime_check():
    global p1_job_time_alert
    out = sp.getoutput(
        "lotus-miner sealing jobs | grep -w PC1 | awk '{ print $7}' | head -n 1 | tail -n 1"
    )
    print("overtime_check:")
    print(out)
    if (out.find("Time") >= 0) or (not out.find("h") >= 0):
        print("time true")
        return True
    if out.strip() and int(out[0 : out.find("h")]) <= p1_job_time_alert:
        print(out[0 : out.find("h")])
        print("true")
        return True
    server_post(machine_name, "P1封装任务超时，请及时处理！")
    return False


# P2任务超时检查


def p2_overtime_check():
    global p2_job_time_alert
    out = sp.getoutput(
        "lotus-miner sealing jobs | grep -w PC2 | awk '{ print $7}' | head -n 1 | tail -n 1"
    )
    print("overtime_check:")
    print(out)
    if not out.find("h") >= 0:
        if (out.find("Time") >= 0) or (not out.find("m") >= 0):
            print("time true")
            return True
        if out.strip() and int(out[0 : out.find("m")]) <= p2_job_time_alert:
            print(out[0 : out.find("m")])
            print("true")
            return True
    server_post(machine_name, "P2封装任务超时，请及时处理！")
    return False


# C2任务超时检查


def c2_overtime_check():
    global c2_job_time_alert
    out = sp.getoutput(
        "lotus-miner sealing jobs | grep -w C2 | awk '{ print $7}' | head -n 1 | tail -n 1"
    )
    print("overtime_check:")
    print(out)
    if not out.find("h") >= 0:
        if (out.find("Time") >= 0) or (not out.find("m") >= 0):
            print("time true")
            return True
        if out.strip() and int(out[0 : out.find("m")]) <= c2_job_time_alert:
            print(out[0 : out.find("m")])
            print("true")
            return True
    server_post(machine_name, "C2封装任务超时，请及时处理！")
    return False


# Default钱包余额预警


def balance_check():
    global default_wallet_balance
    out = sp.getoutput("lotus wallet balance")
    print("balance_check:")
    print(out)
    balance = out.split(" ")
    if is_number(balance[0]):
        if float(balance[0]) < default_wallet_balance:
            print("false")
            server_post(machine_name, "钱包余额不足，请及时充值！")
            return False
    return True


# 检查内网服务器是否可达（宕机或网络不通）


def reachable_check():
    try:
        global server_ip
        is_reachable = True
        ips = server_ip.split("|")
        print("reachable_check:")
        for ip in ips:
            print(ip)
            p = sp.Popen(
                ["ping -c 1 -W 1 " + ip], stdout=sp.PIPE, stderr=sp.PIPE, shell=True
            )
            out = p.stdout.read()
            regex = re.compile("100% packet loss")
            if len(regex.findall(str(out))) != 0:
                print("false")
                server_post(machine_name, str(ip) + "，服务器不可达（宕机/网络故障），请及时排查！")
                is_reachable = False
            time.sleep(1)
        return is_reachable
    except:
        print("reachable_check error!")


# ssh 登录IP是否授权检查


def ssh_login_ip_check():
    try:
        global ssh_white_ip_list
        print("ssh logined ip check:\n")
        hostname = sp.getoutput("hostname")
        # 获取已登录用户IP地址列表
        out = sp.getoutput("who |grep -v tmux |awk '{print $5}'")
        out = out.replace("(", "").replace(")", "")
        login_ip_list = out.split("\n")
        # 去除重复
        login_ip_list = set(login_ip_list)
        login_ip_list = list(login_ip_list)
        # 把ssh登录授权IP地址格式化成列表
        ssh_white_ip_list = ssh_white_ip_list.split("|")
        # 检测已登录IP是否授权
        for ip in login_ip_list:
            if ip != "" and ip not in ssh_white_ip_list:
                curtime = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(time.time())
                )
                msg = "{0},未授权IP:{1},已登录服务器{2}".format(curtime, ip, hostname)
                server_post(machine_name, hostname + msg)
        print("--------ssh logined ip check finished -------------")
    except Exception as e:
        print(str(e))


# 扇区证明出错检查


def sectors_fault_check():
    global sector_faults_num
    sectors_fault_cmd = "lotus-miner proving faults|wc -l"
    out = sp.getoutput(sectors_fault_cmd)
    print("sectors_fault_check:")
    print(out)
    sectors_count = int(out) - 2
    if sectors_count > 0:
        if sectors_count > sector_faults_num:
            sector_faults_num = sectors_count
            server_post(
                machine_name,
                "{0}节点出错{1}个扇区".format(fil_account, sectors_count) + "，请及时处理",
            )
        return False
    if sectors_count == 0:
        sector_faults_num = 0
    return True


# 阵列卡故障盘检测


def raid_offline_check():
    out = sp.getoutput("sudo  MegaCli64 -PDList -aALL|grep -c 'Firmware state'")
    print("raid_offline_check:")
    print(out)
    if is_number(out):
        if int(out) < raid_disk_num:
            print("false")
            server_post(machine_name, "阵列卡磁盘出现丢失，请及时处理！")
            return False
    return True


# 阵列卡预警盘检测


def raid_critical_check():
    out = sp.getoutput(
        "sudo MegaCli64 -AdpAllInfo -aALL | grep 'Critical Disks' | awk '{print $4}'"
    )
    print("raid_critical_check:")
    print(out)
    if is_number(out):
        if int(out) > 0:
            print("false")
            server_post(machine_name, "阵列卡出现预警盘，请注意！")
            return False
    return True


# 阵列卡磁盘坏道检测


def raid_error_check():
    out = sp.getoutput("sudo MegaCli64 -PDList -aALL|grep Error|awk '{print $4}'")
    print("raid_error_check:")
    res = str(out).split()
    # print(out)
    print(str(res))
    for array in res:
        if int(array) > 10:
            server_post(machine_name, "磁盘出现坏道，请注意！")
            return False
    return True


# 阵列卡磁盘故障/bad检测


def raid_failed_check():
    out = sp.getoutput("sudo  MegaCli64 -PDList -aALL|grep  state|grep -E 'Failed|bad'")
    print("raid_failed_check:")
    print(out)
    if not out.strip():
        print("true")
        return True
    server_post("阵列卡出现故障盘，请及时处理！")
    return False


# 检查公网服务器是否可达


def net_check(check_type=""):
    global net_ip
    is_ip_reach = True
    ips = net_ip.split("|")
    for str in ips:
        out = sp.getoutput("timeout 5s nc -zv " + str)
        print("net_check:")
        print(out)
        if out.strip() and out.find("succeeded") >= 0:
            print("true")
            continue
        print("false")
        server_post(machine_name, str + "不可达，请及时排查！")
        is_ip_reach = False
        time.sleep(1)
    return is_ip_reach


# 每日简报汇集


def daily_collection():
    global collection_ip
    global alert_log_path
    res_string = ""
    check_status = True
    ips = collection_ip.split("|")
    now = time.time()
    time_flow = abs(int(now) - int(today_anytime_tsp(int(daily_summary_time))))
    if int(time_flow) <= (int(check_interval) / 2):
        for ip in ips:
            out = sp.getoutput(
                "timeout 30s ssh  "
                + ip
                + " cat "
                + alert_log_path
                + " | grep -a -A 1 Check | sed '$!d'"
            )
            if is_valid_date(out):
                timestamp = int(time.mktime(time.strptime(out, "%a %b %d %H:%M:%S %Y")))
                if (int(now) - timestamp) > int(check_interval + 300):
                    res_string = res_string + ip + "、"
                    check_status = False
            else:
                check_status = False
                res_string = res_string + ip + "、"
        if check_status:
            res_string = "告警脚本正常运行。"
        else:
            res_string = res_string + "机器告警脚本无法获取或可能出现故障，请及时查看。"
        if sectors_fault_check():
            res_string = res_string + "今日节点无扇区出错。"
        else:
            res_string = res_string + "今日节点有扇区出错，请及时处理。"
        res_string = res_string + "今日节点爆了" + mined_block_check(86400) + "个块，大吉大利!"
        server_post("每日简报", res_string)


def loop():
    global sector_faults_num
    sector_faults_num = 0
    while True:
        try:
            start_time = time.time()
            global check_machine
            global fil_account
            if not check_machine.strip():
                print("请填写巡检的机器类型！")
                break
            if reachable_check():
                print("各服务器均可达，无异常")
            if net_check():
                print("各公网均可达，无异常")
            if fm_check():
                print("目录挂载、磁盘空间充足，无异常")
            if check_machine.find("一") >= 0:
                if lotusprocess_check():
                    if chain_check():
                        balance_check()
                        if mpool_check():
                            print("Lotus已巡检完毕，无异常")
            time.sleep(3)
            if check_machine.find("二") >= 0:
                if (
                    minerprocess_check()
                    and p1_overtime_check()
                    and p2_overtime_check()
                    and c2_overtime_check()
                ):
                    print("Seal-Miner已巡检完毕，无异常")
            time.sleep(3)
            if check_machine.find("三") >= 0:
                if daily_summary:
                    daily_collection()
                else:
                    mined_block_check(int(check_interval))
                if nvidia_check() and minerprocess_check():
                    print("WiningPost-Miner已巡检完毕，无异常")
            time.sleep(3)
            if check_machine.find("四") >= 0:
                if (
                    nvidia_check()
                    and minerprocess_check()
                    and wdpost_log_check()
                    and sectors_fault_check()
                ):
                    print("WindowPost-Miner已巡检完毕，无异常")
            time.sleep(3)
            if check_machine.find("五") >= 0:
                if (
                    raid_offline_check()
                    and raid_error_check()
                    and raid_critical_check()
                    and raid_failed_check()
                ):
                    print("存储机已巡检完毕，无异常")
            print("----------Check End-----------")
            print(time.asctime(time.localtime(time.time())))
            end_time = time.time()
            sleep_time = check_interval - (end_time - start_time)
            # sleep
            print("sleep {0} seconds\n".format(check_interval))
            time.sleep(sleep_time)
        except KeyboardInterrupt:
            exit(0)
        except:
            traceback.print_exc()
            time.sleep(120)


def main():
    loop()


if __name__ == "__main__":
    # init_check()
    main()
