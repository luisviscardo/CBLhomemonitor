# CBLhomemonitor ⚡ - Monitor de Rede Residencial

Dashboard moderno, elegante e de alto desempenho para monitoramento em tempo real de roteadores **MikroTik RouterOS v7+**, desenvolvido em **Python (FastAPI)** e interface web com visual futurista e glassmorphic.

---

## 🌟 Principais Recursos

- **Gráficos em Tempo Real (Chart.js):** Fluxo ao vivo de Download e Upload (Mbps) com streaming contínuo via WebSockets.
- **Histórico de Telemetria de Hardware:** Gráficos temporais detalhados de Carga de CPU (%), Uso de Memória RAM (%), Temperatura (°C) e Voltagem (V) com cálculo de médias, picos e seletor de período (*1 Hora*, *6 Horas*, *24 Horas*).
- **Histórico de Consumo (Diário & Mensal):** Gráficos de barras interativos com volume total de dados transferidos (Download e Upload em Gigabytes) nos últimos 30 dias ou 12 meses, com cálculo de média e picos de tráfego.
- **Distribuição de Consumo por Dispositivo:** Gráfico Doughnut dinâmico exibindo a fatia percentual e o total em GB consumido por cada aparelho da residência.
- **Leaderboard / Ranking de Dispositivos por Consumo:** Tabela ordenada com os maiores consumidores da rede com medalhas de pódio (🥇 Ouro, 🥈 Prata, 🥉 Bronze), barras de progresso proporcionais, detalhamento de Download/Upload e filtros de período (*Hoje*, *7 Dias*, *Mês*).
- **Banco de Dados SQLite Embutido (`history.db`):** Persistência automática e eficiente de métricas diárias, mensais e por dispositivo sem dependências externas.
- **Métricas Chave de Hardware:** Uso de CPU, memória RAM livre/total, temperatura, voltagem, arquitetura e tempo de atividade (uptime).
- **Detecção de Dispositivos Conectados:** Combina concessões DHCP ativas e tabela ARP com categorização automática por tipo (PCs/Laptops, Smartphones, Smart TVs, Consoles, Dispositivos IoT, Câmeras e Servidores NAS).
- **Monitor de Portas Físicas (Interfaces):** Status de link (UP/DOWN), taxa de transmissão individual (Kbps), pacotes e erros.
- **Ferramenta de Diagnóstico Ping Integrada:** Dispare pings diretamente pelo roteador MikroTik (`/tool/ping`) para qualquer host ou dispositivo conectado na rede com estatísticas de latência RTT (mínimo, médio, máximo e perda de pacotes).
- **Feed de Logs do RouterOS:** Visualização instantânea de eventos de firewall, renovação de DHCP, alertas e logins.
- **Modo Demonstração (Demo) Nativo:** Permite testar e visualizar o painel imediatamente com dados realistas, mesmo antes de apontar para o roteador físico.
- **Painel de Configurações Interativo:** Altere IP, porta, credenciais, protocolo HTTP/HTTPS e teste a conectividade com 1 clique.

---

## 🚀 Como Iniciar

### 1. Iniciar o Painel no Windows
Você pode simplesmente dar um duplo clique no arquivo [`start.bat`](file:///C:/Users/lsaqu/.gemini/antigravity-ide/scratch/mikrotik-monitor/start.bat) ou executar no terminal PowerShell:

```powershell
cd C:\Users\lsaqu\.gemini\antigravity-ide\scratch\mikrotik-monitor
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Acesse no seu navegador: **`http://localhost:8000`**

---

## ⚙️ Configuração no MikroTik (RouterOS v7+)

O painel utiliza a **API REST nativa** do RouterOS v7. Para habilitá-la:

### Passo 1: Habilitar o Serviço Web (REST)
No terminal do seu MikroTik (via Winbox ou SSH), execute:
```routeros
/ip service enable www
```
*(Se preferir usar HTTPS seguro com certificado: `/ip service enable www-ssl`)*

### Passo 2: Criar Usuário de Leitura (Recomendado)
Para maior segurança, crie um usuário dedicado com privilégios apenas de leitura e teste:
```routeros
/user group add name=monitor-read policy=read,test,api
/user add name=homemonitor group=monitor-read password="SuaSenhaForteAqui"
```

### Passo 3: Conectar no Dashboard
1. Abra o painel em `http://localhost:8000`.
2. Clique no botão **Conexão** (canto superior direito).
3. Desative o **Modo Demonstração**.
4. Digite o IP do seu MikroTik (ex: `192.168.88.1`), usuário `homemonitor` e a senha definida.
5. Clique em **Testar Conexão** e em seguida em **Salvar Configurações**.

---

## 📁 Estrutura do Projeto

- [`app.py`](file:///C:/Users/lsaqu/.gemini/antigravity-ide/scratch/mikrotik-monitor/app.py): Servidor FastAPI com rotas REST e WebSocket para streaming em tempo real.
- [`mikrotik_client.py`](file:///C:/Users/lsaqu/.gemini/antigravity-ide/scratch/mikrotik-monitor/mikrotik_client.py): Cliente assíncrono para a REST API do RouterOS v7.
- [`mock_data.py`](file:///C:/Users/lsaqu/.gemini/antigravity-ide/scratch/mikrotik-monitor/mock_data.py): Gerador de métricas e dispositivos residenciais ultra-realistas.
- [`config.py`](file:///C:/Users/lsaqu/.gemini/antigravity-ide/scratch/mikrotik-monitor/config.py): Gerenciamento de configurações com persistência em `config.json`.
- [`templates/index.html`](file:///C:/Users/lsaqu/.gemini/antigravity-ide/scratch/mikrotik-monitor/templates/index.html): Interface web moderna e responsiva.
- [`static/css/style.css`](file:///C:/Users/lsaqu/.gemini/antigravity-ide/scratch/mikrotik-monitor/static/css/style.css): Tema glassmorphism dark cyberpunk com paleta HSL e animações.
- [`static/js/app.js`](file:///C:/Users/lsaqu/.gemini/antigravity-ide/scratch/mikrotik-monitor/static/js/app.js): Lógica de gráficos em tempo real, filtros de dispositivos e diagnóstico.
