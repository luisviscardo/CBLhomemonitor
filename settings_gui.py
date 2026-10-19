"""
Interface Gráfica Nativa de Configurações do CBLhomemonitor
Permite configurar o MikroTik RouterOS, Telegram e opções de inicialização
de forma simples, intuitiva e amigável para qualquer usuário.
"""
import sys
import json
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

from config import load_config, save_config, RouterConfig, get_app_dir, get_resource_dir
from autostart import is_autostart_enabled, set_autostart

class SettingsWindow:
    def __init__(self, parent=None, on_saved_callback=None):
        self.on_saved_callback = on_saved_callback
        self.config = load_config()

        if parent:
            self.root = tk.Toplevel(parent)
        else:
            self.root = tk.Tk()

        self.root.title("CBLhomemonitor ⚡ - Configurações")
        self.root.geometry("640x720")
        self.root.minsize(580, 650)
        self.root.configure(bg="#0b1120")

        # Ícone da janela
        ico_path = get_resource_dir() / "static" / "img" / "icon.ico"
        if not ico_path.exists():
            ico_path = get_app_dir() / "static" / "img" / "icon.ico"
        if ico_path.exists():
            try:
                self.root.iconbitmap(str(ico_path))
            except Exception:
                pass

        self._apply_dark_theme()
        self._build_ui()
        self._load_values()

    def _apply_dark_theme(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Cores do Dark Theme
        self.c_bg = "#0b1120"
        self.c_card = "#151e32"
        self.c_border = "#26354f"
        self.c_text = "#f1f5f9"
        self.c_muted = "#94a3b8"
        self.c_cyan = "#00f0ff"
        self.c_purple = "#a855f7"
        self.c_green = "#10b981"
        self.c_red = "#f43f5e"

        style.configure("TNotebook", background=self.c_bg, borderwidth=0)
        style.configure("TNotebook.Tab", background=self.c_card, foreground=self.c_muted,
                        padding=[14, 8], font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", self.c_border)],
                  foreground=[("selected", self.c_cyan)])

    def _build_ui(self):
        # CABEÇALHO
        hdr = tk.Frame(self.root, bg=self.c_card, height=64)
        hdr.pack(fill="x", padx=0, pady=0)

        hdr_content = tk.Frame(hdr, bg=self.c_card)
        hdr_content.pack(fill="x", padx=20, pady=12)

        lbl_title = tk.Label(hdr_content, text="CBLhomemonitor ⚡", font=("Segoe UI", 15, "bold"),
                             fg=self.c_cyan, bg=self.c_card)
        lbl_title.pack(side="left")

        lbl_subtitle = tk.Label(hdr_content, text="Configurações do Serviço & Roteador",
                                font=("Segoe UI", 10), fg=self.c_muted, bg=self.c_card)
        lbl_subtitle.pack(side="left", padx=10, pady=2)

        # NOTEBOOK (Abas)
        notebook_frame = tk.Frame(self.root, bg=self.c_bg)
        notebook_frame.pack(fill="both", expand=True, padx=16, pady=12)

        self.notebook = ttk.Notebook(notebook_frame)
        self.notebook.pack(fill="both", expand=True)

        self.tab_mikrotik = tk.Frame(self.notebook, bg=self.c_bg)
        self.tab_telegram = tk.Frame(self.notebook, bg=self.c_bg)
        self.tab_general = tk.Frame(self.notebook, bg=self.c_bg)

        self.notebook.add(self.tab_mikrotik, text=" 🌐 MikroTik RouterOS ")
        self.notebook.add(self.tab_telegram, text=" 🔔 Notificações Telegram ")
        self.notebook.add(self.tab_general, text=" ⚙️ Serviço & Sistema ")

        self._build_tab_mikrotik()
        self._build_tab_telegram()
        self._build_tab_general()

        # RODAPÉ DE AÇÕES
        footer = tk.Frame(self.root, bg=self.c_card)
        footer.pack(fill="x", side="bottom")

        footer_content = tk.Frame(footer, bg=self.c_card)
        footer_content.pack(fill="x", padx=16, pady=12)

        self.lbl_status_msg = tk.Label(footer_content, text="", font=("Segoe UI", 9),
                                       fg=self.c_green, bg=self.c_card)
        self.lbl_status_msg.pack(side="left", padx=4)

        btn_cancel = tk.Button(footer_content, text="Fechar", font=("Segoe UI", 9),
                               bg="#334155", fg="#ffffff", activebackground="#475569",
                               relief="flat", padx=14, pady=6, cursor="hand2",
                               command=self.root.destroy)
        btn_cancel.pack(side="right", padx=6)

        btn_save = tk.Button(footer_content, text="💾 Salvar e Aplicar", font=("Segoe UI", 10, "bold"),
                             bg="#0284c7", fg="#ffffff", activebackground="#0369a1",
                             relief="flat", padx=18, pady=6, cursor="hand2",
                             command=self._save_settings)
        btn_save.pack(side="right", padx=6)

    def _create_card(self, parent, title):
        card = tk.LabelFrame(parent, text=f" {title} ", font=("Segoe UI", 10, "bold"),
                             fg=self.c_cyan, bg=self.c_card, bd=1, relief="solid",
                             highlightbackground=self.c_border, highlightthickness=1)
        card.pack(fill="x", padx=12, pady=8)
        return card

    def _add_field(self, parent, label_text, var, show=None, width=32):
        row = tk.Frame(parent, bg=self.c_card)
        row.pack(fill="x", padx=12, pady=5)
        lbl = tk.Label(row, text=label_text, font=("Segoe UI", 9), fg=self.c_text,
                       bg=self.c_card, width=22, anchor="w")
        lbl.pack(side="left")
        entry = tk.Entry(row, textvariable=var, font=("Segoe UI", 9), bg="#0b1120",
                         fg="#ffffff", insertbackground="#ffffff", bd=1, relief="solid",
                         highlightbackground=self.c_border, show=show, width=width)
        entry.pack(side="left", padx=4, fill="x", expand=True)
        return entry

    def _build_tab_mikrotik(self):
        # Variáveis
        self.var_router_ip = tk.StringVar()
        self.var_port = tk.StringVar(value="80")
        self.var_use_https = tk.BooleanVar(value=False)
        self.var_verify_ssl = tk.BooleanVar(value=False)
        self.var_username = tk.StringVar(value="admin")
        self.var_password = tk.StringVar()
        self.var_show_pwd = tk.BooleanVar(value=False)
        self.var_wan = tk.StringVar(value="ether1")
        self.var_poll = tk.StringVar(value="2.0")
        self.var_demo = tk.BooleanVar(value=False)

        card1 = self._create_card(self.tab_mikrotik, "Conexão com o Roteador")
        self._add_field(card1, "IP / Host do MikroTik:", self.var_router_ip)
        self._add_field(card1, "Porta REST API:", self.var_port)

        row_ssl = tk.Frame(card1, bg=self.c_card)
        row_ssl.pack(fill="x", padx=12, pady=4)
        chk_https = tk.Checkbutton(row_ssl, text="Usar HTTPS (porta 443)", variable=self.var_use_https,
                                   font=("Segoe UI", 9), fg=self.c_text, bg=self.c_card,
                                   selectcolor="#0b1120", activebackground=self.c_card, activeforeground=self.c_cyan)
        chk_https.pack(side="left")

        card2 = self._create_card(self.tab_mikrotik, "Credenciais de Acesso")
        self._add_field(card2, "Usuário:", self.var_username)

        row_pwd = tk.Frame(card2, bg=self.c_card)
        row_pwd.pack(fill="x", padx=12, pady=4)
        lbl_pwd = tk.Label(row_pwd, text="Senha do MikroTik:", font=("Segoe UI", 9),
                           fg=self.c_text, bg=self.c_card, width=22, anchor="w")
        lbl_pwd.pack(side="left")
        self.entry_pwd = tk.Entry(row_pwd, textvariable=self.var_password, font=("Segoe UI", 9),
                                  bg="#0b1120", fg="#ffffff", insertbackground="#ffffff",
                                  bd=1, relief="solid", show="•")
        self.entry_pwd.pack(side="left", padx=4, fill="x", expand=True)

        chk_show = tk.Checkbutton(row_pwd, text="Exibir", variable=self.var_show_pwd,
                                  font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_card,
                                  selectcolor="#0b1120", activebackground=self.c_card,
                                  command=self._toggle_password_visibility)
        chk_show.pack(side="left", padx=4)

        card3 = self._create_card(self.tab_mikrotik, "Monitoramento & Tráfego")
        self._add_field(card3, "Interface de Internet (WAN):", self.var_wan)
        self._add_field(card3, "Intervalo de Coleta (segundos):", self.var_poll)

        row_demo = tk.Frame(card3, bg=self.c_card)
        row_demo.pack(fill="x", padx=12, pady=6)
        chk_demo = tk.Checkbutton(row_demo, text="Modo Demonstração (Simula dados se não houver MikroTik)",
                                  variable=self.var_demo, font=("Segoe UI", 9), fg=self.c_text,
                                  bg=self.c_card, selectcolor="#0b1120", activebackground=self.c_card)
        chk_demo.pack(side="left")

        # ÁREA DE TESTE
        test_frame = tk.Frame(self.tab_mikrotik, bg=self.c_bg)
        test_frame.pack(fill="x", padx=14, pady=10)

        self.btn_test = tk.Button(test_frame, text="⚡ Testar Conexão com o MikroTik",
                                  font=("Segoe UI", 9, "bold"), bg="#1e293b", fg=self.c_cyan,
                                  activebackground="#334155", relief="solid", bd=1,
                                  highlightbackground=self.c_cyan, padx=12, pady=7,
                                  cursor="hand2", command=self._test_mikrotik_connection)
        self.btn_test.pack(side="left")

        self.lbl_test_result = tk.Label(test_frame, text="", font=("Segoe UI", 9),
                                        fg=self.c_muted, bg=self.c_bg, wraplength=350, justify="left")
        self.lbl_test_result.pack(side="left", padx=12)

    def _build_tab_telegram(self):
        self.var_tg_enabled = tk.BooleanVar(value=False)
        self.var_tg_token = tk.StringVar()
        self.var_tg_chat_id = tk.StringVar()
        self.var_tg_temp = tk.StringVar(value="60.0")

        card_tg = self._create_card(self.tab_telegram, "Bot de Alertas no Celular")

        row_en = tk.Frame(card_tg, bg=self.c_card)
        row_en.pack(fill="x", padx=12, pady=6)
        chk_tg = tk.Checkbutton(row_en, text="Ativar Notificações via Telegram 24/7",
                                variable=self.var_tg_enabled, font=("Segoe UI", 9, "bold"),
                                fg=self.c_cyan, bg=self.c_card, selectcolor="#0b1120")
        chk_tg.pack(side="left")

        self._add_field(card_tg, "Bot Token:", self.var_tg_token)
        self._add_field(card_tg, "Chat ID:", self.var_tg_chat_id)
        self._add_field(card_tg, "Limite de Temperatura (°C):", self.var_tg_temp)

        info_tg = tk.Label(self.tab_telegram,
                           text="💡 O serviço monitora em segundo plano e envia alertas instantâneos quando a internet cai ou quando o roteador aquece.",
                           font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_bg,
                           wraplength=520, justify="left")
        info_tg.pack(fill="x", padx=16, pady=8)

        # Botão Teste Telegram
        test_tg_frame = tk.Frame(self.tab_telegram, bg=self.c_bg)
        test_tg_frame.pack(fill="x", padx=14, pady=8)

        self.btn_test_tg = tk.Button(test_tg_frame, text="📩 Enviar Notificação de Teste",
                                     font=("Segoe UI", 9, "bold"), bg="#1e293b", fg=self.c_purple,
                                     activebackground="#334155", relief="solid", bd=1,
                                     padx=12, pady=7, cursor="hand2",
                                     command=self._test_telegram)
        self.btn_test_tg.pack(side="left")

        self.lbl_tg_result = tk.Label(test_tg_frame, text="", font=("Segoe UI", 9),
                                      fg=self.c_muted, bg=self.c_bg)
        self.lbl_tg_result.pack(side="left", padx=12)

    def _build_tab_general(self):
        self.var_server_port = tk.StringVar(value="8000")
        self.var_autostart = tk.BooleanVar(value=is_autostart_enabled())

        card_srv = self._create_card(self.tab_general, "Servidor do Painel Web")
        self._add_field(card_srv, "Porta do Dashboard:", self.var_server_port)

        lbl_srv_info = tk.Label(card_srv, text="O painel fica acessível em http://localhost:[porta]",
                                font=("Segoe UI", 8), fg=self.c_muted, bg=self.c_card)
        lbl_srv_info.pack(fill="x", padx=12, pady=2)

        card_boot = self._create_card(self.tab_general, "Inicialização do Windows")
        row_boot = tk.Frame(card_boot, bg=self.c_card)
        row_boot.pack(fill="x", padx=12, pady=8)

        chk_boot = tk.Checkbutton(row_boot, text="Iniciar o CBLhomemonitor automaticamente ao ligar o Windows",
                                  variable=self.var_autostart, font=("Segoe UI", 9),
                                  fg=self.c_text, bg=self.c_card, selectcolor="#0b1120")
        chk_boot.pack(side="left")

        # Links e Ações Rápidas
        card_quick = self._create_card(self.tab_general, "Ações Rápidas")
        btn_open_folder = tk.Button(card_quick, text="📁 Abrir Pasta de Dados / Banco SQLite",
                                    font=("Segoe UI", 9), bg="#1e293b", fg=self.c_text,
                                    relief="solid", bd=1, padx=10, pady=5, cursor="hand2",
                                    command=lambda: webbrowser.open(str(get_app_dir())))
        btn_open_folder.pack(side="left", padx=12, pady=8)

    def _toggle_password_visibility(self):
        if self.var_show_pwd.get():
            self.entry_pwd.config(show="")
        else:
            self.entry_pwd.config(show="•")

    def _load_values(self):
        cfg = self.config
        self.var_router_ip.set(cfg.router_ip)
        self.var_port.set(str(cfg.port))
        self.var_use_https.set(cfg.use_https)
        self.var_verify_ssl.set(cfg.verify_ssl)
        self.var_username.set(cfg.username)
        self.var_password.set(cfg.password)
        self.var_wan.set(cfg.wan_interface)
        self.var_poll.set(str(cfg.poll_interval))
        self.var_demo.set(cfg.demo_mode)
        self.var_server_port.set(str(getattr(cfg, "server_port", 8000) or 8000))

        self.var_tg_enabled.set(cfg.telegram_enabled)
        self.var_tg_token.set(cfg.telegram_bot_token)
        self.var_tg_chat_id.set(cfg.telegram_chat_id)
        self.var_tg_temp.set(str(cfg.telegram_temp_threshold))
        self.var_autostart.set(is_autostart_enabled())

    def _test_mikrotik_connection(self):
        self.lbl_test_result.config(text="⏳ Conectando e testando MikroTik...", fg=self.c_cyan)
        self.btn_test.config(state="disabled")

        def worker():
            import asyncio
            from mikrotik_client import MikroTikClient
            try:
                port = int(self.var_port.get().strip())
            except ValueError:
                port = 80

            test_cfg = RouterConfig(
                router_ip=self.var_router_ip.get().strip(),
                port=port,
                use_https=self.var_use_https.get(),
                verify_ssl=self.var_verify_ssl.get(),
                username=self.var_username.get().strip(),
                password=self.var_password.get()
            )
            client = MikroTikClient(test_cfg)

            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                res = loop.run_until_complete(client.test_connection())
                loop.close()

                if res.get("success"):
                    identity = res.get("identity", "MikroTik")
                    version = res.get("version", "v7")
                    msg = f"✅ Sucesso! Conectado a {identity} ({version})"
                    fg_color = self.c_green
                else:
                    msg = f"❌ Erro: {res.get('error', 'Falha ao autenticar')}"
                    fg_color = self.c_red
            except Exception as e:
                msg = f"❌ Erro de conexão: {str(e)}"
                fg_color = self.c_red

            self.root.after(0, lambda: self._update_test_ui(msg, fg_color))

        threading.Thread(target=worker, daemon=True).start()

    def _update_test_ui(self, msg, color):
        self.lbl_test_result.config(text=msg, fg=color)
        self.btn_test.config(state="normal")

    def _test_telegram(self):
        token = self.var_tg_token.get().strip()
        chat_id = self.var_tg_chat_id.get().strip()
        if not token or not chat_id:
            messagebox.showwarning("Atenção", "Preencha o Bot Token e o Chat ID para realizar o teste.", parent=self.root)
            return

        self.lbl_tg_result.config(text="⏳ Enviando mensagem...", fg=self.c_purple)
        self.btn_test_tg.config(state="disabled")

        def worker():
            import asyncio
            from telegram_notifier import send_telegram_message
            import time

            test_msg = (
                "🚀 *CBLhomemonitor - Teste de Notificação!*\n\n"
                "Configuração do bot validada através do painel de controle do Windows.\n"
                f"⏰ _Horário: {time.strftime('%d/%m/%Y às %H:%M:%S')}_"
            )

            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                res = loop.run_until_complete(send_telegram_message(token, chat_id, test_msg))
                loop.close()

                if res.get("success"):
                    msg = "✅ Notificação enviada com sucesso!"
                    fg_color = self.c_green
                else:
                    msg = f"❌ Falha: {res.get('error', 'Verifique o Token e Chat ID')}"
                    fg_color = self.c_red
            except Exception as e:
                msg = f"❌ Erro: {str(e)}"
                fg_color = self.c_red

            self.root.after(0, lambda: self._update_tg_ui(msg, fg_color))

        threading.Thread(target=worker, daemon=True).start()

    def _update_tg_ui(self, msg, color):
        self.lbl_tg_result.config(text=msg, fg=color)
        self.btn_test_tg.config(state="normal")

    def _save_settings(self):
        try:
            port = int(self.var_port.get().strip() or "80")
            poll = float(self.var_poll.get().strip() or "2.0")
            server_port = int(self.var_server_port.get().strip() or "8000")
            temp_thresh = float(self.var_tg_temp.get().strip() or "60.0")
        except ValueError:
            messagebox.showerror("Erro de Formatação", "Verifique se as portas e números foram digitados corretamente.", parent=self.root)
            return

        updated = RouterConfig(
            router_ip=self.var_router_ip.get().strip(),
            port=port,
            use_https=self.var_use_https.get(),
            verify_ssl=self.var_verify_ssl.get(),
            username=self.var_username.get().strip(),
            password=self.var_password.get(),
            wan_interface=self.var_wan.get().strip(),
            poll_interval=max(1.0, poll),
            demo_mode=self.var_demo.get(),
            server_port=server_port,
            autostart=self.var_autostart.get(),
            telegram_enabled=self.var_tg_enabled.get(),
            telegram_bot_token=self.var_tg_token.get().strip(),
            telegram_chat_id=self.var_tg_chat_id.get().strip(),
            telegram_temp_threshold=temp_thresh
        )

        save_config(updated)
        set_autostart(self.var_autostart.get())

        self.lbl_status_msg.config(text="✅ Configurações salvas e aplicadas!")

        if self.on_saved_callback:
            try:
                self.on_saved_callback(updated)
            except Exception as e:
                print(f"Callback error: {e}")

        messagebox.showinfo("Sucesso", "Configurações salvas com sucesso!\nO serviço agora utilizará os novos parâmetros.", parent=self.root)

def show_settings_window(parent=None, on_saved_callback=None):
    win = SettingsWindow(parent=parent, on_saved_callback=on_saved_callback)
    if not parent:
        win.root.mainloop()
    return win

if __name__ == "__main__":
    show_settings_window()
