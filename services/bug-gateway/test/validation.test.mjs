import test from "node:test";
import assert from "node:assert/strict";
import { normalize, fingerprint } from "../src/index.js";

const sample = {
  operation: "Commit", category: "Accesso negato",
  exception: "RuntimeError", modules: ["app.py", "network.py"],
  version: "1.9.6", exit_code: 5
};

test("allowlist accepts known sanitized input", () => {
  const obj = normalize(sample);
  assert.equal(obj.category, "Accesso negato");
});

test("accepts release and four-component hotfix versions only", () => {
  assert.equal(normalize({ ...sample, version: "1.10.0" }).version, "1.10.0");
  assert.equal(normalize({ ...sample, version: "1.9.15.1" }).version, "1.9.15.1");
  assert.throws(() => normalize({ ...sample, version: "1.9" }));
  assert.throws(() => normalize({ ...sample, version: "1.9.15.1.2" }));
});

test("reject untrusted config data and raw strings", () => {
  for (const extra of [{ secret: "password" }, { ip: "192.168.1.3" }]) {
    assert.throws(() => normalize({ ...sample, ...extra }));
  }
  assert.throws(() => normalize({ ...sample, operation: "User @EXAMPLE" }));
  assert.throws(() => normalize({ ...sample, modules: ["/Users/alice/private.py"] }));
});

test("stable fingerprint does not depend on version or exit code", async () => {
  const one = await fingerprint(normalize(sample));
  const two = await fingerprint(normalize({ ...sample, version: "1.9.8", exit_code: 42 }));
  assert.equal(one, two);
  assert.match(one, /^[a-f0-9]{24}$/);
});

test("changes in bug category alter signature", async () => {
  const one = await fingerprint(normalize(sample));
  const two = await fingerprint(normalize({ ...sample, category: "Ripristino non completato" }));
  assert.notEqual(one, two);
});


test("retains full reports and sanitizes credentials without erasing IP context", ()=>{
  const payload = normalize({...sample,
    operation:"Lettura configurazione",
    signature:"f".repeat(24),
    summary:"New-NetIPAddress conflict",
    message:"Failed for 10.0.0.1\npassword=superSecretValue",
    traceback:'File "C:\\Users\\bob\\network.py", line 89\nRuntimeError: rejected',
    environment:'{"sistema":"Windows"}',
    inventory:'{"IPAddress":"10.0.0.1"}',
  });
  assert.equal(payload.operation,"Lettura configurazione");
  assert.match(payload.message,/10\.0\.0\.1/);
  assert.doesNotMatch(payload.message,/superSecretValue/);
  assert.doesNotMatch(payload.traceback,/Users\\bob/);
  assert.match(payload.inventory,/10\.0\.0\.1/);
  assert.throws(()=>normalize({...payload,message:"x".repeat(16001)}));
  assert.throws(()=>normalize({...payload,signature:"not-hex"}));
});
