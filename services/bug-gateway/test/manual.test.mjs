import test from "node:test";
import assert from "node:assert/strict";
import worker, { normalizeManual, manualFingerprint } from "../src/index.js";

const endpoint="https://winnat-example.workers.dev/report";
const manual=(issue_number=null)=>({
  mode:"manual", title:"VPN non si collega", category:"Problema esterno",
  version:"1.16.0", issue_number,
  body:"### Diagnostica\nAdattatore mbvpn Up, IP 10.12.3.4\npassword=confidential",
});
const env=()=>({
  WINNAT_ISSUE_TOKEN:"test-only",
  RATE_LIMIT_IP:{limit:async()=>({success:true})},
  RATE_LIMIT_GLOBAL:{limit:async()=>({success:true})}
});
const post=(payload)=>new Request(endpoint,{
  method:"POST",
  headers:{"CF-Connecting-IP":"203.0.113.42","Content-Type":"application/json"},
  body:JSON.stringify(payload)
});

test("validates manual report independently from exception payload",()=>{
  const p=normalizeManual(manual());
  assert.match(p.body,/10\.12\.3\.4/);
  assert.doesNotMatch(p.body,/confidential/);
  for(const bad of [
    {...manual(),title:"abc"},
    {...manual(),body:""},
    {...manual(),issue_number:-1},
    {...manual(),issue_number:"76"},
    {...manual(),extra:"unexpected"},
    {...manual(),category:"Invalid"}
  ])assert.throws(()=>normalizeManual(bad));
});

test("manual submission creates a distinct, tracked issue without any exception",async()=>{
  const fetchOrig=globalThis.fetch;let created;
  globalThis.fetch=async(url,init)=>{
    assert.equal(init.method,"POST");
    created=JSON.parse(init.body);
    return Response.json({number:99,html_url:"https://github.com/matiz311/WinNAT-UI/issues/99"},{status:201});
  };
  try {
    const res=await worker.fetch(post(manual()),env());
    assert.equal(res.status,201);
    assert.equal((await res.json()).number,99);
    assert.deepEqual(created.labels,["bug-report","triage:ricevuto"]);
    assert.match(created.body,/Diagnostica manuale WinNAT-UI\n\n/);
    assert.match(created.body,/winnat-fingerprint:[a-f0-9]{24}/);
    assert.match(created.body,/10\.12\.3\.4/);
    assert.doesNotMatch(created.body,/confidential/);
    assert.match(await manualFingerprint("VPN non si collega"),/^[0-9a-f]{24}$/);
  } finally {globalThis.fetch=fetchOrig;}
});

test("explicit update targets an existing, classified, open issue",async()=>{
  const fetchOrig=globalThis.fetch;let comment;
  globalThis.fetch=async(url,init)=>{
    if(init.method==="POST"){
      assert.match(url,/issues\/76\/comments$/);
      comment=JSON.parse(init.body).body;
      return Response.json({id:101},{status:201});
    }
    assert.match(url,/issues\/76$/);
    return Response.json({number:76,html_url:"https://github.com/matiz311/WinNAT-UI/issues/76",
      state:"open",labels:[{name:"triage:informazioni-richieste"}]});
  };
  try {
    const res=await worker.fetch(post(manual(76)),env());
    assert.equal(res.status,200);
    assert.equal((await res.json()).number,76);
    assert.match(comment,/Aggiornamento diagnostico da WinNAT-UI/);
    assert.match(comment,/10\.12\.3\.4/);
  } finally {globalThis.fetch=fetchOrig;}
});

test("cannot update PRs, closed or unrelated issues through unauthenticated gateway",async()=>{
  const fetchOrig=globalThis.fetch;
  const cases=[
    {number:76,state:"open",labels:[],pull_request:{url:"fake"}},
    {number:76,state:"closed",labels:[{name:"bug-report"}]},
    {number:76,state:"open",labels:[]},
  ];
  try {
    for(const c of cases){
      let writes=0;
      globalThis.fetch=async(url,init)=>{
        if(init.method==="POST")writes++;
        return Response.json({...c,html_url:"https://github.com/matiz311/WinNAT-UI/issues/76"});
      };
      const res=await worker.fetch(post(manual(76)),env());
      assert.equal(res.status,409);
      assert.equal(writes,0);
    }
  } finally {globalThis.fetch=fetchOrig;}
});
