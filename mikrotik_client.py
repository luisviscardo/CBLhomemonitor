import asyncio
import time
import httpx
from typing import Dict, Any, List, Optional
from config import RouterConfig
from mac_vendor import mac_vendor_resolver

class MikroTikClient:
    def __init__(self, config: RouterConfig):
        self.config = config
        self.last_interface_stats: Dict[str, Dict[str, Any]] = {}
        self.last_poll_time: float = 0.0

    @property
    def base_url(self) -> str:
        proto = "https" if self.config.use_https else "http"
        return f"{proto}://{self.config.router_ip}:{self.config.port}/rest"

    def _get_auth(self):
        return (self.config.username, self.config.password)

    async def _request(self, method: str, endpoint: str, json_data: Optional[dict] = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(
            verify=self.config.verify_ssl,
            timeout=4.0,
            auth=self._get_auth()
        ) as client:
            if method.upper() == "GET":
                resp = await client.get(url)
            elif method.upper() == "POST":
                resp = await client.post(url, json=json_data)
            else:
                raise ValueError(f"Método não suportado: {method}")

            resp.raise_for_status()
            return resp.json()

    async def test_connection(self) -> Dict[str, Any]:
        """Testa se a API REST do MikroTik responde corretamente."""
        try:
            data = await self._request("GET", "/system/resource")
            res = data[0] if isinstance(data, list) and len(data) > 0 else data
            return {
                "success": True,
                "version": res.get("version", "Desconhecido"),
                "board_name": res.get("board-name", "RouterBOARD"),
                "uptime": res.get("uptime", "0s")
            }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return {"success": False, "error": "Autenticação falhou: Usuário ou senha incorretos."}
            return {"success": False, "error": f"Erro HTTP {e.response.status_code}: {e.response.text}"}
        except httpx.ConnectError:
            return {"success": False, "error": f"Não foi possível conectar em {self.config.router_ip}:{self.config.port}. Verifique o IP e se o serviço REST (www/www-ssl) está ativo no MikroTik."}
        except httpx.TimeoutException:
            return {"success": False, "error": f"Tempo limite excedido ao tentar conectar com {self.config.router_ip}."}
        except Exception as e:
            return {"success": False, "error": f"Erro de conexão: {str(e)}"}

    async def get_system_info(self) -> Dict[str, Any]:
        resource_task = self._request("GET", "/system/resource")
        identity_task = self._request("GET", "/system/identity")
        
        resource, identity = await asyncio.gather(resource_task, identity_task, return_exceptions=True)
        
        res = resource[0] if isinstance(resource, list) and len(resource) > 0 else (resource if isinstance(resource, dict) else {})
        iden = identity[0] if isinstance(identity, list) and len(identity) > 0 else (identity if isinstance(identity, dict) else {})

        total_mem = int(res.get("total-memory", 0))
        free_mem = int(res.get("free-memory", 0))
        mem_pct = round(((total_mem - free_mem) / total_mem * 100), 1) if total_mem > 0 else 0

        cpu_load_raw = res.get("cpu-load", 0)
        try:
            cpu_load = int(cpu_load_raw)
        except (ValueError, TypeError):
            cpu_load = 0

        return {
            "identity": iden.get("name", "MikroTik"),
            "board_name": res.get("board-name", "RouterBOARD"),
            "model": res.get("board-name", "MikroTik"),
            "version": res.get("version", "RouterOS v7"),
            "uptime": res.get("uptime", "0s"),
            "cpu_load": cpu_load,
            "cpu_count": int(res.get("cpu-count", 1)),
            "cpu_frequency": f"{res.get('cpu-frequency', 0)} MHz",
            "total_memory": total_mem,
            "free_memory": free_mem,
            "memory_usage_pct": mem_pct,
            "architecture": res.get("architecture-name", "arm")
        }

    async def get_interfaces_and_traffic(self) -> Dict[str, Any]:
        raw_interfaces = await self._request("GET", "/interface")
        now = time.time()
        dt = max(0.5, now - self.last_poll_time) if self.last_poll_time > 0 else 2.0

        interfaces = []
        wan_rx_bps = 0
        wan_tx_bps = 0
        wan_total_rx = 0
        wan_total_tx = 0

        current_stats = {}

        for iface in raw_interfaces:
            name = iface.get("name", "")
            rx_bytes = int(iface.get("rx-byte", 0))
            tx_bytes = int(iface.get("tx-byte", 0))

            current_stats[name] = {"rx_byte": rx_bytes, "tx_byte": tx_bytes}

            # Calcular velocidade em bps usando delta
            rate_rx_bps = 0
            rate_tx_bps = 0
            if name in self.last_interface_stats and self.last_poll_time > 0:
                prev = self.last_interface_stats[name]
                delta_rx = max(0, rx_bytes - prev.get("rx_byte", 0))
                delta_tx = max(0, tx_bytes - prev.get("tx_byte", 0))
                rate_rx_bps = int((delta_rx * 8) / dt)
                rate_tx_bps = int((delta_tx * 8) / dt)

            iface_dict = {
                "name": name,
                "type": iface.get("type", "ether"),
                "running": iface.get("running", "false"),
                "disabled": iface.get("disabled", "false"),
                "comment": iface.get("comment", ""),
                "actual-mtu": iface.get("actual-mtu", "1500"),
                "rx-byte": str(rx_bytes),
                "tx-byte": str(tx_bytes),
                "rx-packet": str(iface.get("rx-packet", "0")),
                "tx-packet": str(iface.get("tx-packet", "0")),
                "rx-error": str(iface.get("rx-error", "0")),
                "tx-error": str(iface.get("tx-error", "0")),
                "rx-drop": str(iface.get("rx-drop", "0")),
                "rate_rx_bps": rate_rx_bps,
                "rate_tx_bps": rate_tx_bps,
            }
            interfaces.append(iface_dict)

            # Detectar ou associar interface WAN configurada
            if name == self.config.wan_interface or (not self.config.wan_interface and ("ether1" in name or "wan" in name.lower() or "pppoe" in name.lower())):
                wan_rx_bps = rate_rx_bps
                wan_tx_bps = rate_tx_bps
                wan_total_rx = rx_bytes
                wan_total_tx = tx_bytes

        self.last_interface_stats = current_stats
        self.last_poll_time = now

        traffic = {
            "wan_interface": self.config.wan_interface,
            "rx_bps": wan_rx_bps,
            "tx_bps": wan_tx_bps,
            "rx_mbps": round(wan_rx_bps / 1_000_000, 2),
            "tx_mbps": round(wan_tx_bps / 1_000_000, 2),
            "total_rx_bytes": wan_total_rx,
            "total_tx_bytes": wan_total_tx,
            "total_rx_gb": round(wan_total_rx / (1024**3), 2),
            "total_tx_gb": round(wan_total_tx / (1024**3), 2),
        }

        return {"interfaces": interfaces, "traffic": traffic}

    def _infer_device_type(self, hostname: str, vendor: str) -> str:
        hn = (hostname or "").lower()
        vd = (vendor or "").lower()
        if any(x in hn or x in vd for x in ["iphone", "galaxy", "pixel", "redmi", "xiaomi", "moto", "android", "mobile"]):
            return "mobile"
        if any(x in hn for x in ["macbook", "laptop", "notebook", "thinkpad", "dell-nb"]):
            return "laptop"
        if any(x in hn or x in vd for x in ["desktop", "pc", "gamer", "workstation"]):
            return "pc"
        if any(x in hn or x in vd for x in ["tv", "bravia", "samsung-tv", "lg-tv", "roku", "firetv", "chromecast", "apple-tv"]):
            return "tv"
        if any(x in hn or x in vd for x in ["playstation", "ps4", "ps5", "xbox", "nintendo", "switch"]):
            return "game"
        if any(x in hn or x in vd for x in ["nas", "synology", "qnap", "truenas", "server"]):
            return "nas"
        if any(x in hn or x in vd for x in ["camera", "cam", "intelbras", "dlink", "hikvision"]):
            return "camera"
        if any(x in hn or x in vd for x in ["alexa", "echo", "dot", "tuya", "sonoff", "shelly", "bulb", "lamp", "plug", "sensor", "espressif", "apsystems", "altenergy", "sweeper", "vacuum", "iot"]):
            return "iot"
        return "device"

    async def get_connected_devices(self) -> List[Dict[str, Any]]:
        leases_task = self._request("GET", "/ip/dhcp-server/lease")
        arp_task = self._request("GET", "/ip/arp")
        conns_task = self._request("GET", "/ip/firewall/connection")
        
        raw_leases, raw_arp, raw_conns = await asyncio.gather(
            leases_task, arp_task, conns_task, return_exceptions=True
        )

        devices_by_mac = {}

        # 1. Leases DHCP
        if isinstance(raw_leases, list):
            for lease in raw_leases:
                mac = lease.get("mac-address", "").upper()
                if not mac:
                    continue
                raw_hn = lease.get("host-name", "")
                addr = lease.get("address", "")
                vendor = mac_vendor_resolver.get_vendor(mac, hostname=raw_hn)
                friendly_hn = mac_vendor_resolver.infer_friendly_name(raw_hn, vendor, addr, mac)
                dev_type = self._infer_device_type(friendly_hn or raw_hn, vendor)
                devices_by_mac[mac] = {
                    "hostname": friendly_hn,
                    "raw_hostname": raw_hn,
                    "address": addr,
                    "mac-address": mac,
                    "interface": lease.get("server", "LAN"),
                    "status": lease.get("status", "bound"),
                    "dynamic": lease.get("dynamic", "true"),
                    "comment": lease.get("comment", ""),
                    "expires-after": lease.get("expires-after", ""),
                    "type": dev_type,
                    "vendor": vendor,
                    "rx_bytes": 0,
                    "tx_bytes": 0,
                    "total_bytes": 0,
                    "current_rate_rx": 0,
                    "current_rate_tx": 0,
                    "active_conns": 0
                }

        # 2. Tabela ARP
        if isinstance(raw_arp, list):
            for entry in raw_arp:
                mac = entry.get("mac-address", "").upper()
                if not mac:
                    continue
                if mac in devices_by_mac:
                    devices_by_mac[mac]["interface"] = entry.get("interface", devices_by_mac[mac]["interface"])
                    if not devices_by_mac[mac]["comment"]:
                        devices_by_mac[mac]["comment"] = entry.get("comment", "")
                else:
                    raw_hn = entry.get("comment", "")
                    addr = entry.get("address", "")
                    vendor = mac_vendor_resolver.get_vendor(mac, hostname=raw_hn)
                    friendly_hn = mac_vendor_resolver.infer_friendly_name(raw_hn, vendor, addr, mac)
                    dev_type = self._infer_device_type(friendly_hn or raw_hn, vendor)
                    devices_by_mac[mac] = {
                        "hostname": friendly_hn,
                        "raw_hostname": raw_hn,
                        "address": addr,
                        "mac-address": mac,
                        "interface": entry.get("interface", "LAN"),
                        "status": "active" if entry.get("complete") == "true" else "idle",
                        "dynamic": entry.get("dynamic", "true"),
                        "comment": entry.get("comment", ""),
                        "type": dev_type,
                        "vendor": vendor,
                        "rx_bytes": 0,
                        "tx_bytes": 0,
                        "total_bytes": 0,
                        "current_rate_rx": 0,
                        "current_rate_tx": 0,
                        "active_conns": 0
                    }

        # 3. Connection Tracking Real por IP
        ip_stats = {}
        if isinstance(raw_conns, list):
            for c in raw_conns:
                src = c.get("src-address", "")
                dst = c.get("dst-address", "")
                src_ip = src.split(":")[0] if ":" in src else src
                dst_ip = dst.split(":")[0] if ":" in dst else dst

                ip = None
                is_orig_src = False
                if src_ip.startswith("192.168.") or src_ip.startswith("10.") or src_ip.startswith("172.16."):
                    ip = src_ip
                    is_orig_src = True
                elif dst_ip.startswith("192.168.") or dst_ip.startswith("10.") or dst_ip.startswith("172.16."):
                    ip = dst_ip
                    is_orig_src = False

                if ip:
                    if ip not in ip_stats:
                        ip_stats[ip] = {
                            "rx_bytes": 0,
                            "tx_bytes": 0,
                            "rate_rx": 0,
                            "rate_tx": 0,
                            "active_conns": 0
                        }
                    orig_b = int(c.get("orig-bytes", 0)) + int(c.get("orig-fasttrack-bytes", 0))
                    repl_b = int(c.get("repl-bytes", 0)) + int(c.get("repl-fasttrack-bytes", 0))
                    orig_r = int(c.get("orig-rate", 0))
                    repl_r = int(c.get("repl-rate", 0))

                    ip_stats[ip]["active_conns"] += 1
                    if is_orig_src:
                        ip_stats[ip]["tx_bytes"] += orig_b
                        ip_stats[ip]["rx_bytes"] += repl_b
                        ip_stats[ip]["rate_tx"] += orig_r
                        ip_stats[ip]["rate_rx"] += repl_r
                    else:
                        ip_stats[ip]["rx_bytes"] += orig_b
                        ip_stats[ip]["tx_bytes"] += repl_b
                        ip_stats[ip]["rate_rx"] += orig_r
                        ip_stats[ip]["rate_tx"] += repl_r

        # 4. Acoplar métricas reais a cada dispositivo cadastrado
        for dev in devices_by_mac.values():
            ip = dev.get("address")
            if ip in ip_stats:
                st = ip_stats[ip]
                dev["rx_bytes"] = st["rx_bytes"]
                dev["tx_bytes"] = st["tx_bytes"]
                dev["total_bytes"] = st["rx_bytes"] + st["tx_bytes"]
                dev["current_rate_rx"] = st["rate_rx"]
                dev["current_rate_tx"] = st["rate_tx"]
                dev["active_conns"] = st["active_conns"]

        return list(devices_by_mac.values())

    async def get_wan_info(self) -> Dict[str, Any]:
        try:
            addresses = await self._request("GET", "/ip/address")
            wan_ip = "Desconhecido"
            for addr in addresses:
                if addr.get("interface") == self.config.wan_interface:
                    wan_ip = addr.get("address", "").split("/")[0]
                    break
                if not self.config.wan_interface and ("ether1" in addr.get("interface", "") or "wan" in addr.get("interface", "").lower()):
                    wan_ip = addr.get("address", "").split("/")[0]
                    break
        except Exception:
            wan_ip = "N/A"

        return {
            "ip": wan_ip,
            "gateway": self.config.router_ip,
            "dns": "Automático",
            "ping_latency_ms": 0
        }

    async def get_logs(self) -> List[Dict[str, Any]]:
        try:
            raw_logs = await self._request("GET", "/log")
            if isinstance(raw_logs, list):
                # Retorna os últimos 30 logs mais recentes
                logs = []
                for entry in raw_logs[-30:]:
                    logs.append({
                        "time": entry.get("time", ""),
                        "topics": entry.get("topics", "system"),
                        "message": entry.get("message", "")
                    })
                logs.reverse() # mais recentes primeiro
                return logs
            return []
        except Exception:
            return []

    async def ping(self, address: str, count: int = 4) -> Dict[str, Any]:
        try:
            payload = {"address": address, "count": count}
            data = await self._request("POST", "/tool/ping", json_data=payload)
            if isinstance(data, list) and len(data) > 0:
                results = []
                times = []
                for i, r in enumerate(data):
                    time_val = r.get("time", "0ms")
                    ms = float(time_val.replace("ms", "")) if "ms" in time_val else 0.0
                    times.append(ms)
                    results.append({
                        "seq": i + 1,
                        "host": address,
                        "size": int(r.get("size", 56)),
                        "ttl": int(r.get("ttl", 64)),
                        "time": time_val,
                        "status": r.get("status", "echo reply")
                    })
                return {
                    "host": address,
                    "packets_sent": count,
                    "packets_received": len(results),
                    "packet_loss_pct": round(((count - len(results)) / count) * 100),
                    "min_rtt": min(times) if times else 0,
                    "avg_rtt": round(sum(times) / len(times), 2) if times else 0,
                    "max_rtt": max(times) if times else 0,
                    "results": results
                }
            return {"error": "Sem resposta do comando ping"}
        except Exception as e:
            return {"error": str(e)}

    async def get_full_snapshot(self) -> Dict[str, Any]:
        """Agrega todas as informações para o dashboard"""
        sys_task = self.get_system_info()
        iface_task = self.get_interfaces_and_traffic()
        dev_task = self.get_connected_devices()
        wan_task = self.get_wan_info()
        logs_task = self.get_logs()

        sys_info, iface_data, devices, wan_info, logs = await asyncio.gather(
            sys_task, iface_task, dev_task, wan_task, logs_task
        )

        return {
            "status": "connected",
            "mode": "live",
            "system": sys_info,
            "traffic": iface_data["traffic"],
            "interfaces": iface_data["interfaces"],
            "devices": devices,
            "wan_info": wan_info,
            "logs": logs
        }
