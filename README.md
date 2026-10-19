<div align="center">
  <img src="static/img/logo.svg" width="96" height="96" alt="CBLhomemonitor Logo" />
  <h1>CBLhomemonitor ⚡</h1>
  <p><strong>Monitor de Rede Residencial de Alta Performance para MikroTik RouterOS v7+</strong></p>
</div>

---

## 🌟 Principais Recursos

- **Gráficos de Tráfego em Tempo Real (Chart.js):** Fluxo ao vivo de Download e Upload (Mbps) com streaming contínuo via WebSockets.
- **Rastreamento Real de Consumo por Dispositivo (Conntrack):** Coleta individual de bytes enviados e recebidos por cada aparelho via tabela de Connection Tracking do RouterOS.
- **Leaderboard / Ranking de Dispositivos:** Tabela ordenada com medalhas (🥇 Ouro, 🥈 Prata, 🥉 Bronze), barras de progresso proporcionais e formatação adaptativa (KB, MB, GB).
- **Histórico de Uso da Internet (Diário & Mensal):** Gráficos de barras interativos com volume total de dados transferidos (Download e Upload) nos últimos 30 dias ou 12 meses.
- **Histórico de Telemetria de Hardware:** Monitoramento de Carga de CPU (%), Uso de RAM (%), Temperatura (°C) e Voltagem (V) com filtros de *1 Hora*, *6 Horas* e *24 Horas*.
- **Alertas Automatizados via Telegram:** Notificações instantâneas no seu celular para queda do link WAN e superaquecimento do roteador.
- **Detecção Inteligente de Dispositivos:** Mapeamento automático de concessões DHCP e tabela ARP com categorização por tipo (PCs, Smartphones, Smart TVs, Consoles, Dispositivos IoT e Câmeras).
- **Ferramenta de Diagnóstico Ping:** Dispare testes de latência ICMP diretamente a partir do roteador MikroTik (`/tool/ping`).
- **Banco de Dados Embutido SQLite (`history.db`):** Armazenamento local rápido e leve, sem necessidade de servidores de banco externos.
- **Design Futurista Dark Glassmorphism:** Interface visual refinada, tema escuro e responsividade para qualquer resolução.

---

## 🚀 Como Iniciar

### 1. Clonar o Repositório e Instalar Dependências

```bash
git clone https://github.com/luisviscardo/CBLhomemonitor.git
cd CBLhomemonitor
pip install fastapi uvicorn httpx pydantic
```

### 2. Iniciar o Servidor

No Windows, dê um duplo clique no arquivo [`start.bat`](file:///C:/Users/lsaqu/.gemini/antigravity-ide/scratch/mikrotik-monitor/start.bat) ou execute no terminal:

```bash
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Acesse no seu navegador: **`http://localhost:8000`**

---

## ⚙️ Configuração no MikroTik (RouterOS v7+)

O painel utiliza a **API REST nativa** do RouterOS v7.

### Passo 1: Habilitar o Serviço REST (www)
No terminal do seu MikroTik (via Winbox ou SSH):
```routeros
/ip service enable www
```
*(Se preferir usar HTTPS seguro: `/ip service enable www-ssl`)*

### Passo 2: Criar Usuário de Leitura (Recomendado)
Para maior segurança, crie um usuário dedicado com privilégios apenas de leitura e teste:
```routeros
/user group add name=monitor-read policy=read,test,api
/user add name=homemonitor group=monitor-read password="SuaSenhaForteAqui"
```

### Passo 3: Conectar no Dashboard
1. Abra o painel em `http://localhost:8000`.
2. Clique no botão **Conexão** (canto superior direito).
3. Preencha o IP do seu MikroTik (ex: `192.168.88.1`), porta `80`, usuário e senha.
4. Clique em **Testar Conexão** e em seguida em **Salvar Configurações**.

---

## 📁 Estrutura do Projeto

- [`app.py`](file:///C:/Users/lsaqu/.gemini/antigravity-ide/scratch/mikrotik-monitor/app.py): Backend FastAPI com rotas REST e WebSockets.
- [`mikrotik_client.py`](file:///C:/Users/lsaqu/.gemini/antigravity-ide/scratch/mikrotik-monitor/mikrotik_client.py): Integração assíncrona com a REST API e Connection Tracking do RouterOS.
- [`database.py`](file:///C:/Users/lsaqu/.gemini/antigravity-ide/scratch/mikrotik-monitor/database.py): Camada SQLite com tabelas diárias, mensais, de dispositivos e telemetria de hardware.
- [`telegram_notifier.py`](file:///C:/Users/lsaqu/.gemini/antigravity-ide/scratch/mikrotik-monitor/telegram_notifier.py): Gestor de alertas automáticos via Telegram Bot.
- [`mock_data.py`](file:///C:/Users/lsaqu/.gemini/antigravity-ide/scratch/mikrotik-monitor/mock_data.py): Dados simulados para o Modo Demonstração.
- [`templates/index.html`](file:///C:/Users/lsaqu/.gemini/antigravity-ide/scratch/mikrotik-monitor/templates/index.html): Interface web completa.
- [`static/css/style.css`](file:///C:/Users/lsaqu/.gemini/antigravity-ide/scratch/mikrotik-monitor/static/css/style.css): Estilos CSS Dark Glassmorphism e regras responsivas.
- [`static/js/app.js`](file:///C:/Users/lsaqu/.gemini/antigravity-ide/scratch/mikrotik-monitor/static/js/app.js): Gerenciamento do WebSocket, gráficos Chart.js e filtros.
- [`static/img/logo.svg`](file:///C:/Users/lsaqu/.gemini/antigravity-ide/scratch/mikrotik-monitor/static/img/logo.svg): Logotipo oficial em vetor SVG.
