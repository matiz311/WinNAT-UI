import test from "node:test";
import assert from "node:assert/strict";
import worker, { normalize, fingerprint } from "../src/index.js";

const sample = {
  operation: "Commit", category: "Accesso negato", exception: "RuntimeError",
  modules: ["network.py", "app.py"], version: "1.9.6", exit_code: 5
};
const endpoint = "https://winnat-bug-gateway.example.workers.dev/report";
const env = () => ({
  WINNAT_ISSUE_TOKEN: "test-only",
  RATE_LIMIT_IP: {limit: async()=>({success:true})},
  RATE_LIMIT_GLOBAL: {limit: async()=>({success:true})}
});
const post = (payload=sample) => new Request(endpoint, {
  method:"POST",
  headers:{"CF-Connecting-IP":"203.0.113.4", "Content-Type":"application/json"},
  body:JSON.stringify(payload)
});

test("health requires the server bindings", async()=>{
  const url=endpoint.replace("/report","/health");
  assert.equal((await worker.fetch(new Request(url), {})).status,503);
  const response=await worker.fetch(new Request(url),env());
  assert.equal(response.status,200);
  assert.deepEqual(await response.json(),{status:"ready"});
});

test("rejects unexpected report fields without contacting GitHub", async()=>{
  const response=await worker.fetch(post({...sample,raw_log:"private"}),env());
  assert.equal(response.status,400);
});

test("rejects rate-limited submissions", async()=>{
  const bindings=env();
  bindings.RATE_LIMIT_IP.limit=async()=>({success:false});
  assert.equal((await worker.fetch(post(),bindings)).status,429);
});

test("enforces byte limit even without Content-Length", async()=>{
  const request = new Request(endpoint, {
    method:"POST",
    headers:{"CF-Connecting-IP":"203.0.113.4","Content-Type":"application/json"},
    body:"x".repeat(67000)
  });
  assert.equal((await worker.fetch(request,env())).status,413);
});

test("creates a sanitized labeled issue", async()=>{
  const original=globalThis.fetch;
  let issue;
  globalThis.fetch=async (_url,init)=>{
    if(init.method==="POST"){
      issue=JSON.parse(init.body);
      return Response.json({number:11,html_url:"https://github.com/matiz311/WinNAT-UI/issues/11"},{status:201});
    }
    return Response.json([]);
  };
  try {
    const response=await worker.fetch(post(),env());
    assert.equal(response.status,201);
    assert.deepEqual((await response.json()).already_exists,false);
    assert.deepEqual(issue.labels,["bug-report","triage:ricevuto"]);
    assert.match(issue.body,/winnat-fingerprint:[a-f0-9]{24}/);
    assert.doesNotMatch(issue.body,/203\.0\.113\.4|test-only/);
  } finally {globalThis.fetch=original;}
});

test("publishes full diagnostic context and masks secrets server side", async()=>{
  const original=globalThis.fetch;
  let issue;
  globalThis.fetch=async (_url,init)=>{
    if(init.method==="POST"){
      issue=JSON.parse(init.body);
      return Response.json({number:33,html_url:"https://github.com/matiz311/WinNAT-UI/issues/33"},{status:201});
    }
    return Response.json([]);
  };
  try {
    const detailed={...sample,
      signature:"f".repeat(24),
      summary:"New-NetIPAddress : Oggetto già presente su LAN1",
      message:"STDERR:\nNew-NetIPAddress -IPAddress 192.168.1.1\npassword=segreto123",
      traceback:'File "C:\\Users\\mario\\app.py", line 55\nRuntimeError: conflict',
      environment:'{"sistema":"Windows-11","amministratore":true}',
      inventory:'{"ips":[{"IPAddress":"192.168.1.1"}]}'
    };
    const response=await worker.fetch(post(detailed),env());
    assert.equal(response.status,201);
    assert.match(issue.title,/New-NetIPAddress/);
    assert.match(issue.body,/192\.168\.1\.1/);
    assert.match(issue.body,/Windows-11/);
    assert.match(issue.body,/Traceback Python/);
    assert.doesNotMatch(issue.body,/segreto123|Users\\mario/);
  } finally {globalThis.fetch=original;}
});

test("reuses matching issue but appends every new diagnostic occurrence", async()=>{
  const original=globalThis.fetch;
  const sig=await fingerprint(normalize(sample));
  let comment;
  globalThis.fetch=async (url,init)=>{
    if(init.method==="POST"){
      assert.match(url,/issues\/22\/comments$/);
      comment=JSON.parse(init.body).body;
      return Response.json({id:1234},{status:201});
    }
    return Response.json([{number:22,state:"open",html_url:"https://github.com/matiz311/WinNAT-UI/issues/22",body:"<!-- winnat-fingerprint:"+sig+" -->"}]);
  };
  try {
    const response=await worker.fetch(post({...sample, message:"Nuova evidenza 192.168.7.1"}),env());
    // Sample's legacy fingerprint excludes message, so dedup still matches.
    assert.equal(response.status,200);
    assert.equal((await response.json()).already_exists,true);
    assert.match(comment,/Nuova occorrenza/);
    assert.match(comment,/192\.168\.7\.1/);
  } finally {globalThis.fetch=original;}
});
