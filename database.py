import sqlite3
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List

DB_PATH = Path(__file__).parent / "history.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Tabela de consumo diário total
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_traffic (
                date TEXT PRIMARY KEY,
                rx_bytes INTEGER DEFAULT 0,
                tx_bytes INTEGER DEFAULT 0,
                total_bytes INTEGER DEFAULT 0
            )
        """)

        # Tabela de consumo mensal total
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS monthly_traffic (
                month TEXT PRIMARY KEY,
                rx_bytes INTEGER DEFAULT 0,
                tx_bytes INTEGER DEFAULT 0,
                total_bytes INTEGER DEFAULT 0
            )
        """)

        # Tabela de consumo por dispositivo por dia
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS device_traffic (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                mac_address TEXT,
                ip_address TEXT,
                hostname TEXT,
                device_type TEXT,
                rx_bytes INTEGER DEFAULT 0,
                tx_bytes INTEGER DEFAULT 0,
                total_bytes INTEGER DEFAULT 0,
                UNIQUE(date, mac_address)
            )
        """)

        # Tabela de telemetria histórica de hardware (CPU, RAM, Temp, Voltagem)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hardware_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                cpu_load REAL,
                memory_usage_pct REAL,
                free_memory_mb REAL,
                temperature REAL,
                voltage REAL
            )
        """)
        conn.commit()

def clear_all_history():
    """Limpa todo o histórico anterior e inicia o registro limpo a partir de hoje."""
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    month_str = now.strftime("%Y-%m")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM daily_traffic")
        cursor.execute("DELETE FROM monthly_traffic")
        cursor.execute("DELETE FROM device_traffic")
        cursor.execute("DELETE FROM hardware_history")

        # Iniciar hoje zerado
        cursor.execute("""
            INSERT INTO daily_traffic (date, rx_bytes, tx_bytes, total_bytes)
            VALUES (?, 0, 0, 0)
        """, (today_str,))

        # Iniciar mês atual zerado
        cursor.execute("""
            INSERT INTO monthly_traffic (month, rx_bytes, tx_bytes, total_bytes)
            VALUES (?, 0, 0, 0)
        """, (month_str,))

        conn.commit()
    print(f"Histórico completamente zerado. Iniciando novo registro a partir de hoje ({today_str}).")

def sync_device_baseline(devices: List[Dict[str, Any]]):
    """Atualiza o banco com os dados reais de tráfego medidos individualmente por dispositivo no MikroTik."""
    if not devices:
        return
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    with get_connection() as conn:
        cursor = conn.cursor()
        for d in devices:
            mac = d.get("mac-address") or d.get("mac_address", "")
            mac = mac.upper() if mac else ""
            if not mac:
                continue
            rx = int(d.get("rx_bytes", 0))
            tx = int(d.get("tx_bytes", 0))
            tot = rx + tx
            cursor.execute("""
                INSERT INTO device_traffic (date, mac_address, ip_address, hostname, device_type, rx_bytes, tx_bytes, total_bytes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, mac_address) DO UPDATE SET
                    ip_address = excluded.ip_address,
                    hostname = excluded.hostname,
                    device_type = excluded.device_type,
                    rx_bytes = excluded.rx_bytes,
                    tx_bytes = excluded.tx_bytes,
                    total_bytes = excluded.total_bytes
            """, (today_str, mac, d.get("address") or d.get("ip_address", ""), d.get("hostname", "Desconhecido"), d.get("type", "device"), rx, tx, tot))
        conn.commit()

def record_hardware_sample(cpu_load: float, memory_usage_pct: float, free_memory_mb: float, temperature: float, voltage: float):
    """Registra uma amostra de telemetria de hardware no banco de dados."""
    now = datetime.now()
    ts_str = now.strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO hardware_history (timestamp, cpu_load, memory_usage_pct, free_memory_mb, temperature, voltage)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ts_str, round(cpu_load, 1), round(memory_usage_pct, 1), round(free_memory_mb, 1), round(temperature, 1), round(voltage, 1)))
        
        # Opcional: manter no máximo os últimos 5000 registros para não crescer indefinidamente
        cursor.execute("""
            DELETE FROM hardware_history WHERE id IN (
                SELECT id FROM hardware_history ORDER BY id DESC LIMIT -1 OFFSET 5000
            )
        """)
        conn.commit()

def get_hardware_history(timeframe: str = "1h") -> Dict[str, Any]:
    """Retorna o histórico de telemetria de hardware filtrado por período (1h, 6h, 24h)."""
    now = datetime.now()
    if timeframe == "24h":
        since = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    elif timeframe == "6h":
        since = (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")
    else: # "1h"
        since = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, cpu_load, memory_usage_pct, free_memory_mb, temperature, voltage
            FROM hardware_history
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        """, (since,))
        rows = cursor.fetchall()

    labels = []
    cpu_data = []
    ram_data = []
    temp_data = []
    volt_data = []

    for r in rows:
        # Formatar timestamp para visualização (HH:MM:SS para 1h/6h, DD/MM HH:MM para 24h)
        dt = datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S")
        label = dt.strftime("%d/%m %H:%M") if timeframe == "24h" else dt.strftime("%H:%M:%S")
        labels.append(label)
        cpu_data.append(r["cpu_load"])
        ram_data.append(r["memory_usage_pct"])
        temp_data.append(r["temperature"])
        volt_data.append(r["voltage"])

    count = len(rows) or 1
    avg_cpu = round(sum(cpu_data) / count, 1) if cpu_data else 0
    peak_cpu = max(cpu_data) if cpu_data else 0
    avg_ram = round(sum(ram_data) / count, 1) if ram_data else 0
    peak_ram = max(ram_data) if ram_data else 0
    avg_temp = round(sum(temp_data) / count, 1) if temp_data else 0
    peak_temp = max(temp_data) if temp_data else 0
    avg_volt = round(sum(volt_data) / count, 1) if volt_data else 0

    return {
        "timeframe": timeframe,
        "labels": labels,
        "cpu_load": cpu_data,
        "memory_pct": ram_data,
        "temperature": temp_data,
        "voltage": volt_data,
        "summary": {
            "avg_cpu": avg_cpu,
            "peak_cpu": peak_cpu,
            "avg_ram": avg_ram,
            "peak_ram": peak_ram,
            "avg_temp": avg_temp,
            "peak_temp": peak_temp,
            "avg_voltage": avg_volt
        }
    }



def record_traffic_sample(rx_delta_bytes: int, tx_delta_bytes: int, device_deltas: List[Dict[str, Any]] = None):
    """Registra incremento de tráfego do dia e atualiza o mês correspondente."""
    if rx_delta_bytes <= 0 and tx_delta_bytes <= 0:
        return

    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    month_str = now.strftime("%Y-%m")

    with get_connection() as conn:
        cursor = conn.cursor()

        # Atualizar diário
        cursor.execute("""
            INSERT INTO daily_traffic (date, rx_bytes, tx_bytes, total_bytes)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                rx_bytes = rx_bytes + excluded.rx_bytes,
                tx_bytes = tx_bytes + excluded.tx_bytes,
                total_bytes = total_bytes + excluded.total_bytes
        """, (today_str, rx_delta_bytes, tx_delta_bytes, rx_delta_bytes + tx_delta_bytes))

        # Atualizar mensal
        cursor.execute("""
            INSERT INTO monthly_traffic (month, rx_bytes, tx_bytes, total_bytes)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(month) DO UPDATE SET
                rx_bytes = rx_bytes + excluded.rx_bytes,
                tx_bytes = tx_bytes + excluded.tx_bytes,
                total_bytes = total_bytes + excluded.total_bytes
        """, (month_str, rx_delta_bytes, tx_delta_bytes, rx_delta_bytes + tx_delta_bytes))

        # Atualizar dispositivos
        if device_deltas:
            for d in device_deltas:
                mac = d.get("mac_address", "").upper()
                if not mac:
                    continue
                dev_rx = d.get("rx_bytes", 0)
                dev_tx = d.get("tx_bytes", 0)
                dev_tot = dev_rx + dev_tx
                cursor.execute("""
                    INSERT INTO device_traffic (date, mac_address, ip_address, hostname, device_type, rx_bytes, tx_bytes, total_bytes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(date, mac_address) DO UPDATE SET
                        ip_address = excluded.ip_address,
                        hostname = excluded.hostname,
                        device_type = excluded.device_type,
                        rx_bytes = rx_bytes + excluded.rx_bytes,
                        tx_bytes = tx_bytes + excluded.tx_bytes,
                        total_bytes = total_bytes + excluded.total_bytes
                """, (today_str, mac, d.get("ip_address", ""), d.get("hostname", "Desconhecido"), d.get("device_type", "device"), dev_rx, dev_tx, dev_tot))

        conn.commit()

def get_daily_history(days: int = 30) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, rx_bytes, tx_bytes, total_bytes
            FROM daily_traffic
            ORDER BY date DESC
            LIMIT ?
        """, (days,))
        rows = cursor.fetchall()

    rows = list(reversed(rows)) # Ordem cronológica crescente

    labels = []
    rx_gb = []
    tx_gb = []
    total_gb = []

    sum_rx = 0
    sum_tx = 0
    peak_val = 0
    peak_date = "--"

    for r in rows:
        d_obj = datetime.strptime(r["date"], "%Y-%m-%d")
        labels.append(d_obj.strftime("%d/%m"))
        
        rx_val = round(r["rx_bytes"] / (1024**3), 2)
        tx_val = round(r["tx_bytes"] / (1024**3), 2)
        tot_val = round(r["total_bytes"] / (1024**3), 2)

        rx_gb.append(rx_val)
        tx_gb.append(tx_val)
        total_gb.append(tot_val)

        sum_rx += r["rx_bytes"]
        sum_tx += r["tx_bytes"]

        if tot_val > peak_val:
            peak_val = tot_val
            peak_date = d_obj.strftime("%d/%m")

    count = len(rows) or 1
    total_consumed_gb = round((sum_rx + sum_tx) / (1024**3), 2)
    daily_avg_gb = round(total_consumed_gb / count, 2)

    return {
        "labels": labels,
        "download_gb": rx_gb,
        "upload_gb": tx_gb,
        "total_gb": total_gb,
        "summary": {
            "period": f"Últimos {len(rows)} dias",
            "total_gb": total_consumed_gb,
            "total_rx_gb": round(sum_rx / (1024**3), 2),
            "total_tx_gb": round(sum_tx / (1024**3), 2),
            "daily_avg_gb": daily_avg_gb,
            "peak_day": peak_date,
            "peak_gb": peak_val
        }
    }

def get_monthly_history(months: int = 12) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT month, rx_bytes, tx_bytes, total_bytes
            FROM monthly_traffic
            ORDER BY month DESC
            LIMIT ?
        """, (months,))
        rows = cursor.fetchall()

    rows = list(reversed(rows))

    month_names_pt = {
        "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
        "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
        "09": "Set", "10": "Out", "11": "Nov", "12": "Dez"
    }

    labels = []
    rx_gb = []
    tx_gb = []
    total_gb = []

    sum_rx = 0
    sum_tx = 0
    peak_val = 0
    peak_month = "--"

    for r in rows:
        parts = r["month"].split("-")
        m_name = f"{month_names_pt.get(parts[1], parts[1])}/{parts[0][2:]}" if len(parts) == 2 else r["month"]
        labels.append(m_name)

        rx_val = round(r["rx_bytes"] / (1024**3), 2)
        tx_val = round(r["tx_bytes"] / (1024**3), 2)
        tot_val = round(r["total_bytes"] / (1024**3), 2)

        rx_gb.append(rx_val)
        tx_gb.append(tx_val)
        total_gb.append(tot_val)

        sum_rx += r["rx_bytes"]
        sum_tx += r["tx_bytes"]

        if tot_val > peak_val:
            peak_val = tot_val
            peak_month = m_name

    total_consumed_gb = round((sum_rx + sum_tx) / (1024**3), 2)
    count = len(rows) or 1
    monthly_avg_gb = round(total_consumed_gb / count, 2)

    return {
        "labels": labels,
        "download_gb": rx_gb,
        "upload_gb": tx_gb,
        "total_gb": total_gb,
        "summary": {
            "period": f"Últimos {len(rows)} meses",
            "total_gb": total_consumed_gb,
            "total_rx_gb": round(sum_rx / (1024**3), 2),
            "total_tx_gb": round(sum_tx / (1024**3), 2),
            "monthly_avg_gb": monthly_avg_gb,
            "peak_month": peak_month,
            "peak_gb": peak_val
        }
    }

def get_device_consumption_ranking(period: str = "month") -> Dict[str, Any]:
    """Retorna o ranking de consumo por dispositivo e dados para gráfico (pizza/donut/barras)."""
    now = datetime.now()
    if period == "today":
        date_filter = now.strftime("%Y-%m-%d")
        query = """
            SELECT mac_address, ip_address, hostname, device_type,
                   SUM(rx_bytes) as total_rx,
                   SUM(tx_bytes) as total_tx,
                   SUM(total_bytes) as total_consumed
            FROM device_traffic
            WHERE date = ?
            GROUP BY mac_address
            ORDER BY total_consumed DESC
        """
        params = (date_filter,)
    elif period == "7days":
        date_filter = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        query = """
            SELECT mac_address, ip_address, hostname, device_type,
                   SUM(rx_bytes) as total_rx,
                   SUM(tx_bytes) as total_tx,
                   SUM(total_bytes) as total_consumed
            FROM device_traffic
            WHERE date >= ?
            GROUP BY mac_address
            ORDER BY total_consumed DESC
        """
        params = (date_filter,)
    else: # "month" ou padrão 30 dias
        date_filter = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        query = """
            SELECT mac_address, ip_address, hostname, device_type,
                   SUM(rx_bytes) as total_rx,
                   SUM(tx_bytes) as total_tx,
                   SUM(total_bytes) as total_consumed
            FROM device_traffic
            WHERE date >= ?
            GROUP BY mac_address
            ORDER BY total_consumed DESC
        """
        params = (date_filter,)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

    total_network_bytes = sum(r["total_consumed"] for r in rows) or 1
    top_devices = []

    chart_labels = []
    chart_data = []
    chart_colors = [
        "#00f0ff", # Cyan
        "#a855f7", # Violet
        "#3b82f6", # Blue
        "#10b981", # Emerald
        "#f59e0b", # Amber
        "#f43f5e", # Rose
        "#06b6d4", # Light Cyan
        "#8b5cf6", # Purple
        "#64748b"  # Slate
    ]

    for idx, r in enumerate(rows):
        tot_bytes = r["total_consumed"]
        rx_bytes = r["total_rx"]
        tx_bytes = r["total_tx"]

        tot_gb = round(tot_bytes / (1024**3), 2)
        rx_gb = round(rx_bytes / (1024**3), 2)
        tx_gb = round(tx_bytes / (1024**3), 2)
        percentage = round((tot_bytes / total_network_bytes) * 100, 1)

        # Formatação adaptativa (GB para tráfego pesado, MB/KB para tráfego leve)
        if tot_bytes >= 1024**3:
            formatted_total = f"{round(tot_bytes / (1024**3), 2)} GB"
        elif tot_bytes >= 1024**2:
            formatted_total = f"{round(tot_bytes / (1024**2), 1)} MB"
        else:
            formatted_total = f"{round(tot_bytes / 1024, 1)} KB"

        if rx_bytes >= 1024**3:
            formatted_rx = f"{round(rx_bytes / (1024**3), 2)} GB"
        elif rx_bytes >= 1024**2:
            formatted_rx = f"{round(rx_bytes / (1024**2), 1)} MB"
        else:
            formatted_rx = f"{round(rx_bytes / 1024, 1)} KB"

        if tx_bytes >= 1024**3:
            formatted_tx = f"{round(tx_bytes / (1024**3), 2)} GB"
        elif tx_bytes >= 1024**2:
            formatted_tx = f"{round(tx_bytes / (1024**2), 1)} MB"
        else:
            formatted_tx = f"{round(tx_bytes / 1024, 1)} KB"

        device_info = {
            "rank": idx + 1,
            "mac_address": r["mac_address"],
            "ip_address": r["ip_address"],
            "hostname": r["hostname"],
            "device_type": r["device_type"] or "device",
            "download_gb": rx_gb,
            "upload_gb": tx_gb,
            "total_gb": tot_gb,
            "total_bytes_raw": tot_bytes,
            "formatted_total": formatted_total,
            "formatted_rx": formatted_rx,
            "formatted_tx": formatted_tx,
            "percentage": percentage,
            "color": chart_colors[idx % len(chart_colors)]
        }
        top_devices.append(device_info)

        # Dados para o gráfico Donut (Top 6 + Outros)
        if idx < 6:
            chart_labels.append(r["hostname"] or r["ip_address"])
            chart_data.append(tot_gb if tot_gb > 0 else round(tot_bytes / (1024**2), 1))

    if len(rows) > 6:
        other_bytes = sum(r["total_consumed"] for r in rows[6:])
        chart_labels.append("Outros Dispositivos")
        chart_data.append(round(other_bytes / (1024**3), 2))

    return {
        "period": period,
        "total_network_gb": round(total_network_bytes / (1024**3), 2),
        "devices": top_devices,
        "chart": {
            "labels": chart_labels,
            "data": chart_data,
            "colors": chart_colors[:len(chart_labels)]
        }
    }
