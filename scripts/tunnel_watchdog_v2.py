#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""固定子域看门狗：保证 https://citybike-dash.loca.lt 始终在线，地址永不改变。
- 每 20s 探活；隧道进程崩溃/子域冷却则自动重抢 citybike-dash（冷却期等待 60s 再抢）。
- Windows 兼容：用 shell=True 调 npx（cmd 才能解析 npx.cmd），用 PowerShell 按命令行清理旧进程。
"""
import subprocess, time, urllib.request

PORT = 8097
SUB = 'citybike-dash'
TUNNEL_URL = 'https://citybike-dash.loca.lt/'
NPM_CMD = 'npx -y localtunnel --port %d --subdomain %s' % (PORT, SUB)

def alive():
    try:
        urllib.request.urlopen(TUNNEL_URL, timeout=10)
        return True
    except Exception:
        return False

def kill_all():
    # Windows: PowerShell 按命令行匹配杀 localtunnel 相关进程（pkill 在 Windows 不可用）
    try:
        ps = ("Get-CimInstance Win32_Process -Filter \"CommandLine like '%localtunnel%'\" "
              "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
        subprocess.run(['powershell', '-NoProfile', '-Command', ps],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
    except Exception:
        pass
    time.sleep(2)

def start_once():
    # shell=True 让 cmd.exe 解析 npx（Windows 下 npx 是 npx.cmd，需经 PATH 查找）
    return subprocess.Popen(NPM_CMD, shell=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def ensure_up():
    """启动 localtunnel 直到探活成功（处理子域冷却）。"""
    while True:
        p = start_once()
        for _ in range(15):  # 最多等 ~30s
            time.sleep(2)
            if alive():
                return p
        try:
            p.terminate()
        except Exception:
            pass
        time.sleep(60)  # 子域冷却期，等后再抢

if __name__ == '__main__':
    print('[watchdog] 启动，守护', TUNNEL_URL)
    while True:
        try:
            if not alive():
                print('[watchdog] 隧道掉线，重抢固定子域', SUB, '...')
                kill_all()
                ensure_up()
                print('[watchdog] 隧道已恢复')
        except Exception as e:
            print('[watchdog] 异常:', e)
        time.sleep(20)
