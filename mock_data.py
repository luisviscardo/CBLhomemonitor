import time
import random
import math
from datetime import datetime, timedelta

start_time = time.time() - (14 * 86400 + 7 * 3600 + 22 * 60) # 14 dias de uptime inicial

# Dados base de dispositivos da casa
MOCK_DEVICES = [
    {
        "hostname": "Desktop-Gamer-PC",
        "address": "192.168.88.10",
        "mac-address": "E4:54:E8:A1:3B:11",
        "interface": "ether2",
        "status": "bound",
        "dynamic": "true",
        "comment": "Quarto Principal",
        "type": "pc",
        "vendor": "ASUS"
    },
    {
        "hostname": "MacBook-Pro-M3",
        "address": "192.168.88.15",
        "mac-address": "F0:18:98:B4:72:DE",
        "interface": "bridge-LAN",
        "status": "bound",
        "dynamic": "true",
        "comment": "Escritório",
        "type": "laptop",
        "vendor": "Apple"
    },
    {
        "hostname": "iPhone-15-Pro",
        "address": "192.168.88.25",
        "mac-address": "7C:04:D0:6F:1C:8A",
        "interface": "bridge-LAN",
        "status": "bound",
        "dynamic": "true",
        "comment": "Wi-Fi 5GHz",
        "type": "mobile",
        "vendor": "Apple"
    },
    {
        "hostname": "Samsung-NeoQLED-65",
        "address": "192.168.88.30",
        "mac-address": "50:85:69:A3:21:40",
        "interface": "ether3",
        "status": "bound",
        "dynamic": "false",
        "comment": "Sala de Estar",
        "type": "tv",
        "vendor": "Samsung"
    },
    {
        "hostname": "PlayStation-5",
        "address": "192.168.88.42",
        "mac-address": "00:D9:D1:4E:99:BC",
        "interface": "ether3",
        "status": "bound",
        "dynamic": "true",
        "comment": "Sala de Estar",
        "type": "game",
        "vendor": "Sony"
    },
    {
        "hostname": "Synology-NAS-DS920",
        "address": "192.168.88.100",
        "mac-address": "00:11:32:9F:8B:22",
        "interface": "ether4",
        "status": "bound",
        "dynamic": "false",
        "comment": "Servidor de Arquivos & Backups",
        "type": "nas",
        "vendor": "Synology"
    },
    {
        "hostname": "Echo-Dot-Quarto",
        "address": "192.168.88.55",
        "mac-address": "44:65:0D:33:41:F9",
        "interface": "bridge-LAN",
        "status": "bound",
        "dynamic": "true",
        "comment": "Alexa Smart Speaker",
        "type": "iot",
        "vendor": "Amazon"
    },
    {
        "hostname": "Tuya-Smart-Switch-Hub",
        "address": "192.168.88.61",
        "mac-address": "BC:DD:C2:5E:01:88",
        "interface": "bridge-LAN",
        "status": "bound",
        "dynamic": "true",
        "comment": "Iluminação Inteligente",
        "type": "iot",
        "vendor": "Tuya/Espressif"
    },
    {
        "hostname": "Camera-Seguranca-Garagem",
        "address": "192.168.88.75",
        "mac-address": "3C:52:A1:0F:2E:77",
        "interface": "bridge-LAN",
        "status": "bound",
        "dynamic": "false",
        "comment": "Câmera Wi-Fi 1080p",
        "type": "camera",
        "vendor": "Intelbras"
    }
]

# Histórico de tráfego acumulado
total_rx_bytes = 485_200_000_000  # ~485 GB
total_tx_bytes = 72_400_000_000   # ~72 GB
last_sample_time = time.time()

def get_mock_snapshot():
    global total_rx_bytes, total_tx_bytes, last_sample_time
    now = time.time()
    dt = max(1.0, now - last_sample_time)
    last_sample_time = now

    # Simular flutuação realista de largura de banda
    base_dl = 75.0 + 35.0 * math.sin(now / 15.0) + random.uniform(-10.0, 20.0) # Mbps
    base_ul = 22.0 + 12.0 * math.cos(now / 20.0) + random.uniform(-3.0, 8.0)  # Mbps
    base_dl = max(4.5, base_dl)
    base_ul = max(1.5, base_ul)

    # Converter para bits/s e bytes
    rx_bps = int(base_dl * 1_000_000)
    tx_bps = int(base_ul * 1_000_000)
    total_rx_bytes += int((rx_bps / 8) * dt)
    total_tx_bytes += int((tx_bps / 8) * dt)

    # Uptime formatado
    uptime_sec = int(now - start_time)
    days = uptime_sec // 86400
    hours = (uptime_sec % 86400) // 3600
    mins = (uptime_sec % 3600) // 60
    uptime_str = f"{days}d {hours}h {mins}m"

    # CPU e Memória
    cpu_load = max(5, min(85, int(18 + 14 * math.sin(now / 8.0) + random.randint(-4, 9))))
    total_mem = 1024 * 1024 * 1024 # 1 GB
    free_mem = int(total_mem * (0.68 + 0.05 * math.sin(now / 25.0) + random.uniform(-0.01, 0.01)))

    interfaces = [
        {
            "name": "ether1-WAN",
            "type": "ether",
            "running": "true",
            "disabled": "false",
            "comment": "Internet Fibra Óptica (Provedor)",
            "rx-byte": str(total_rx_bytes),
            "tx-byte": str(total_tx_bytes),
            "rx-packet": str(total_rx_bytes // 1100),
            "tx-packet": str(total_tx_bytes // 950),
            "rx-error": "0",
            "tx-error": "0",
            "rx-drop": "12",
            "tx-drop": "0",
            "actual-mtu": "1500",
            "link-downs": "0",
            "rate_rx_bps": rx_bps,
            "rate_tx_bps": tx_bps,
        },
        {
            "name": "ether2-PC",
            "type": "ether",
            "running": "true",
            "disabled": "false",
            "comment": "Desktop Gamer Gigabit",
            "rx-byte": str(int(total_rx_bytes * 0.45)),
            "tx-byte": str(int(total_tx_bytes * 0.50)),
            "rx-packet": "3420199",
            "tx-packet": "2198001",
            "rx-error": "0",
            "tx-error": "0",
            "actual-mtu": "1500",
            "rate_rx_bps": int(rx_bps * 0.40),
            "rate_tx_bps": int(tx_bps * 0.35),
        },
        {
            "name": "ether3-TV-Console",
            "type": "ether",
            "running": "true",
            "disabled": "false",
            "comment": "Switch Sala (TV + PS5)",
            "rx-byte": str(int(total_rx_bytes * 0.30)),
            "tx-byte": str(int(total_tx_bytes * 0.15)),
            "rx-packet": "1940212",
            "tx-packet": "1040332",
            "rx-error": "0",
            "tx-error": "0",
            "actual-mtu": "1500",
            "rate_rx_bps": int(rx_bps * 0.35),
            "rate_tx_bps": int(tx_bps * 0.10),
        },
        {
            "name": "ether4-NAS",
            "type": "ether",
            "running": "true",
            "disabled": "false",
            "comment": "Synology DiskStation",
            "rx-byte": str(int(total_rx_bytes * 0.15)),
            "tx-byte": str(int(total_tx_bytes * 0.25)),
            "rx-packet": "981240",
            "tx-packet": "1420199",
            "rx-error": "0",
            "tx-error": "0",
            "actual-mtu": "1500",
            "rate_rx_bps": int(rx_bps * 0.15),
            "rate_tx_bps": int(tx_bps * 0.45),
        },
        {
            "name": "ether5-AP-Mesh",
            "type": "ether",
            "running": "true",
            "disabled": "false",
            "comment": "Access Point Wi-Fi 6",
            "rx-byte": str(int(total_rx_bytes * 0.10)),
            "tx-byte": str(int(total_tx_bytes * 0.10)),
            "rx-packet": "841290",
            "tx-packet": "651002",
            "rx-error": "0",
            "tx-error": "0",
            "actual-mtu": "1500",
            "rate_rx_bps": int(rx_bps * 0.10),
            "rate_tx_bps": int(tx_bps * 0.10),
        },
        {
            "name": "bridge-LAN",
            "type": "bridge",
            "running": "true",
            "disabled": "false",
            "comment": "Rede Local Interna",
            "rx-byte": str(total_rx_bytes),
            "tx-byte": str(total_tx_bytes),
            "rx-packet": str(total_rx_bytes // 1100),
            "tx-packet": str(total_tx_bytes // 950),
            "actual-mtu": "1500",
            "rate_rx_bps": rx_bps,
            "rate_tx_bps": tx_bps,
        }
    ]

    # Logs de eventos
    logs = [
        {"time": datetime.now().strftime("%H:%M:%S"), "topics": "system,info", "message": "user admin logged in from 192.168.88.15 via rest"},
        {"time": (datetime.now() - timedelta(minutes=2)).strftime("%H:%M:%S"), "topics": "dhcp,info", "message": "dhcp-server assigned 192.168.88.25 to iPhone-15-Pro"},
        {"time": (datetime.now() - timedelta(minutes=8)).strftime("%H:%M:%S"), "topics": "firewall,info", "message": "drop invalid forward: in:ether1-WAN out:ether2, src 185.120.45.10"},
        {"time": (datetime.now() - timedelta(minutes=15)).strftime("%H:%M:%S"), "topics": "system,info", "message": "DNS cache flushed automatically"},
        {"time": (datetime.now() - timedelta(minutes=32)).strftime("%H:%M:%S"), "topics": "interface,info", "message": "ether2-PC link up (speed 1Gbps, full duplex)"},
        {"time": (datetime.now() - timedelta(hours=1)).strftime("%H:%M:%S"), "topics": "dhcp,info", "message": "dhcp-server renewed lease for MacBook-Pro-M3"},
        {"time": (datetime.now() - timedelta(hours=3)).strftime("%H:%M:%S"), "topics": "system,warning", "message": "high memory usage spike (cleared)"},
    ]

    return {
        "status": "connected",
        "mode": "demo",
        "system": {
            "identity": "MikroTik-Home-Core",
            "board_name": "RB5009UG+S+IN",
            "model": "RouterBOARD 5009",
            "version": "7.14.3 (stable)",
            "uptime": uptime_str,
            "cpu_load": cpu_load,
            "cpu_count": 4,
            "cpu_frequency": "1400 MHz",
            "total_memory": total_mem,
            "free_memory": free_mem,
            "memory_usage_pct": round(((total_mem - free_mem) / total_mem) * 100, 1),
            "temperature": 41.5 + random.uniform(-0.5, 1.2),
            "voltage": 24.2
        },
        "traffic": {
            "wan_interface": "ether1-WAN",
            "rx_bps": rx_bps,
            "tx_bps": tx_bps,
            "rx_mbps": round(rx_bps / 1_000_000, 2),
            "tx_mbps": round(tx_bps / 1_000_000, 2),
            "total_rx_bytes": total_rx_bytes,
            "total_tx_bytes": total_tx_bytes,
            "total_rx_gb": round(total_rx_bytes / (1024**3), 2),
            "total_tx_gb": round(total_tx_bytes / (1024**3), 2),
        },
        "wan_info": {
            "ip": "177.136.210.45",
            "gateway": "177.136.210.1",
            "dns": "1.1.1.1, 8.8.8.8",
            "ping_latency_ms": round(14.2 + random.uniform(-1.5, 3.2), 1)
        },
        "interfaces": interfaces,
        "devices": [
            {
                **dev,
                "rx_bytes": int(total_rx_bytes * [0.42, 0.26, 0.14, 0.09, 0.05, 0.03, 0.007, 0.002, 0.001][idx % 9]),
                "tx_bytes": int(total_tx_bytes * [0.46, 0.22, 0.05, 0.12, 0.08, 0.06, 0.006, 0.003, 0.001][idx % 9]),
                "total_bytes": int(total_rx_bytes * [0.42, 0.26, 0.14, 0.09, 0.05, 0.03, 0.007, 0.002, 0.001][idx % 9]) + int(total_tx_bytes * [0.46, 0.22, 0.05, 0.12, 0.08, 0.06, 0.006, 0.003, 0.001][idx % 9]),
                "current_rate_rx": int(rx_bps * [0.40, 0.25, 0.15, 0.10, 0.05, 0.03, 0.01, 0.005, 0.005][idx % 9]),
                "current_rate_tx": int(tx_bps * [0.45, 0.20, 0.05, 0.15, 0.08, 0.05, 0.01, 0.005, 0.005][idx % 9]),
                "active_conns": [42, 28, 14, 9, 6, 4, 2, 1, 1][idx % 9]
            }
            for idx, dev in enumerate(MOCK_DEVICES)
        ],
        "logs": logs
    }

def mock_ping(address: str, count: int = 4):
    """Simula o comando de ping do MikroTik"""
    base_latency = 12.0 if "8.8.8.8" in address or "1.1.1.1" in address else 22.0
    results = []
    for seq in range(count):
        rtt = round(base_latency + random.uniform(-2.0, 4.5), 2)
        results.append({
            "seq": seq + 1,
            "host": address,
            "size": 56,
            "ttl": 58,
            "time": f"{rtt}ms",
            "status": "echo reply"
        })
    avg_rtt = round(sum(float(r["time"].replace("ms", "")) for r in results) / len(results), 2)
    return {
        "host": address,
        "packets_sent": count,
        "packets_received": count,
        "packet_loss_pct": 0,
        "min_rtt": min(float(r["time"].replace("ms", "")) for r in results),
        "avg_rtt": avg_rtt,
        "max_rtt": max(float(r["time"].replace("ms", "")) for r in results),
        "results": results
    }
