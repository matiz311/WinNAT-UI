// Cloudflare Worker: anonymous WinNAT-UI bug intake.
// IMPORTANT: deploy with a server-side GitHub fine-grained token (Issues: write).
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
"network_plan.py","updater.py","ui_theme.py","bug_report.py"]);
const HEADERS = {"content-type":"application/json; charset=utf-8","cache-control":"no-store"};
const json = (object, status=200) => new Response(JSON.stringify(object), {status,headers:HEADERS});
function normalize(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw Error("bad");
  const allowed = new Set(["operation","category","exception","modules","version","exit_code"]);
  if (Object.keys(raw).some(k => !allowed.has(k))) throw Error("unexpected fields");
  if (!OPS.has(raw.operation) || !CATS.has(raw.category) || !EXCEPTIONS.has(raw.exception)) throw Error("invalid enums");
  if (!Array.isArray(raw.modules) || raw.modules.length > 8 || raw.modules.some(m=>!MODULES.has(m))) throw Error("invalid modules");
  if (typeof raw.version !== "string" || !/^\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(raw.version)) throw Error("invalid version");
  if (raw.exit_code !== null && (!Number.isInteger(raw.exit_code) || raw.exit_code < 0 || raw.exit_code > 9999)) throw Error("invalid code");
  return {...raw,modules:[...new Set(raw.modules)].sort()};
}
async function fingerprint(p) {
  const stable = JSON.stringify({category:p.category,exception:p.exception,modules:p.modules,operation:p.operation});
  const bytes = await crypto.subtle.digest("SHA-256",new TextEncoder().encode(stable));
  return Array.from(new Uint8Array(bytes)).map(x=>x.toString(16).padStart(2,"0")).join("").slice(0,24);
}
async function github(env, endpoint, init={}) {
  const response = await fetch("https://api.github.com"+endpoint,{
    ...init,headers:{
      "accept":"application/vnd.github+json",
      "authorization":"Bearer "+env.GITHUB_ISSUE_TOKEN,
      "x-github-api-version":"2022-11-28",
      "user-agent":"WinNAT-UI-Bug-Gateway",
      ...(init.headers||{})
    }
  });
  if (!response.ok) throw Error("GitHub API "+response.status);
  return response.json();
}
async function lookup(env, sig) {
  // GitHub Issue listing avoids search indexing delay for recently created bugs.
  const issues = await github(env, "/repos/"+REPO+"/issues?state=all&labels=bug-report&per_page=100");
  return issues.find(x=>!x.pull_request &&
    (x.body||"").includes("<!-- winnat-fingerprint:"+sig+" -->"))||null;
}
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method!=="POST"||url.pathname!=="/report") return json({error:"not-found"},404);
    if (!env.GITHUB_ISSUE_TOKEN || !env.RATE_LIMIT) return json({error:"not-configured"},503);
    if (Number(request.headers.get("content-length")||0)>4096) return json({error:"payload-too-large"},413);
    const ip = request.headers.get("CF-Connecting-IP");
    if (!ip) return json({error:"missing-origin"},403);
    const digest=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(ip));
    const key=Array.from(new Uint8Array(digest)).map(x=>x.toString(16).padStart(2,"0")).join("").slice(0,32);
    const hits=Number(await env.RATE_LIMIT.get("rl:"+key)||0);
    if (hits>=3) return json({error:"too-many-requests"},429);
    // This is a best-effort KV limit, NOT an atomic or DDoS-grade defense.
    await env.RATE_LIMIT.put("rl:"+key,String(hits+1),{expirationTtl:3600});
    let payload;
    try {
      const raw=await request.text();
      if(raw.length>4096) return json({error:"payload-too-large"},413);
      payload=normalize(JSON.parse(raw));
    } catch {return json({error:"invalid-payload"},400);}
    const sig=await fingerprint(payload);
    try {
      const existing=await lookup(env,sig);
      if(existing){
        return json({number:existing.number,url:existing.html_url,already_exists:true});
      }
      const title="[Bug] "+payload.operation+" - "+payload.category;
      const body=[
        "## Report automatico anonimo","",
        "**Versione WinNAT-UI:** "+payload.version,
        "**Operazione:** "+payload.operation,
        "**Categoria:** "+payload.category,
        "**Eccezione Python:** "+payload.exception,
        "**Exit code PowerShell:** "+(payload.exit_code===null?"Non disponibile":payload.exit_code),
        "**Moduli:** "+(payload.modules.join(", ")||"Non disponibili"),"",
        "<!-- winnat-fingerprint:"+sig+" -->","",
        "Nessun log grezzo o configurazione di rete è stato ricevuto.",
        "Per indicare la correzione, aggiungere alla Issue la label `fixed-in/vMAJOR.MINOR.PATCH`.",
      ].join("\n");
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

export { normalize, fingerprint };
