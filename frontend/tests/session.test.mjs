// Native Node tests with mocked API responses; no running backend is used.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(import.meta.url);
const ts = require("typescript");
const axios = require("axios");

function load(file, mocks = {}) {
  const source = readFileSync(new URL(`../src/lib/${file}.ts`, import.meta.url), "utf8");
  const code = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true,
  } }).outputText;
  const loadedModule = { exports: {} };
  new Function("require", "module", "exports", code)(
    (name) => mocks[name] ?? require(name), loadedModule, loadedModule.exports,
  );
  return loadedModule.exports;
}

function browser(path = "/dashboard") {
  const values = new Map([["access_token", "old-access"], ["refresh_token", "old-refresh"]]);
  globalThis.localStorage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
  globalThis.window = new EventTarget();
  window.location = { pathname: path, href: path };
  const events = [];
  window.addEventListener("accomfind:session-ended", (event) => events.push(event.detail));
  const session = load("session");
  const { api } = load("api", { "./session": session });
  return { api, session, events };
}

function failure(config, status, code) {
  return Promise.reject(new axios.AxiosError("Request rejected", "ERR_BAD_REQUEST", config, null, {
    status, statusText: "Rejected", data: { detail: "Rejected" }, config,
    headers: code ? { "x-auth-error": code } : {},
  }));
}

function success(config, data = {}) {
  return { status: 200, statusText: "OK", headers: {}, config, data };
}

test("inactive response clears session and explains why on login", async () => {
  const { api, events } = browser();
  api.defaults.adapter = (config) => failure(config, 403, "account_inactive");
  await assert.rejects(api.get("/protected"));
  assert.equal(localStorage.getItem("access_token"), null);
  assert.equal(localStorage.getItem("refresh_token"), null);
  assert.deepEqual(events, ["account_inactive"]);
  assert.equal(window.location.href, "/login?reason=account_inactive");
});

test("permission-only 403 does not log out an active user", async () => {
  const { api, events } = browser();
  api.defaults.adapter = (config) => failure(config, 403);
  await assert.rejects(api.get("/admin-only"));
  assert.equal(localStorage.getItem("access_token"), "old-access");
  assert.deepEqual(events, []);
  assert.equal(window.location.href, "/dashboard");
});

test("revoked session ends immediately without refreshing", async () => {
  const { api, events } = browser();
  const previous = axios.defaults.adapter;
  let refreshes = 0;
  axios.defaults.adapter = () => { refreshes++; throw new Error("Must not refresh"); };
  try {
    api.defaults.adapter = (config) => failure(config, 401, "session_revoked");
    await assert.rejects(api.get("/protected"));
    assert.equal(refreshes, 0);
    assert.deepEqual(events, ["session_expired"]);
  } finally { axios.defaults.adapter = previous; }
});

test("inactive response during refresh retains the inactive message", async () => {
  const { api, events } = browser();
  const previous = axios.defaults.adapter;
  axios.defaults.adapter = (config) => failure(config, 403, "account_inactive");
  try {
    api.defaults.adapter = (config) => failure(config, 401);
    await assert.rejects(api.get("/protected"));
    assert.equal(localStorage.getItem("access_token"), null);
    assert.deepEqual(events, ["account_inactive"]);
    assert.equal(window.location.href, "/login?reason=account_inactive");
  } finally { axios.defaults.adapter = previous; }
});

test("simultaneous expired requests share one refresh", async () => {
  const { api } = browser();
  const previous = axios.defaults.adapter;
  let refreshes = 0;
  axios.defaults.adapter = async (config) => {
    refreshes++;
    await new Promise((resolve) => setTimeout(resolve, 5));
    return success(config, { access_token: "new-access", refresh_token: "new-refresh" });
  };
  api.defaults.adapter = (config) => config.headers.Authorization === "Bearer new-access"
    ? Promise.resolve(success(config)) : failure(config, 401);
  try {
    const responses = await Promise.all([api.get("/one"), api.get("/two")]);
    assert.ok(responses.every((response) => response.status === 200));
    assert.equal(refreshes, 1);
    assert.equal(localStorage.getItem("access_token"), "new-access");
  } finally { axios.defaults.adapter = previous; }
});

test("a pending refresh cannot restore a cleared session", async () => {
  const { api, session } = browser();
  const previous = axios.defaults.adapter;
  let started;
  const refreshStarted = new Promise((resolve) => { started = resolve; });
  let release;
  axios.defaults.adapter = (config) => {
    started();
    return new Promise((resolve) => { release = () => resolve(success(config, {
      access_token: "new-access", refresh_token: "new-refresh",
    })); });
  };
  api.defaults.adapter = (config) => failure(config, 401);
  try {
    const pending = api.get("/protected");
    const rejected = assert.rejects(pending);
    await refreshStarted;
    session.endSession("account_inactive");
    release();
    await rejected;
    assert.equal(localStorage.getItem("access_token"), null);
    assert.equal(localStorage.getItem("refresh_token"), null);
    assert.equal(window.location.href, "/login?reason=account_inactive");
  } finally { axios.defaults.adapter = previous; }
});

test("verification and reset pages retain their email links when sessions end", () => {
  for (const path of ["/verify-email", "/reset-password"]) {
    const { session, events } = browser(path);
    window.location.href = `${path}#token=secret`;
    session.endSession("account_inactive");
    assert.equal(window.location.href, `${path}#token=secret`);
    assert.equal(localStorage.getItem("access_token"), null);
    assert.deepEqual(events, ["account_inactive"]);
  }
});

for (const status of [429, 503]) {
  test(`refresh ${status} preserves session and allows a later retry`, async () => {
    const { api, events } = browser();
    const previous = axios.defaults.adapter;
    axios.defaults.adapter = (config) => failure(config, status);
    api.defaults.adapter = (config) => config.headers.Authorization === "Bearer new-access"
      ? Promise.resolve(success(config)) : failure(config, 401);
    try {
      await assert.rejects(api.get("/protected"), (error) => error.response.status === status);
      assert.equal(localStorage.getItem("access_token"), "old-access");
      assert.equal(localStorage.getItem("refresh_token"), "old-refresh");
      assert.deepEqual(events, []);
      axios.defaults.adapter = (config) => Promise.resolve(success(config, {
        access_token: "new-access", refresh_token: "new-refresh",
      }));
      assert.equal((await api.get("/protected")).status, 200);
    } finally { axios.defaults.adapter = previous; }
  });
}


test("API errors preserve text and format validation messages", () => {
  const { getApiErrorMessage } = load("api-error");
  const error = (detail) => new axios.AxiosError("Rejected", "ERR_BAD_REQUEST", undefined, undefined, {
    data: { detail }, status: 422, statusText: "Rejected", headers: {}, config: {},
  });
  assert.equal(getApiErrorMessage(error("Upload failed"), "Fallback"), "Upload failed");
  assert.equal(getApiErrorMessage(error([{ msg: "Title is short" }, { msg: "Address is short" }]), "Fallback"),
    "Title is short; Address is short");
});

test("API errors use safe fallback for absent or malformed payloads", () => {
  const { getApiErrorMessage } = load("api-error");
  for (const detail of [null, {}, [{ msg: {} }], [null], ""]) {
    const error = new axios.AxiosError("Rejected", "ERR_BAD_REQUEST", undefined, undefined, {
      data: { detail }, status: 422, statusText: "Rejected", headers: {}, config: {},
    });
    assert.equal(getApiErrorMessage(error, "Fallback"), "Fallback");
  }
  assert.equal(getApiErrorMessage(new Error("Network error"), "Fallback"), "Fallback");
  assert.equal(getApiErrorMessage(null, "Fallback"), "Fallback");
});
