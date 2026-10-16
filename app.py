"""WinNAT UI - Tkinter GUI for Windows."""
import ipaddress
import json
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import network

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WinNAT UI 1.2.0 | Windows NAT Manager")
        self.geometry("1040x740")
        self.minsize(850, 600)
        self.data = None
        self.q = queue.Queue()
        self.busy = False
        self.pending = []
        self.configure(padx=16, pady=12)
        self.build()
        self.after(100, self.poll)
        self.refresh()

    def build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 10))
        ttk.Label(top, text="WinNAT UI", font=("Segoe UI", 19, "bold")).pack(side="left")
        ttk.Button(top, text="Aggiorna diagnostica", command=self.refresh).pack(side="right")
        self.status = tk.StringVar(value="Rilevamento in corso...")
        ttk.Label(self, textvariable=self.status).pack(fill="x")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, pady=10)
        summary = ttk.Frame(notebook, padding=10)
        manage = ttk.Frame(notebook, padding=10)
        wizard = ttk.Frame(notebook, padding=10)
        notebook.add(summary, text=" Panoramica ")
        notebook.add(manage, text=" Gestione WinNAT ")
        notebook.add(wizard, text=" Setup guidato ")
        changes = ttk.Frame(notebook, padding=10)
        notebook.add(changes, text=" Modifiche pendenti ")
        ttk.Label(changes, text="Configurazione candidata: prepara le modifiche e poi Applica (Commit). Nessuna modifica alla rete avviene durante la preparazione.", wraplength=930).pack(anchor="w", pady=10)
        self.pending_tree = ttk.Treeview(changes, columns=("action", "details"), show="headings", height=12)
        self.pending_tree.heading("action", text="Operazione")
        self.pending_tree.heading("details", text="Dettagli")
        self.pending_tree.column("action", width=230)
        self.pending_tree.column("details", width=640)
        self.pending_tree.pack(fill="both", expand=True)
        controls = ttk.Frame(changes)
        controls.pack(fill="x", pady=12)
        ttk.Button(controls, text="Rimuovi selezionata", command=self.unstage).pack(side="left", padx=4)
        ttk.Button(controls, text="Scarta modifiche", command=self.discard).pack(side="left", padx=4)
        ttk.Button(controls, text="Applica (Commit)", command=self.commit).pack(side="right", padx=4)
        about = ttk.Frame(notebook, padding=15)
        notebook.add(about, text=" Informazioni ")
        ttk.Label(about, text="WinNAT UI - Versione 1.2.0", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(about, justify="left", text="Autore: Matteo Cannizzo\nEditore dichiarato: Matteo Cannizzo\n"
                  "Repository: github.com/matiz311/WinNAT-UI\n\n"
                  "I metadati dell'eseguibile non sono una firma digitale.\n"
                  "Per un editore Windows verificato serve un certificato Authenticode valido.").pack(anchor="w", pady=15)

        ttk.Label(summary, text="WAN: uscita Internet, stimata dalla default route. LAN: rete dei dispositivi.", wraplength=930).pack(anchor="w")
        ttk.Label(summary, text="WinNAT traduce gli IP dei client LAN. ICS e un'altra funzione Windows: servizio attivo non significa condivisione attiva.", wraplength=930).pack(anchor="w", pady=(0, 10))
        self.output = tk.Text(summary, font=("Consolas", 10), wrap="none", state="disabled")
        self.output.pack(fill="both", expand=True)
        ttk.Button(summary, text="Esporta diagnostica JSON", command=self.export).pack(anchor="e", pady=6)

        ttk.Label(manage, text="WinNAT traduce il traffico delle subnet interne verso la rete esterna, ma non fornisce DHCP o DNS.", wraplength=900).pack(anchor="w")
        ttk.Label(manage, text="Windows supporta un solo prefisso interno WinNAT. Se esistono altre regole, occorre valutarle prima di crearne una nuova.", wraplength=900).pack(anchor="w", pady=(0, 12))
        ttk.Label(manage, text="Regole NAT rilevate", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.tree = ttk.Treeview(manage, columns=("name", "prefix", "active"), show="headings", height=9)
        for column, label, width in (("name", "Nome", 180), ("prefix", "Prefisso interno", 240), ("active", "Attiva", 100)):
            self.tree.heading(column, text=label)
            self.tree.column(column, width=width)
        self.tree.pack(fill="x", pady=8)
        ttk.Button(manage, text="Prepara rimozione", command=self.remove).pack(anchor="w", pady=8)
        ttk.Separator(manage).pack(fill="x", pady=12)
        ttk.Label(manage, text="Aggiungi regola", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.nat_name = tk.StringVar(value="WinNAT-UI")
        self.nat_prefix = tk.StringVar(value="192.168.1.0/24")
        self.field(manage, "Nome regola:", self.nat_name)
        self.field(manage, "Prefisso interno CIDR:", self.nat_prefix)
        ttk.Button(manage, text="Prepara creazione WinNAT", command=self.add).pack(anchor="w", pady=10)
        ttk.Label(manage, text="Limite Windows: un solo prefisso interno WinNAT supportato.\n"
                  "Non vengono rimosse regole esistenti senza selezione e conferma.",
                  foreground="#925e12").pack(anchor="w", pady=12)

        ttk.Label(wizard, text="Configura PC come router Ethernet -> WAN", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(wizard, text="L'app non fornisce DHCP e non rimuove configurazioni preesistenti.\n"
                  "Se esistono NAT o condivisioni ICS, il setup viene bloccato.").pack(anchor="w", pady=10)
        self.lan = tk.StringVar(value="Ethernet")
        self.prefix = tk.StringVar(value="192.168.1.0/24")
        self.gateway = tk.StringVar(value="192.168.1.254")
        ttk.Label(wizard, text="Interfaccia LAN").pack(anchor="w")
        self.lan_combo = ttk.Combobox(wizard, textvariable=self.lan, state="readonly", width=50)
        self.lan_combo.pack(anchor="w", pady=(2, 12))
        self.field(wizard, "Rete LAN (CIDR):", self.prefix)
        self.field(wizard, "Indirizzo IPv4 Ethernet del PC:", self.gateway)
        ttk.Button(wizard, text="Prepara setup", command=self.initial_setup).pack(anchor="w", pady=12)
        ttk.Separator(wizard).pack(fill="x", pady=10)
        ttk.Label(wizard, text="Rimuovi il setup creato dall'applicazione", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(wizard, text="Rimuove il NAT gestito e l'IP aggiunto dal wizard, ma conserva gli IP gia presenti e le altre regole.", wraplength=900).pack(anchor="w", pady=5)
        ttk.Button(wizard, text="Prepara rimozione setup", command=self.remove_setup).pack(anchor="w", pady=5)
        ttk.Label(wizard, text="WAN: rilevata tramite la rotta IPv4 predefinita; verifica la scelta nella Panoramica.\n"
                  "Il dispositivo collegato deve usare l'IP Ethernet del PC come default gateway.").pack(anchor="w")

    def field(self, parent, label, variable):
        ttk.Label(parent, text=label).pack(anchor="w", pady=(8, 2))
        ttk.Entry(parent, textvariable=variable, width=52).pack(anchor="w")

    def run_async(self, job, done=None):
        if self.busy:
            return
        self.busy = True
        self.status.set("Operazione in corso...")
        def task():
            try:
                result = job()
                self.q.put((True, result, done))
            except Exception as exc:
                self.q.put((False, str(exc), done))
        threading.Thread(target=task, daemon=True).start()

    def poll(self):
        try:
            while True:
                ok, result, callback = self.q.get_nowait()
                self.busy = False
                if ok:
                    self.status.set("Operazione completata")
                    if callback:
                        callback(result)
                else:
                    self.status.set("Errore: " + result[:200])
                    messagebox.showerror("Operazione non riuscita", result)
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def refresh(self):
        self.run_async(network.collect, self.render)

    def render(self, data):
        self.data = data
        self.tree.delete(*self.tree.get_children())
        for n in data.get("nats", []):
            self.tree.insert("", "end", values=(n.get("Name"), n.get("InternalIPInterfaceAddressPrefix"), n.get("Active")))
        adapters = data.get("adapters", [])
        self.lan_combo["values"] = [a["Name"] for a in adapters if a.get("Status") == "Up"]
        routes = [r for r in data.get("routes", []) if r.get("DestinationPrefix") == "0.0.0.0/0"]
        routes.sort(key=lambda x: (int(x.get("RouteMetric") or 0) + int(x.get("InterfaceMetric") or 0)))
        wan = routes[0] if routes else None
        parts = ["=== WAN (stima da default route) ===", json.dumps(wan, indent=2, ensure_ascii=False) if wan else "Nessuna default route IPv4",
                 "\n=== Interfacce ==="]
        for a in adapters:
            ips = [x for x in data.get("ips", []) if x.get("InterfaceIndex") == a.get("InterfaceIndex")]
            forwarding = [x.get("Forwarding") for x in data.get("interfaces", []) if x.get("InterfaceIndex") == a.get("InterfaceIndex")]
            parts.append("%s | %s | %s | IP=%s | Forwarding=%s" %
                         (a.get("Name"), a.get("Status"), a.get("InterfaceDescription"),
                          ",".join(x.get("IPAddress", "") + "/" + str(x.get("PrefixLength")) for x in ips), forwarding))
        parts += ["\n=== WinNAT ===", json.dumps(data.get("nats", []), indent=2, ensure_ascii=False),
                  "\n=== WinNAT sessioni (fino a 100) ===", json.dumps(data.get("sessions", []), indent=2, ensure_ascii=False),
                  "\n=== ICS servizio ===", json.dumps(data.get("ics"), indent=2, ensure_ascii=False),
                  "\n=== ICS condivisioni ===", json.dumps(data.get("icsConnections", []), indent=2, ensure_ascii=False)]
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("end", "\n".join(parts))
        self.output.configure(state="disabled")
        conflicts = len(data.get("nats", [])) > 1
        self.status.set(("ATTENZIONE: piu WinNAT configurati | " if conflicts else "") +
                        ("Amministratore" if network.admin() else "Sola lettura: avvia come amministratore"))

    def authorized(self):
        if not network.admin():
            messagebox.showwarning("Privilegi richiesti", "Avvia WinNAT UI come amministratore.")
            return False
        if self.data is None:
            messagebox.showwarning("Diagnostica", "Aggiorna prima la diagnostica.")
            return False
        return True

    def add(self):
        if not self.authorized():
            return
        try:
            name = network.validate_name(self.nat_name.get().strip())
            prefix = network.validate_prefix(self.nat_prefix.get().strip())
        except Exception as exc:
            return messagebox.showerror("Input non valido", str(exc))
        if self.data.get("nats"):
            return messagebox.showwarning("WinNAT esistente", "Esiste gia almeno una regola WinNAT. Rimuovi esplicitamente i NAT incompatibili prima di crearne altri.")
        if any(c.get("SharingEnabled") for c in self.data.get("icsConnections", [])):
            return messagebox.showwarning("ICS attivo", "ICS risulta abilitato su una connessione. Controlla e disabilita la condivisione concorrente prima di usare WinNAT.")
        self.stage("add", (name, prefix), "Crea NAT", name + " | " + prefix)

    def remove(self):
        if not self.authorized():
            return
        selected = self.tree.selection()
        if not selected:
            return messagebox.showwarning("Selezione richiesta", "Seleziona una regola WinNAT.")
        name = self.tree.item(selected[0], "values")[0]
        self.stage("remove", (name,), "Rimuovi NAT", name)

    def initial_setup(self):
        if not self.authorized():
            return
        try:
            prefix = network.validate_prefix(self.prefix.get().strip())
            gateway = network.validate_gateway(self.gateway.get().strip(), ipaddress.IPv4Network(prefix))
            lan = self.lan.get()
            network.validate_alias(lan, self.data)
        except Exception as exc:
            return messagebox.showerror("Input non valido", str(exc))
        if self.data.get("nats"):
            return messagebox.showwarning("NAT esistente", "Setup interrotto: esistono regole WinNAT. Gestiscile dalla scheda WinNAT prima di procedere.")
        if any(c.get("SharingEnabled") for c in self.data.get("icsConnections", [])):
            return messagebox.showwarning("ICS rilevato", "Setup interrotto: esiste almeno una condivisione ICS attiva. Verifica prima quali interfacce utilizza.")
        if not any(r.get("DestinationPrefix") == "0.0.0.0/0" for r in self.data.get("routes", [])):
            return messagebox.showerror("WAN assente", "Non esiste una default route IPv4.")
        self.stage("setup", (lan, prefix, gateway), "Setup Ethernet", "%s | %s | %s" % (lan,prefix,gateway))

    def remove_setup(self):
        if not self.authorized():
            return
        state = network.managed_state()
        if not state:
            return messagebox.showinfo("Setup non rilevato", "Nessun setup tracciato dall'app. Le regole manuali sono gestibili nella scheda WinNAT.")
        details = "LAN: {lan} | Rete: {prefix} | IP: {gateway} | NAT: {nat}".format(**state)
        if not messagebox.askyesno("Conferma rimozione", details + "\nLa connettivita dei dispositivi collegati potrebbe interrompersi. Procedere?"):
            return
        self.stage("teardown", (), "Rimuovi setup", details)

    def stage(self, kind, args, label, detail):
        if self.pending:
            return messagebox.showwarning("Modifica pendente", "Esegui o scarta il commit precedente prima di preparare una nuova modifica.")
        self.pending.append((kind, args, label, detail))
        self.pending_tree.insert("", "end", values=(label, detail))
        self.status.set("Modifica preparata. Apri Modifiche pendenti per applicarla.")

    def unstage(self):
        selected = self.pending_tree.selection()
        if selected:
            self.pending_tree.delete(selected[0])
            self.pending.clear()

    def discard(self):
        if self.pending and messagebox.askyesno("Scarta", "Scartare la configurazione candidata?"):
            self.pending_tree.delete(*self.pending_tree.get_children())
            self.pending.clear()
            self.status.set("Modifiche scartate.")

    def commit(self):
        if not self.authorized():
            return
        if not self.pending:
            return messagebox.showinfo("Nessuna modifica", "Nessuna operazione da applicare.")
        kind, args, label, detail = self.pending[0]
        if not messagebox.askyesno("Conferma commit", "Applicare la modifica?\\n%s\\n%s\\nLa connettivita potrebbe interrompersi." % (label, detail)):
            return
        def execute():
            current = network.collect()
            network.snapshot(current)
            nats = current.get("nats", [])
            if kind == "add":
                if nats or any(x.get("SharingEnabled") for x in current.get("icsConnections", [])):
                    raise ValueError("Conflitto WinNAT/ICS: aggiornare e risolvere prima del commit.")
                return network.create_nat(*args)
            if kind == "remove":
                if not any(x.get("Name") == args[0] for x in nats):
                    raise ValueError("Il NAT selezionato non esiste piu.")
                return network.remove_nat(*args)
            if kind == "setup":
                if nats or any(x.get("SharingEnabled") for x in current.get("icsConnections", [])):
                    raise ValueError("Setup bloccato: NAT o ICS gia esistente.")
                return network.setup(*args, current)
            if kind == "teardown":
                return network.teardown(current)
            raise ValueError("Operazione non supportata")
        def success(_):
            self.pending_tree.delete(*self.pending_tree.get_children())
            self.pending.clear()
            messagebox.showinfo("Commit", "Modifica applicata. Ricarico lo stato di Windows.")
            self.refresh()
        self.run_async(execute, success)

    def mutate(self, operation):
        try:
            saved = network.snapshot(self.data)
        except Exception as exc:
            return messagebox.showerror("Backup non riuscito", str(exc))
        self.status.set("Backup salvato: " + saved)
        def completed(_):
            messagebox.showinfo("Operazione eseguita", "Configurazione modificata. Backup JSON: " + saved)
            self.refresh()
        self.run_async(operation, completed)

    def export(self):
        if not self.data:
            return
        filename = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if filename:
            with open(filename, "w", encoding="utf-8") as file:
                json.dump(self.data, file, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("WinNAT UI richiede Windows.")
    App().mainloop()
