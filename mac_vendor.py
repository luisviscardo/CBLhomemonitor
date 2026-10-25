"""
Módulo de Identificação de Fabricantes via MAC Address (MAC Vendors API)
Conecta à API pública https://api.macvendors.com/ com cache persistente em SQLite,
fila assíncrona com controle de taxa (1 req / 1.25s) e dicionário embutido dos
principais fabricantes para resolução instantânea com zero latência.
"""
import asyncio
import logging
import re
import time
from typing import Dict, Optional, Set, Any
import httpx

logger = logging.getLogger("CBLhomemonitor.mac_vendor")

# Dicionário offline embutido com prefixos OUI dos fabricantes mais populares no Brasil e no mundo
# Garante resolução imediata sem depender de requisições de rede para a maioria dos dispositivos
COMMON_OFFLINE_VENDORS: Dict[str, str] = {
    # Câmeras, CFTV e Redes no Brasil
    "54:6C:AC": "Intelbras",
    "98:E5:5B": "Intelbras (Mibo Cam)",
    "80:85:44": "Intelbras (Mibo Cam)",
    "00:1A:3F": "Intelbras",
    "48:5B:39": "Intelbras",
    "90:F6:52": "Intelbras",
    "DC:F7:56": "Intelbras",
    "40:EE:15": "Zioncom (Multilaser)",
    "80:97:1B": "APsystems (Solar Inverter)",
    "C0:F8:53": "Tuya Smart (IoT)",
    "38:A5:C9": "Tuya Smart (IoT)",
    "24:CE:33": "Tuya Smart (IoT)",
    "58:A8:E8": "Tuya Smart (IoT)",
    "18:0B:1B": "Tuya Smart (IoT)",
    "C0:95:CF": "Tuya Smart (IoT)",
    "FC:67:1F": "Tuya Smart (IoT)",
    "BC:35:1E": "Espressif (IoT)",
    "AC:A7:04": "Espressif (IoT)",
    "18:FE:34": "Espressif (IoT)",
    "24:0A:C4": "Espressif (IoT)",
    "24:62:AB": "Espressif (IoT)",
    "24:6F:28": "Espressif (IoT)",
    "2C:F4:32": "Espressif (IoT)",
    "30:AE:A4": "Espressif (IoT)",
    "3C:61:05": "Espressif (IoT)",
    "3C:71:BF": "Espressif (IoT)",
    "48:3F:DA": "Espressif (IoT)",
    "48:55:19": "Espressif (IoT)",
    "68:C6:3A": "Espressif (IoT)",
    "84:0D:8E": "Espressif (IoT)",
    "A0:20:A6": "Espressif (IoT)",
    "C4:4F:33": "Espressif (IoT)",
    "DC:4F:22": "Espressif (IoT)",
    "EC:FA:BC": "Espressif (IoT)",

    # Robôs aspiradores e smart home
    "20:67:E0": "Sweeper (Robô Aspirador)",
    "C8:5C:CC": "Xiaomi (Smart Device)",
    "64:09:80": "Xiaomi",
    "74:51:BA": "Xiaomi",
    "7C:49:EB": "Xiaomi",
    "F8:A4:5F": "Xiaomi",

    # Ar Condicionado, Linha Branca e Samsung
    "68:3A:48": "Samsung (Ar-Condicionado)",
    "00:07:AB": "Samsung",
    "00:12:47": "Samsung",
    "18:3A:2D": "Samsung",
    "24:4B:81": "Samsung",
    "48:44:F7": "Samsung",
    "88:36:5F": "Samsung",
    "AC:5F:3E": "Samsung",
    "BC:44:86": "Samsung",

    # Apple
    "00:17:F2": "Apple",
    "00:1E:C2": "Apple",
    "00:26:BB": "Apple",
    "3C:15:C2": "Apple",
    "A4:83:E7": "Apple",
    "AC:BC:32": "Apple",
    "B0:34:95": "Apple",
    "BC:54:51": "Apple",
    "DC:A9:04": "Apple",
    "F0:18:98": "Apple",

    # Roteadores e Redes (MikroTik, TP-Link, Ubiquiti, etc.)
    "00:0C:42": "MikroTik",
    "08:55:31": "MikroTik",
    "18:FD:74": "MikroTik",
    "2C:C8:1B": "MikroTik",
    "48:8F:5A": "MikroTik",
    "64:D1:54": "MikroTik",
    "6C:3B:6B": "MikroTik",
    "74:4D:28": "MikroTik",
    "B8:69:F4": "MikroTik",
    "C4:AD:34": "MikroTik",
    "CC:2D:E0": "MikroTik",
    "D4:01:C3": "MikroTik",
    "E4:8D:8C": "MikroTik",
    "F4:1E:26": "MikroTik",
    "00:14:78": "TP-Link",
    "50:C7:BF": "TP-Link",
    "74:DA:88": "TP-Link",
    "B0:4E:26": "TP-Link",
    "C0:06:C3": "TP-Link",
    "E8:48:B8": "TP-Link",
    "F4:F2:6D": "TP-Link",
    "00:27:22": "Ubiquiti",
    "24:A4:3C": "Ubiquiti",
    "78:8A:20": "Ubiquiti",
    "B4:FB:E4": "Ubiquiti",
    "DC:9F:DB": "Ubiquiti",

    # Amazon (Echo, Alexa, Fire TV)
    "00:FC:8B": "Amazon (Echo/Alexa)",
    "0C:47:C9": "Amazon (Echo/Alexa)",
    "18:74:2E": "Amazon (Fire TV)",
    "38:F7:3D": "Amazon (Echo/Alexa)",
    "40:B4:CD": "Amazon (Echo/Alexa)",
    "44:65:0D": "Amazon (Echo/Alexa)",
    "50:F5:DA": "Amazon (Echo/Alexa)",
    "68:37:E9": "Amazon (Echo/Alexa)",
    "68:54:5A": "Amazon (Echo/Alexa)",
    "74:C2:46": "Amazon (Echo/Alexa)",
    "AC:63:BE": "Amazon (Echo/Alexa)",
    "B4:7C:9C": "Amazon (Echo/Alexa)",
    "CC:9E:A2": "Amazon (Echo/Alexa)",
    "F0:F0:A4": "Amazon (Echo/Alexa)",
    "FC:A1:83": "Amazon (Echo/Alexa)",

    # Google / Chromecast
    "00:1A:11": "Google",
    "3C:5A:B4": "Google (Nest/Home)",
    "48:D6:D5": "Google (Chromecast)",
    "54:60:09": "Google (Chromecast)",
    "6C:AD:F8": "Google (Chromecast)",
    "94:EB:CD": "Google (Chromecast)",
    "A4:77:33": "Google (Nest/Home)",
    "D8:6C:63": "Google (Nest/Home)",
    "E4:F0:42": "Google (Chromecast)",
    "F8:8F:CA": "Google (Nest/Home)",

    # Consoles e TVs
    "00:04:1F": "Sony Interactive (PlayStation)",
    "00:13:15": "Sony Interactive (PlayStation)",
    "00:1D:BA": "Sony Interactive (PlayStation)",
    "00:24:8D": "Sony Interactive (PlayStation)",
    "70:9E:29": "Sony Interactive (PlayStation)",
    "B8:86:87": "Sony Interactive (PlayStation)",
    "FC:0F:E6": "Sony Interactive (PlayStation)",
    "00:09:BF": "Nintendo",
    "00:1F:32": "Nintendo (Switch)",
    "34:AF:2C": "Nintendo (Switch)",
    "7C:BB:8A": "Nintendo (Switch)",
    "98:B6:E9": "Nintendo (Switch)",
    "00:0D:3A": "Microsoft (Xbox/Surface)",
    "28:18:78": "Microsoft (Xbox)",
    "48:51:B7": "Microsoft (Xbox)",
    "58:82:A8": "Microsoft (Xbox)",
    "7C:ED:8D": "Microsoft (Xbox)",
    "98:5F:D3": "Microsoft (Xbox)",
    "00:05:CD": "Denon / Marantz",
    "00:09:B0": "Onkyo",
    "00:0E:58": "Sonos"
}

def normalize_mac(mac: str) -> str:
    """Normaliza o endereço MAC para o formato padrão XX:XX:XX:XX:XX:XX."""
    if not mac:
        return ""
    clean = re.sub(r"[^0-9A-Fa-f]", "", mac).upper()
    if len(clean) == 12:
        return ":".join(clean[i:i+2] for i in range(0, 12, 2))
    return mac.upper().replace("-", ":").strip()

def get_mac_prefix(mac: str) -> str:
    """Retorna os 3 primeiros octetos (OUI) do MAC em maiúsculas (ex: 54:6C:AC)."""
    norm = normalize_mac(mac)
    parts = norm.split(":")
    if len(parts) >= 3:
        return ":".join(parts[:3])
    return norm[:8]

def is_randomized_mac(mac: str) -> bool:
    """
    Verifica se o endereço MAC utiliza endereço local privado / aleatório
    (Locally Administered Address - bit 1 do primeiro byte é 1).
    Dispositivos modernos (iOS Private Wi-Fi, Android MAC Randomization, Windows)
    geram esses MACs dinamicamente, de modo que consultas OUI retornam 404.
    """
    norm = normalize_mac(mac)
    parts = norm.split(":")
    if not parts or not parts[0]:
        return False
    try:
        first_byte = int(parts[0], 16)
        return bool(first_byte & 2)
    except Exception:
        return False

def clean_vendor_name(raw: str) -> str:
    """
    Limpa o nome retornado pela API para remover sufixos corporativos extensos
    (ex: 'Apple, Inc.' -> 'Apple', 'Intelbras S/A' -> 'Intelbras').
    """
    if not raw:
        return ""
    name = raw.strip()
    
    # Tratamentos específicos conhecidos
    lower = name.lower()
    if "intelbras" in lower:
        return "Intelbras"
    if "altenergy" in lower or "apsystems" in lower:
        return "APsystems (Solar Inverter)"
    if "tuya" in lower:
        return "Tuya Smart (IoT)"
    if "espressif" in lower:
        return "Espressif (IoT)"
    if "zioncom" in lower:
        return "Zioncom (Multilaser)"
    if "samsung" in lower:
        return "Samsung"
    if "apple" in lower:
        return "Apple"
    if "xiaomi" in lower:
        return "Xiaomi"
    if "motorola" in lower:
        return "Motorola"
    if "mikrotik" in lower:
        return "MikroTik"
    if "tp-link" in lower:
        return "TP-Link"
    if "ubiquiti" in lower:
        return "Ubiquiti"
    if "sony" in lower:
        return "Sony"
    if "microsoft" in lower:
        return "Microsoft"
    if "nintendo" in lower:
        return "Nintendo"
    if "giga-byte" in lower or "gigabyte" in lower:
        return "Gigabyte (PC)"
    if "asus" in lower or "asustek" in lower:
        return "ASUS"
    if "dell" in lower:
        return "Dell"
    if "hewlett" in lower or lower.startswith("hp "):
        return "HP"
    if "lenovo" in lower:
        return "Lenovo"
    if "lg electronics" in lower:
        return "LG"

    # Limpeza genérica de sufixos empresariais
    regexes = [
        r",?\s*(?:inc\.?|llc\.?|ltd\.?|co\.,?\s*ltd\.?|corp\.?|corporation|gmbh|s/?a|s\.a\.|eireli|ltda)\.?$",
        r"\(.*\)$"
    ]
    for r in regexes:
        name = re.sub(r, "", name, flags=re.IGNORECASE).strip()

    return name or raw.strip()

class MacVendorResolver:
    """
    Gerenciador assíncrono de identificação de MAC Vendors.
    Integra-se com https://api.macvendors.com/ respeitando estritamente
    a taxa de 1 req / 1.25s e persistindo todo resultado no banco SQLite.
    """
    API_URL = "https://api.macvendors.com"

    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._pending: Set[str] = set()
        self._last_req_time: float = 0.0
        self._worker_task: Optional[asyncio.Task] = None
        self._initialized = False

    def init_cache(self):
        """Carrega cache pré-existente do banco de dados e do dicionário offline."""
        if self._initialized:
            return
        # 1. Carregar dicionário embutido
        for prefix, vendor in COMMON_OFFLINE_VENDORS.items():
            self._cache[prefix] = vendor

        # 2. Carregar registros persistidos no SQLite
        try:
            from database import get_all_cached_vendors
            db_vendors = get_all_cached_vendors()
            for prefix, vendor in db_vendors.items():
                if vendor:
                    self._cache[prefix] = vendor
            logger.info(f"MAC Vendor Cache inicializado com {len(self._cache)} fabricantes conhecidos.")
        except Exception as e:
            logger.warning(f"Aviso ao carregar cache de MAC Vendors do banco: {e}")

        self._initialized = True

    def start_worker(self):
        """Inicia o worker assíncrono em segundo plano se ainda não estiver rodando."""
        self.init_cache()
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())
            logger.info("Worker de resolução de MAC Vendors via macvendors.com iniciado.")

    async def _worker_loop(self):
        """Loop que consome a fila com limitação de taxa (1 req a cada 1.25s) e consulta a API."""
        headers = {
            "User-Agent": "CBLhomemonitor/1.2 (MikroTik Home Monitor)",
            "Accept": "*/*"
        }
        async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
            while True:
                mac = await self._queue.get()
                prefix = get_mac_prefix(mac)

                if prefix in self._cache and self._cache[prefix]:
                    self._pending.discard(prefix)
                    self._queue.task_done()
                    continue

                # Garantir intervalo mínimo de 1.25s entre requisições para evitar HTTP 429
                elapsed = time.time() - self._last_req_time
                if elapsed < 1.25:
                    await asyncio.sleep(1.25 - elapsed)

                resolved_vendor = ""
                try:
                    # macvendors.com aceita o prefixo ou MAC completo
                    url = f"{self.API_URL}/{prefix}"
                    resp = await client.get(url)
                    self._last_req_time = time.time()

                    if resp.status_code == 200:
                        raw_text = resp.text.strip()
                        resolved_vendor = clean_vendor_name(raw_text)
                        logger.info(f"MAC {prefix} identificado com sucesso: {resolved_vendor}")
                    elif resp.status_code == 404:
                        # Fabricante não catalogado na base do macvendors
                        resolved_vendor = "Não Catalogado"
                    elif resp.status_code == 429:
                        logger.warning("Limite de requisições do macvendors.com atingido (429). Aguardando 5 segundos...")
                        await asyncio.sleep(5.0)
                        # Reenfileira para tentar novamente mais tarde
                        await self._queue.put(mac)
                        self._queue.task_done()
                        continue
                    else:
                        logger.warning(f"Resposta inesperada de macvendors.com ({resp.status_code}) para {prefix}")
                except Exception as e:
                    logger.debug(f"Erro ao consultar macvendors.com para {prefix}: {e}")

                if resolved_vendor:
                    self._cache[prefix] = resolved_vendor
                    try:
                        from database import save_cached_vendor
                        save_cached_vendor(prefix, resolved_vendor)
                    except Exception as e:
                        logger.debug(f"Erro ao persistir vendor no banco: {e}")

                self._pending.discard(prefix)
                self._queue.task_done()

    def get_vendor(self, mac: str, hostname: str = "") -> str:
        """
        Retorna o fabricante de forma imediata (cache ou offline).
        Se ainda não for conhecido, adiciona à fila de resolução em segundo plano.
        """
        self.init_cache()
        if not mac:
            return ""

        prefix = get_mac_prefix(mac)

        # 1. Se for MAC aleatório/privado, deduz pelo hostname se disponível
        if is_randomized_mac(mac):
            hn = (hostname or "").lower()
            if any(k in hn for k in ["s24", "galaxy", "samsung"]):
                return "Samsung (MAC Privado)"
            if any(k in hn for k in ["iphone", "ipad", "macbook", "apple"]):
                return "Apple (MAC Privado)"
            if any(k in hn for k in ["pixel"]):
                return "Google Pixel (MAC Privado)"
            if any(k in hn for k in ["xiaomi", "redmi"]):
                return "Xiaomi (MAC Privado)"
            return "Dispositivo Privado (Wi-Fi)"

        # 2. Verificar cache em memória
        if prefix in self._cache:
            val = self._cache[prefix]
            return "" if val == "Não Catalogado" else val

        # 3. Enfileirar para busca na API caso não esteja pendente
        if prefix not in self._pending:
            self._pending.add(prefix)
            self._queue.put_nowait(mac)

        return ""

    def infer_friendly_name(self, raw_hostname: str, vendor: str, ip: str, mac: str) -> str:
        """
        Gera um nome amigável e legível para o dispositivo na interface:
        - Se tem hostname descritivo (ex: 'S24-Ultra-de-Luis-Viscardo', 'iM5-SC-81IO'), preserva.
        - Se for genérico ('Dispositivo Sem Nome', 'wlan0', 'Dispositivo ARP', vazio) e o vendor for conhecido:
          gera um nome elegante baseado na marca e no final do IP (ex: 'Intelbras (.111)', 'Tuya Smart (.236)').
        """
        hn = (raw_hostname or "").strip()
        last_octet = ip.split(".")[-1] if ip and "." in ip else ""
        last_octet_str = f" (.{last_octet})" if last_octet else ""

        generic_names = [
            "", "dispositivo sem nome", "dispositivo arp", "dispositivo",
            "wlan0", "wlan1", "eth0", "ether1", "bridge", "lan", "unknown"
        ]

        is_generic = hn.lower() in generic_names or not hn

        if is_generic:
            if vendor and vendor not in ["Não Catalogado", "Dispositivo Privado (Wi-Fi)"]:
                return f"{vendor}{last_octet_str}"
            if vendor == "Dispositivo Privado (Wi-Fi)":
                return f"Dispositivo Wi-Fi{last_octet_str}"
            return f"Dispositivo{last_octet_str}"

        # Melhoria de nomes crípticos conhecidos
        if hn.startswith("iM") and vendor == "Intelbras":
            return f"Câmera Intelbras {hn}"
        if hn == "lwip0" and vendor:
            return f"{vendor} IoT{last_octet_str}"

        return hn

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do serviço de identificação de MAC."""
        return {
            "total_cached": len(self._cache),
            "pending_queue": self._queue.qsize(),
            "in_flight": len(self._pending)
        }

# Instância Singleton global
mac_vendor_resolver = MacVendorResolver()
