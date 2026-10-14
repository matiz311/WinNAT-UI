import test from "node:test";
import assert from "node:assert/strict";
import worker, { normalize, fingerprint } from "../src/index.js";

const sample = {
  operation: "Commit", category: "Accesso negato", exception: "RuntimeError",
  modules: ["network.py", "app.py"], version: "1.9.6", exit_code: 5
};
const endpoint = "https://winnat-bug-gateway.example.workers.dev/report";
const env = () => ({
  GITHUB_ISSUE_TOKEN: "test-only",
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
    body:"x".repeat(4200)
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
    assert.deepEqual(issue.labels,["bug-report"]);
    assert.match(issue.body,/winnat-fingerprint:[a-f0-9]{24}/);
    assert.doesNotMatch(issue.body,/203\.0\.113\.4|test-only/);
  } finally {globalThis.fetch=original;}
});

test("reuses a matching open issue", async()=>{
  const original=globalThis.fetch;
  const sig=await fingerprint(normalize(sample));
  globalThis.fetch=async (_url,init)=>{
    assert.notEqual(init.method,"POST");
    return Response.json([{number:22,html_url:"https://github.com/matiz311/WinNAT-UI/issues/22",body:"<!-- winnat-fingerprint:"+sig+" -->"}]);
  };
  try {
    const response=await worker.fetch(post(),env());
    assert.equal(response.status,200);
    assert.equal((await response.json()).already_exists,true);
  } finally {globalThis.fetch=original;}
});
