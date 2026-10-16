// Cloudflare Worker: opt-in, detailed WinNAT-UI diagnostic intake.
// Use a server-side GitHub fine-grained token (Issues: write).
// Never publish the token in the desktop client, git repository or browser.
const REPO = "matiz311/WinNAT-UI";
const OPS = new Set(["Commit","Aggiornamenti","Download aggiornamento","Update","Refresh","Aggiorna","Sessioni","Altra operazione"]);
const CATS = new Set([
  "Configurazione modificata dopo l'anteprima","Oggetto Windows già esistente",
  "Conflitto di indirizzo IP","Ripristino non completato","Accesso negato",
  "Operazione scaduta","Rete non raggiungibile",
  "Errore di configurazione LAN tramite netsh","Errore operativo non classificato"
]);
const EXCEPTIONS = new Set(["RuntimeError","ValueError","TypeError","KeyError","OSError",
"PermissionError","FileNotFoundError","TimeoutError","CalledProcessError","ConnectionError",
"HTTPError","URLError","Exception","AttributeError","IndexError","NotImplementedError",
"JSONDecodeError","Non determinato"]);
const MODULES = new Set(["app.py","network.py","network_guide.py","network_rollback.py",
"network_plan.py","updater.py","ui_theme.py","bug_report.py","issue_tracker.py","nat_backend.py","version.py"]);
const HEADERS = {"content-type":"application/json; charset=utf-8","cache-control":"no-store"};
const json = (object, status=200) => new Response(JSON.stringify(object), {status,headers:HEADERS});
async function boundedText(request, limit=65536) {
  // Never buffer an unbounded request, even when Content-Length is missing.
  if (!request.body) return "";
  const reader = request.body.getReader();
  const chunks = [];
  let total = 0;
  try {
    while (true) {
      const {value, done} = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > limit) throw Error("payload-too-large");
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  const result = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {result.set(chunk,offset); offset += chunk.byteLength;}
  return new TextDecoder("utf-8",{fatal:true}).decode(result);
}
function configured(env) {
  return Boolean(env.WINNAT_ISSUE_TOKEN && env.RATE_LIMIT_IP && env.RATE_LIMIT_GLOBAL);
}
// Best-effort defense in depth. The client applies the same masking before sending.
function redact(text) {
  return text
    .replace(/-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----/gi,"[CHIAVE PRIVATA OSCURATA]")
    .replace(/\b(?:github_pat_|ghp_|gho_|ghu_|ghs_|ghr_)[A-Za-z0-9_]{16,}\b/g,"[TOKEN GITHUB OSCURATO]")
    .replace(/("[^"\r\n]*(?:password|passwd|token|secret|api[_-]?key)[^"\r\n]*"\s*:\s*)(?:"[^"\r\n]*"|[^\s,}]+)/gi,'$1"[OSCURATO]"')
    .replace(/\b(bearer|basic)\s+[a-z0-9._~+/\-=]{8,}/gi,"[TOKEN DI AUTORIZZAZIONE OSCURATO]")
    .replace(/([a-z][a-z0-9+.-]*:\/\/)[^/@\s:]+:[^/@\s]+@/gi,"$1[credenziali oscurate]@")
    .replace(/\b(password|passwd|pwd|token|api[_-]?key|access[_-]?token|refresh[_-]?token|secret|authorization|client[_-]?secret|cookie|set-cookie)\b(\s*[:=]\s*)(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;]+)/gi,"$1$2[OSCURATO]")
    .replace(/(-{1,2}(?:password|token|api-key|secret)\s+)(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s;]+)/gi,"$1[OSCURATO]")
    .replace(/(convertto-securestring\s+)(?:"[^"\r\n]*"|'[^'\r\n]*')/gi,"$1[OSCURATO]")
    .replace(/([A-Z]:\\Users\\)[^\\\r\n]+/gi,"$1[utente]")
    .replace(/(\/(?:home|Users)\/)[^\/\r\n]+/gi,"$1[utente]")
    .replace(/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g,"[email oscurata]");
}
function normalize(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw Error("bad");
  const allowed = new Set(["operation","category","exception","modules","version","exit_code",
    "signature","summary","message","traceback","environment","inventory"]);
  if (Object.keys(raw).some(k => !allowed.has(k))) throw Error("unexpected fields");
  if (typeof raw.operation!=="string" || !/^[\p{L}\p{N} _./:+()\-]{1,80}$/u.test(raw.operation) ||
      !CATS.has(raw.category) || !EXCEPTIONS.has(raw.exception)) throw Error("invalid enums");
  if (!Array.isArray(raw.modules) || raw.modules.length > 8 || raw.modules.some(m=>!MODULES.has(m))) throw Error("invalid modules");
  if (typeof raw.version !== "string" || !/^\d{1,3}\.\d{1,3}\.\d{1,3}(?:\.\d{1,3})?$/.test(raw.version)) throw Error("invalid version");
  if (raw.exit_code !== null && (!Number.isInteger(raw.exit_code) || raw.exit_code < 0 || raw.exit_code > 9999)) throw Error("invalid code");
  const result = {...raw,modules:[...new Set(raw.modules)].sort()};
  if (raw.signature !== undefined && (typeof raw.signature !== "string" || !/^[a-f0-9]{24}$/.test(raw.signature)))
    throw Error("invalid signature");
  for (const [name,max] of Object.entries({summary:240,message:16000,traceback:13000,environment:1500,inventory:14000})) {
    if (raw[name] === undefined) continue; // Backwards compatible with existing clients.
    if (typeof raw[name] !== "string" || raw[name].length > max || /[\u0000-\u0008\u000b\u000e-\u001f]/.test(raw[name]))
      throw Error("invalid "+name);
    result[name] = redact(raw[name]);
  }
  return result;
}
function literal(text) {
  return (text || "(non disponibile)").split(/\r?\n/).map(line=>"    "+line).join("\n");
}
function section(p, duplicate=false) {
  return [
    duplicate ? "### Nuova occorrenza / nuove evidenze" : "## Diagnostica automatica WinNAT-UI",
    "",
    "**Versione:** "+p.version,
    "**Operazione:** "+p.operation,
    "**Categoria:** "+p.category,
    "**Eccezione:** "+p.exception,
    "**Codice uscita PowerShell:** "+(p.exit_code===null?"Non disponibile":p.exit_code),
    "**Moduli:** "+(p.modules.join(", ")||"Non disponibili"),
    "",
    "### Errore principale",literal(p.summary),"",
    "### Errore originale, stdout/stderr e script PowerShell",literal(p.message),"",
    "### Traceback Python",literal(p.traceback),"",
    "### Ambiente di esecuzione",literal(p.environment),"",
    "### Inventario rete dall'interfaccia",literal(p.inventory),"",
    "### Riproduzione e risultato atteso",
    "Da integrare con i passaggi dell'utente, se necessari.","",
    "**Visibilità:** Issue GitHub pubblica. IP, interfacce e topologia non vengono",
    "oscurati per mantenere il contesto diagnostico. Credenziali, token, email",
    "e nomi utente nei percorsi sono mascherati dove riconoscibili.",
    "La mascheratura automatica non garantisce la rimozione di tutti i segreti."
  ].join("\n");
}

async function fingerprint(p) {
  const stable = JSON.stringify({category:p.category,exception:p.exception,modules:p.modules,operation:p.operation,...(p.signature?{signature:p.signature}:{})});
  const bytes = await crypto.subtle.digest("SHA-256",new TextEncoder().encode(stable));
  return Array.from(new Uint8Array(bytes)).map(x=>x.toString(16).padStart(2,"0")).join("").slice(0,24);
}
async function github(env, endpoint, init={}) {
  const response = await fetch("https://api.github.com"+endpoint,{
    ...init,headers:{
      "accept":"application/vnd.github+json",
      "authorization":"Bearer "+env.WINNAT_ISSUE_TOKEN,
      "x-github-api-version":"2022-11-28",
      "user-agent":"WinNAT-UI-Bug-Gateway",
      ...(init.headers||{})
    }
  });
  if (!response.ok) throw Error("GitHub API "+response.status);
  return response.json();
}
async function lookup(env, sig) {
  // GitHub's issue list may lag newly-created issues by several seconds.
  // Recheck before creating a new one; no raw report or user identity is cached.
  for (let attempt = 0; attempt < 6; attempt++) {
    const issues = await github(env, "/repos/"+REPO+"/issues?state=open&labels=bug-report&per_page=100");
    const found = issues.find(x=>!x.pull_request && x.state==="open" &&
      (x.body||"").includes("<!-- winnat-fingerprint:"+sig+" -->"));
    if (found) return found;
    if (attempt < 5) await new Promise(resolve=>setTimeout(resolve, 1000));
  }
  return null;
}
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname==="/health" && request.method==="GET") {
      return configured(env) ? json({status:"ready"}) : json({status:"not-configured"},503);
    }
    if (request.method!=="POST"||url.pathname!=="/report") return json({error:"not-found"},404);
    if (!configured(env)) return json({error:"not-configured"},503);
    if (Number(request.headers.get("content-length")||0)>65536) return json({error:"payload-too-large"},413);
    if (!(request.headers.get("content-type")||"").toLowerCase().startsWith("application/json"))
      return json({error:"unsupported-media-type"},415);
    const ip = request.headers.get("CF-Connecting-IP");
    if (!ip) return json({error:"missing-origin"},403);
    const digest=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(ip));
    const key=Array.from(new Uint8Array(digest)).map(x=>x.toString(16).padStart(2,"0")).join("").slice(0,32);
    // Built-in rate limiting is location-scoped and eventually consistent.
    const limits=await Promise.all([
      env.RATE_LIMIT_IP.limit({key:"report:"+key}),
      env.RATE_LIMIT_GLOBAL.limit({key:"all-report-submissions"})
    ]);
    if (limits.some(x=>!x.success)) return json({error:"too-many-requests"},429);
    let payload;
    try {
      payload=normalize(JSON.parse(await boundedText(request)));
    } catch(error) {
      if (error.message==="payload-too-large") return json({error:"payload-too-large"},413);
      return json({error:"invalid-payload"},400);
    }
    const sig=await fingerprint(payload);
    try {
      const existing=await lookup(env,sig);
      if(existing){
        // Never discard diagnostics just because the issue fingerprint matches.
        // Each new report is a distinct occurrence with its own environment.
        await github(env,"/repos/"+REPO+"/issues/"+existing.number+"/comments",{
          method:"POST",headers:{"content-type":"application/json"},
          body:JSON.stringify({body:section(payload,true)})
        });
        return json({number:existing.number,url:existing.html_url,already_exists:true});
      }
      const title=("[Bug] "+payload.operation+" - "+payload.category+
        (payload.summary?" | "+payload.summary.slice(0,100):"")).replace(/[\r\n]+/g," ").slice(0,240);
      const body=section(payload)+"\n\n<!-- winnat-fingerprint:"+sig+" -->\n\n"+
        "Per indicare la correzione, aggiungere alla Issue la label `fixed-in/vMAJOR.MINOR.PATCH`.";
      const created=await github(env,"/repos/"+REPO+"/issues",{
        method:"POST",headers:{"content-type":"application/json"},
        body:JSON.stringify({title,body,labels:["bug-report"]})
      });
      return json({number:created.number,url:created.html_url,already_exists:false},201);
    }catch(error){
      return json({error:"github-unavailable"},502);
    }
  }
};

export { normalize, fingerprint, redact, section };
