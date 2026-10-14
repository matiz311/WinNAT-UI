"""WinNAT UI - configuration-oriented Windows desktop interface."""
import ipaddress
import json
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import network

VERSION = "1.3.0"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WinNAT UI " + VERSION)
        self.geometry("1110x780")
        self.minsize(920, 640)
        self.data = None
        self.pending = []
        self.work = queue.Queue()
        self.tasks = set()
        self.selected_tab = None
        self.configure(padx=12, pady=10)
        self.build()
        self.after(100, self.drain)
        self.after(60000, self.periodic_sessions)
        self.refresh()

    def build(self):
        head = ttk.Frame(self)
        head.pack(fill="x")
        ttk.Label(head, text="WinNAT UI", font=("Segoe UI", 19, "bold")).pack(side="left")
        self.commit_button = ttk.Button(head, text="Commit", command=self.commit)
        self.commit_button.pack(side="right", padx=4)
        ttk.Button(head, text="Scarta", command=self.discard).pack(side="right", padx=4)
        ttk.Button(head, text="Aggiorna", command=self.refresh).pack(side="right", padx=4)
        self.notice = tk.StringVar(value="Caricamento configurazione...")
        ttk.Label(self, textvariable=self.notice).pack(anchor="w", pady=(8, 2))
        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 7))
        self.progress.start(11)

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)
        self.tabs.bind("<<NotebookTabChanged>>", self.tab_changed)
        overview = ttk.Frame(self.tabs, padding=12)
        rules = ttk.Frame(self.tabs, padding=12)
        wizard = ttk.Frame(self.tabs, padding=12)
        pending = ttk.Frame(self.tabs, padding=12)
        sessions = ttk.Frame(self.tabs, padding=12)
        about = ttk.Frame(self.tabs, padding=12)
        for tab, label in [(overview,"Dashboard"),(rules,"NAT"),(wizard,"Rete"),(pending,"Modifiche"),(sessions,"Sessioni"),(about,"Informazioni")]:
            self.tabs.add(tab, text=label)
        self.session_tab = sessions
        ttk.Label(overview, text="Configurazione corrente", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(overview, text="La WAN viene individuata dalla route predefinita; verifica sempre l'interfaccia prima di configurare il forwarding.").pack(anchor="w", pady=6)
        self.dashboard = tk.Text(overview, font=("Consolas", 10), state="disabled", wrap="word")
        self.dashboard.pack(fill="both", expand=True)
        ttk.Button(overview, text="Esporta", command=self.export).pack(anchor="e", pady=5)

        ttk.Label(rules, text="Regole WinNAT", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(rules, text="Le operazioni sono candidate: la rete Windows cambia solo con Commit. Le righe [+] e [-] indicano modifiche non ancora applicate.").pack(anchor="w", pady=7)
        self.nat_table = self.table(rules, [("state","Stato",100),("name","Nome",220),("prefix","Subnet interna",230),("active","Attiva",100)], height=15)
        actions = ttk.Frame(rules)
        actions.pack(fill="x", pady=8)
        ttk.Button(actions, text="Aggiungi", command=self.add).pack(side="left", padx=3)
        ttk.Button(actions, text="Elimina", command=self.remove).pack(side="left", padx=3)
        ttk.Label(rules, text="Windows WinNAT supporta un solo prefisso interno. Non aggiungere regole concorrenti a quelle esistenti.").pack(anchor="w", pady=8)

        ttk.Label(wizard, text="Setup Ethernet -> Internet", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(wizard, text="Configura l'IP gateway della scheda LAN e crea una regola WinNAT. Non viene creato un server DHCP o DNS.").pack(anchor="w", pady=8)
        self.lan = tk.StringVar(value="Ethernet")
        self.prefix = tk.StringVar(value="192.168.1.0/24")
        self.gateway = tk.StringVar(value="192.168.1.254")
        ttk.Label(wizard, text="Interfaccia LAN").pack(anchor="w")
        self.lan_box = ttk.Combobox(wizard, textvariable=self.lan, width=44, state="readonly")
        self.lan_box.pack(anchor="w", pady=5)
        self.field(wizard, "Subnet LAN (CIDR)", self.prefix)
        self.field(wizard, "IP gateway sul PC", self.gateway)
        ttk.Button(wizard, text="Configura", command=self.setup).pack(anchor="w", pady=12)
        ttk.Separator(wizard).pack(fill="x", pady=12)
        ttk.Label(wizard, text="Rimozione configurazione gestita", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(wizard, text="Rimuove il NAT gestito dal wizard e, se aggiunto dall'app, il suo IP LAN. Non rimuove configurazioni estranee.").pack(anchor="w", pady=5)
        ttk.Button(wizard, text="Rimuovi", command=self.teardown).pack(anchor="w", pady=9)
        self.wizard_notice = tk.StringVar(value="Nessuna modifica preparata")
        ttk.Label(wizard, textvariable=self.wizard_notice).pack(anchor="w", pady=7)

        ttk.Label(pending, text="Candidate configuration", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(pending, text="Confronta le modifiche proposte prima dell'applicazione. Tutte le modifiche vengono verificate di nuovo al momento del commit.").pack(anchor="w", pady=8)
        self.pending_table = self.table(pending, [("action","Azione",230),("details","Modifica proposta",680)], height=12)
        ttk.Button(pending, text="Annulla selezione", command=self.unstage).pack(anchor="w", pady=8)
        self.summary = tk.Text(pending, height=7, font=("Consolas", 10), state="disabled", wrap="word")
        self.summary.pack(fill="both", expand=True)

        toolbar = ttk.Frame(sessions)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Sessioni NAT attive", font=("Segoe UI", 13, "bold")).pack(side="left")
        ttk.Button(toolbar, text="Aggiorna", command=self.refresh_sessions).pack(side="right")
        ttk.Label(sessions, text="Vista indipendente dalla configurazione. Aggiornamento ogni 60 secondi quando la scheda è aperta; limite di 500 righe.").pack(anchor="w", pady=8)
        self.session_table = self.table(sessions,[("nat","NAT",150),("src","Origine",230),("dst","Destinazione",230),("external","Traduzione",230),("proto","Protocollo",110)],height=19)
        self.session_status = tk.StringVar(value="Apri la scheda per caricare le sessioni.")
        ttk.Label(sessions, textvariable=self.session_status).pack(anchor="w", pady=8)

        ttk.Label(about, text="WinNAT UI " + VERSION, font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(about, text="Autore: Matteo Cannizzo\nRepository: github.com/matiz311/WinNAT-UI\nLa presenza di metadati autore non equivale a firma digitale.").pack(anchor="w", pady=12)

    def table(self, parent, columns, height):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        view = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings", height=height)
        for code, label, width in columns:
            view.heading(code, text=label)
            view.column(code, width=width, minwidth=60)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=view.yview)
        view.configure(yscrollcommand=scroll.set)
        view.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return view

    def field(self, parent, label, variable):
        ttk.Label(parent, text=label).pack(anchor="w", pady=(7, 1))
        ttk.Entry(parent, width=47, textvariable=variable).pack(anchor="w")

    def run_task(self, key, fn, on_success):
        if key in self.tasks:
            return
        self.tasks.add(key)
        self.notice.set("Operazione in corso: " + key)
        self.progress.start(11)
        def runner():
            try:
                self.work.put((key, True, fn(), on_success))
            except Exception as error:
                self.work.put((key, False, str(error), on_success))
        threading.Thread(target=runner, daemon=True).start()

    def drain(self):
        try:
            while True:
                key, ok, value, callback = self.work.get_nowait()
                self.tasks.discard(key)
                if not self.tasks:
                    self.progress.stop()
                if ok:
                    callback(value)
                else:
                    self.notice.set("Errore: " + value[:160])
                    messagebox.showerror("Errore", value)
        except queue.Empty:
            pass
        self.after(100, self.drain)

    def refresh(self):
        self.run_task("Configurazione", network.collect, self.render)

    def render(self, data):
        self.data = data
        adapter_names = [a["Name"] for a in data.get("adapters",[]) if str(a.get("Status")).lower() == "up"]
        self.lan_box["values"] = adapter_names
        if adapter_names and self.lan.get() not in adapter_names:
            self.lan.set("Ethernet" if "Ethernet" in adapter_names else adapter_names[0])
        routes = [r for r in data.get("routes",[]) if r.get("DestinationPrefix") == "0.0.0.0/0"]
        routes.sort(key=lambda r: int(r.get("RouteMetric") or 0)+int(r.get("InterfaceMetric") or 0))
        lines = ["WAN prevista: " + (routes[0].get("InterfaceAlias","?") if routes else "nessuna default route"),"",
                 "Interfacce e indirizzi IPv4:"]
        for a in data.get("adapters",[]):
            ips = [f"{p['IPAddress']}/{p['PrefixLength']}" for p in data.get("ips",[]) if p.get("InterfaceIndex")==a.get("InterfaceIndex")]
            lines.append(f"  {a['Name']} [{a.get('Status')}]  {', '.join(ips) or '-'}")
        lines.extend(["","NAT rilevate: "+str(len(data.get("nats",[]))),
                      "ICS: "+str(data.get("ics",{}).get("Status","sconosciuto")),
                      "Condivisioni ICS: "+str([c.get("Name") for c in data.get("icsConnections",[]) if c.get("SharingEnabled")])])
        self.dashboard.configure(state="normal")
        self.dashboard.delete("1.0","end")
        self.dashboard.insert("end","\n".join(lines))
        self.dashboard.configure(state="disabled")
        self.render_candidate()
        self.notice.set("Configurazione caricata" + (" | Modifiche da applicare" if self.pending else ""))

    def render_candidate(self):
        self.nat_table.delete(*self.nat_table.get_children())
        nats = {n["Name"]:n for n in (self.data or {}).get("nats",[])}
        removals = {p["args"][0] for p in self.pending if p["kind"]=="remove"}
        for name,n in nats.items():
            self.nat_table.insert("", "end", values=("- Da eliminare" if name in removals else "Attiva",name,n.get("InternalIPInterfaceAddressPrefix",""),str(n.get("Active",""))))
        for p in self.pending:
            if p["kind"]=="add":
                self.nat_table.insert("","end",values=("+ Da creare",p["args"][0],p["args"][1],"Non applicata"))
            if p["kind"]=="setup":
                self.nat_table.insert("","end",values=("+ Setup", "WinNAT-UI",p["args"][1],"Non applicata"))
            if p["kind"]=="teardown":
                state=network.managed_state()
                if state and state["nat"] in nats and state["nat"] not in removals:
                    for item in self.nat_table.get_children():
                        if self.nat_table.item(item,"values")[1]==state["nat"]:
                            v=list(self.nat_table.item(item,"values"))
                            v[0]="- Da eliminare"
                            self.nat_table.item(item,values=v)
        self.pending_table.delete(*self.pending_table.get_children())
        for p in self.pending:
            self.pending_table.insert("","end",values=(p["label"],p["details"]))
        lines=["MODIFICHE DA APPLICARE: " + str(len(self.pending))]
        lines.extend(f"{i+1}. {p['label']}: {p['details']}" for i,p in enumerate(self.pending))
        if not self.pending: lines.append("Nessuna modifica candidata. La configurazione Windows non verra alterata.")
        self.summary.configure(state="normal")
        self.summary.delete("1.0","end")
        self.summary.insert("end","\n".join(lines))
        self.summary.configure(state="disabled")
        self.wizard_notice.set("Modifiche da applicare: "+str(len(self.pending)))
        self.commit_button.configure(text="Commit ("+str(len(self.pending))+")" if self.pending else "Commit")

    def stage(self, kind, args, label, details):
        if any(p["kind"]==kind and p["args"]==args for p in self.pending):
            return
        self.pending.append(dict(kind=kind,args=args,label=label,details=details))
        self.render_candidate()
        self.notice.set("Modifiche da applicare: "+str(len(self.pending)))

    def add(self):
        if self.data is None: return
        name=simpledialog.askstring("Aggiungi NAT","Nome della regola:",initialvalue="WinNAT-UI",parent=self)
        if name is None:return
        prefix=simpledialog.askstring("Aggiungi NAT","Rete interna CIDR:",initialvalue="192.168.1.0/24",parent=self)
        if prefix is None:return
        try:
            network.validate_name(name)
            network.validate_prefix(prefix)
        except Exception as exc:
            return messagebox.showerror("Dati non validi",str(exc))
        self.stage("add",(name,prefix),"Aggiungi NAT",name+" / "+prefix)

    def remove(self):
        selected=self.nat_table.selection()
        if not selected:return messagebox.showinfo("Selezione","Seleziona una regola NAT.")
        values=self.nat_table.item(selected[0],"values")
        if str(values[0]).startswith("+"):
            self.pending=[p for p in self.pending if not (p["kind"]=="add" and p["args"][0]==values[1])]
            self.render_candidate()
            return
        self.stage("remove",(values[1],),"Elimina NAT",str(values[1]))

    def setup(self):
        if self.data is None:return
        try:
            lan=self.lan.get()
            prefix=network.validate_prefix(self.prefix.get())
            gateway=network.validate_gateway(self.gateway.get(),ipaddress.IPv4Network(prefix))
            network.validate_alias(lan,self.data)
        except Exception as exc:
            return messagebox.showerror("Dati non validi",str(exc))
        self.stage("setup",(lan,prefix,gateway),"Configura rete",lan+" | "+prefix+" | gateway "+gateway)

    def teardown(self):
        state=network.managed_state()
        if not state:return messagebox.showinfo("Configurazione","Non esiste un setup registrato dall'app.")
        self.stage("teardown",(),"Rimuovi configurazione",state["lan"]+" | "+state["prefix"])

    def unstage(self):
        selected=self.pending_table.selection()
        if not selected:return
        pos=self.pending_table.index(selected[0])
        del self.pending[pos]
        self.render_candidate()

    def discard(self):
        if self.pending and messagebox.askyesno("Scarta","Scartare tutte le modifiche candidate?"):
            self.pending.clear()
            self.render_candidate()

    def commit(self):
        if not network.admin():return messagebox.showwarning("Permessi","Avvia come amministratore per applicare modifiche.")
        if not self.pending:return messagebox.showinfo("Commit","Nessuna modifica da applicare.")
        changes=list(self.pending)
        summary="\n".join(f"{i+1}. {p['label']}\n   {p['details']}" for i,p in enumerate(changes))
        if not messagebox.askyesno("Conferma Commit","Modifiche previste:\n\n"+summary+"\n\nApplicare ora? La rete potrebbe interrompersi."):
            return
        def execute():
            # Not an atomic transaction: a failure keeps remaining operations candidate.
            current=network.collect()
            network.snapshot(current)
            completed=[]
            for p in changes:
                kind,args=p["kind"],p["args"]
                nats=current.get("nats",[])
                if kind=="add":
                    if nats or any(c.get("SharingEnabled") for c in current.get("icsConnections",[])):
                        raise ValueError("WinNAT/ICS presente: rimuovi prima la configurazione concorrente.")
                    network.create_nat(*args)
                elif kind=="remove":
                    if not any(n.get("Name")==args[0] for n in nats):
                        raise ValueError("NAT non presente: "+args[0])
                    network.remove_nat(*args)
                elif kind=="setup":
                    if nats or any(c.get("SharingEnabled") for c in current.get("icsConnections",[])):
                        raise ValueError("Setup bloccato da WinNAT/ICS esistente.")
                    network.setup(*args,current)
                elif kind=="teardown":
                    network.teardown(current)
                completed.append(p)
                current=network.collect()
            return completed
        def success(applied):
            self.pending=[p for p in self.pending if p not in applied]
            messagebox.showinfo("Commit","Modifiche applicate: "+str(len(applied)))
            self.refresh()
        # One change per commit prevents half-applied multi-step operations.
        if len(changes)!=1:
            return messagebox.showwarning("Commit","Applica una modifica per volta per evitare commit parziali. Puoi lasciare le altre in attesa.")
        self.run_task("Commit",execute,success)

    def tab_changed(self,_event=None):
        if self.tabs.select()==str(self.session_tab):
            self.refresh_sessions()

    def periodic_sessions(self):
        if self.tabs.select()==str(self.session_tab):
            self.refresh_sessions()
        self.after(60000,self.periodic_sessions)

    def refresh_sessions(self):
        self.run_task("Sessioni",network.sessions,self.show_sessions)

    def show_sessions(self,rows):
        self.session_table.delete(*self.session_table.get_children())
        def endpoint(obj,ip,port):
            return str(obj.get(ip) or "")+(":"+str(obj[port]) if obj.get(port) is not None else "")
        for s in rows:
            self.session_table.insert("","end",values=(s.get("NatName") or "",
                endpoint(s,"InternalSourceAddress","InternalSourcePort"),
                endpoint(s,"InternalDestinationAddress","InternalDestinationPort"),
                endpoint(s,"ExternalSourceAddress","ExternalSourcePort"),
                str(s.get("Protocol") or "")))
        self.session_status.set(str(len(rows))+" sessioni visualizzate (massimo 500)")
        self.notice.set("Sessioni aggiornate")

    def export(self):
        if self.data is None:return
        file=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("JSON","*.json")])
        if file:
            with open(file,"w",encoding="utf-8") as output:
                json.dump(self.data,output,indent=2,ensure_ascii=False)

if __name__=="__main__":
    if sys.platform!="win32":raise SystemExit("Windows richiesto")
    App().mainloop()
