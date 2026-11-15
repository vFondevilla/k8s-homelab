"use strict";

// Run inside the pinned driver image, with the safety module preloaded.
// Set globalThis.csiTestTls to an ephemeral {key, cert} pair before this script.
const assert = require("node:assert/strict");
const https = require("node:https");
const { Client: TestClient } = require("/home/csi/app/src/driver/freenas/http");
const { Api } = require("/home/csi/app/src/driver/freenas/http/api");

(async () => {
  const credential = "test-only-csi-credential-do-not-use";
  const logs = [];
  let status = 200;
  let requests = 0;
  const server = https.createServer(globalThis.csiTestTls, (request, response) => {
    requests++;
    assert.equal(request.headers.authorization, `Bearer ${credential}`);
    response.writeHead(status, { "Content-Type": "application/json" });
    response.end(JSON.stringify(status === 200
      ? { success: true } : { echo: request.headers.authorization }));
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const client = new TestClient({ protocol: "https", host: "127.0.0.1",
    port: server.address().port, apiKey: credential, allowInsecure: true });
  client.logger = { debug: message => logs.push(message) };
  const safe = value => {
    assert.ok(!JSON.stringify(value).includes(credential), "credential escaped");
    assert.ok(!JSON.stringify(value).includes("Authorization"), "headers escaped");
  };
  try {
    for (const method of ["get", "post", "put", "delete"]) {
      status = 200;
      assert.deepEqual((await client[method]("/test")).body, { success: true });
      status = 401;
      const response = await client[method]("/test");
      assert.equal(response.statusCode, 401);
      assert.deepEqual(Object.keys(response).sort(), ["body", "statusCode"]);
      safe(response);
      status = 500;
      await assert.rejects(client[method]("/test"), error => {
        assert.match(error.message, /status 500/);
        assert.equal(error.cause, undefined);
        safe(error.stack);
        return true;
      });
    }
    status = 401;
    const api = new Api(client, { get: async () => undefined });
    await assert.rejects(api.getSystemVersion(), error => {
      assert.match(error.message, /401/);
      safe(error.stack);
      return true;
    });
    const before = requests;
    client.options.protocol = "http";
    await assert.rejects(client.get("/test"), /check HTTPS/);
    assert.equal(requests, before, "plain HTTP must not send a request");
    client.options.protocol = "https";
    client.getHttpsAgent().destroy();
    await new Promise(resolve => server.close(resolve));
    await assert.rejects(client.get("/test"), error => {
      assert.match(error.message, /ECONNREFUSED/);
      safe(error.stack);
      return true;
    });
    safe(logs);
    console.log("PASS: HTTPS credentials transmitted correctly; 200 bodies preserved; 401/probe/500/transport errors and debug logs contain no credentials; HTTP blocked");
  } finally {
    client.getHttpsAgent().destroy();
    server.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
