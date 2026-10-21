const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

// Exercise the shipped adapter directly: no browser, build step or dependencies.
const htmlPath = process.env.AGENT_WORLD_HTML || path.resolve(__dirname, "../viz/agent_world.html");
const html = fs.readFileSync(htmlPath, "utf8");
const source = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)]
  .map(match => match[1]).find(source => source.includes("globalThis.AgentWorldData ="));
assert.ok(source, "The HTML includes the data adapter");
vm.runInThisContext(source);
const {normalizeTranscript, normalizeTrace, snapshotAt, parseJSON, textOf} = globalThis.AgentWorldData;
const root = process.env.AGENT_WORLD_OUT || path.resolve(__dirname, "../out");
const load = relative => JSON.parse(fs.readFileSync(path.join(root, relative, "transcript.json"), "utf8"));
const optionalFixture = relative => ({
  skip: fs.existsSync(path.join(root, relative)) ? false : `Optional run fixture is absent: ${relative}`,
});
const end = parsed => snapshotAt(parsed.beats, parsed.beats.length - 1, parsed.meta);
const call = (id, tool, args = {}) => ({id, function: {name: tool, arguments: JSON.stringify(args)}});
const done = (id, envelope, extra = {}) => ({type: "tool_call_completed", tool_call_id: id,
  result: {content: [{type: "text", text: JSON.stringify(envelope)}], ...extra}});

for (const [relative, count, submitted, inventory, findings, errors] of [
  ["", 8, true, 5, 32, 0],
  ["live", 9, true, 5, 23, 0],
  ["no_submission", 7, false, 5, 0, 0],
  ["isolation_probe", 3, true, 0, 0, 0],
  ["repair", 9, true, 5, 32, 1],
]) {
  test(`actual ${relative || "baseline"} transcript preserves episode outcome`,
    optionalFixture(path.join(relative, "transcript.json")), () => {
    const original = load(relative), parsed = normalizeTranscript(original), state = end(parsed);
    assert.equal(parsed.runId, original.run_id);
    assert.equal(parsed.beats.filter(beat => beat.kind === "result").length, count);
    assert.equal(state.toolUsed, count);
    assert.equal(state.toolLimit, 50);
    assert.equal(state.submitted, submitted);
    assert.equal(state.completed, submitted);
    assert.equal(state.inventory.length, inventory);
    assert.equal(state.findings.length, findings);
    assert.equal(state.errors, errors);
    assert.equal(parsed.meta.outputTokenBudget, 30000);
    assert.match(parsed.meta.brief, /sandboxed computing environment/);
    assert.ok(parsed.beats.every(beat => typeof beat.text === "string"));
    assert.equal(state.score.score, submitted ? 1 : 0);
  });
}

test("actual parallel fetch has one clone beat, five results and no duplicate walks",
  optionalFixture("live/transcript.json"), () => {
  const parsed = normalizeTranscript(load("live"));
  const parallel = parsed.beats.filter(beat => beat.kind === "parallel");
  assert.equal(parallel.length, 1);
  assert.deepEqual(parallel[0].calls.map(call => call.station), ["R01", "R03", "S01", "S03", "S04"]);
  assert.equal(parsed.beats.filter(beat => beat.kind === "walk" && beat.tool === "request_document").length, 0);
  assert.equal(parsed.beats.filter(beat => beat.kind === "result" && beat.groupId === parallel[0].groupId).length, 5);
  const usage = load("live").events.filter(event => event.type === "token_usage");
  const state = end(parsed);
  assert.equal(state.inputTokens, usage.reduce((sum, event) => sum + event.input_tokens, 0));
  assert.equal(state.outputTokens, 7779);
  assert.ok(parsed.beats.some(beat => beat.tool === "run_python" && beat.kind === "result" && beat.text.includes("48.787")));
});

test("actual backward scrub removes future evidence and accepted findings",
  optionalFixture("repair/transcript.json"), () => {
  const parsed = normalizeTranscript(load("repair"));
  const beforeResult = parsed.beats.findIndex(beat => beat.kind === "result") - 1;
  const initial = snapshotAt(parsed.beats, beforeResult, parsed.meta);
  assert.equal(initial.toolUsed, 0);
  assert.deepEqual(initial.inventory, []);
  assert.equal(initial.submitted, false);
  const rejected = parsed.beats.findIndex(beat => beat.kind === "result" && beat.error);
  const afterRejected = snapshotAt(parsed.beats, rejected, parsed.meta);
  assert.equal(afterRejected.toolUsed, 8);
  assert.equal(afterRejected.errors, 1);
  assert.equal(afterRejected.submitted, false);
  assert.deepEqual(afterRejected.findings, []);
  assert.equal(end(parsed).submitted, true);
  assert.deepEqual(snapshotAt(parsed.beats, beforeResult, parsed.meta), initial);
  assert.equal(snapshotAt(parsed.beats, -1, parsed.meta).toolUsed, 0);
});

test("actual live ledger reproduces budgets, evidence and submissions without thoughts or tokens",
  optionalFixture("live/gb2019-live-opus55-001_artifacts/episode/trace.jsonl"), () => {
  const tracePath = path.join(root, "live/gb2019-live-opus55-001_artifacts/episode/trace.jsonl");
  const source = fs.readFileSync(tracePath, "utf8");
  const beats = normalizeTrace(source), state = snapshotAt(beats, beats.length - 1);
  assert.equal(beats.length, 18);
  assert.equal(beats.filter(beat => beat.kind === "think" || beat.kind === "tokens").length, 0);
  assert.ok(beats.filter(beat => beat.kind === "walk").every(beat => beat.text === "…"));
  assert.equal(state.toolUsed, 9);
  assert.equal(state.toolLimit, 50);
  assert.equal(state.findings.length, 23);
  assert.equal(state.submitted, true);
  assert.equal(state.completed, false, "A submission cannot fabricate a final scoring event");
  assert.equal(state.outputTokens, 0);
  assert.equal(beats.find(beat => beat.tool === "run_python" && beat.kind === "result").outcome, "OK");
  assert.deepEqual(state.inventory, ["R01", "R03", "S01", "S03", "S04"]);
});

test("leading JSON plus stdout parses safely, including quotes and nested braces", () => {
  const envelope = {ok: true, data: {value: "} quoted \\\" [", list: [{}]}};
  assert.deepEqual(parseJSON(JSON.stringify(envelope) + "\n\n--- stdout ---\nhello"), envelope);
  assert.equal(parseJSON("{malformed", "fallback"), "fallback");
  assert.equal(parseJSON("plain text"), null);
  assert.equal(textOf([{type: "text", text: "one"}, {type: "text", text: "two"}]), "one\n\ntwo");
});

test("structuredContent fallback, unknown events and malformed inputs stay inspectable", () => {
  for (const value of [null, 2, [], "{broken", {events: "no"}]) {
    const parsed = normalizeTranscript(value);
    assert.deepEqual(parsed.beats, []);
    assert.equal(end(parsed).toolUsed, 0);
  }
  const parsed = normalizeTranscript({events: [
    null,
    {type: "future_event", payload: "<script>"},
    {type: "tool_call_started", tool_call: {id: "x", function: {name: "new_tool", arguments: "{broken"}}},
    {type: "tool_call_completed", tool_call_id: "x", result: {
      content: [{text: "not JSON"}], structuredContent: {ok: true, tool: "new_tool", budget: {tool_calls_used: 1, tool_calls_limit: 10}, data: {value: 3}},
    }},
  ]});
  assert.equal(parsed.beats[0].kind, "generic");
  assert.match(parsed.beats[1].text, /<script>/);
  assert.equal(parsed.beats[2].station, "think");
  assert.deepEqual(parsed.beats[2].args, {});
  assert.equal(parsed.beats[3].envelope.data.value, 3);
  assert.equal(end(parsed).toolUsed, 1);
  assert.equal(end(parsed).toolLimit, 10);
  assert.equal(normalizeTrace("malformed\n{}\n").length, 2);
});

test("all three error signals are classified and failed retrievals never enter inventory", () => {
  const parsed = normalizeTranscript({events: [
    {type: "tool_call_started", tool_call: call("x", "request_document", {doc_id: "R01"})},
    done("x", {ok: false, tool: "request_document", error: {code: "NO_DOCUMENT", message: "Missing"}}),
    done("y", {ok: true}, {isError: true}),
    {...done("z", {ok: true}), outcome_code: "EXEC_FAILED"},
  ]});
  assert.equal(end(parsed).errors, 3);
  assert.deepEqual(end(parsed).inventory, []);
  const trace = normalizeTrace([{tool: "submit_findings", request_id: "r",
    outcome_code: "VALIDATION_FAILED", args: {submission: {findings: [{finding_id: "F01"}]}},
    envelope: {ok: true, data: {status: "accepted_and_frozen"}}}]);
  assert.equal(trace[1].error, true);
  assert.equal(snapshotAt(trace, 1).submitted, false);
});

test("missing start records still associate calls, parallel arguments and accepted findings", () => {
  const events = [
    {type: "message_added", message: {role: "assistant", tool_calls: [
      call("a", "request_document", {doc_id: "R01"}), call("b", "request_document", {doc_id: "S01"}),
    ]}},
    done("a", {ok: true, tool: "request_document", data: {doc_id: "R01"}}),
    done("b", {ok: true, tool: "request_document", data: {doc_id: "S01"}}),
    {type: "message_added", message: {role: "assistant", tool_calls: [
      call("c", "submit_findings", {submission: {findings: [{finding_id: "F01", status: "reported"}]}}),
    ]}},
    done("c", {ok: true, tool: "submit_findings", data: {status: "accepted_and_frozen"}}),
  ];
  const parsed = normalizeTranscript({events});
  assert.equal(parsed.beats[0].kind, "parallel");
  assert.deepEqual(end(parsed).inventory, ["R01", "S01"]);
  assert.equal(end(parsed).findings[0].finding_id, "F01");
  assert.equal(end(parsed).toolUsed, 3);
});

function syntheticReplay() {
  const docA = call("a", "request_document", {doc_id: "R01"});
  const docB = call("b", "request_document", {doc_id: "S01"});
  const submit = call("submit", "submit_findings", {
    submission: {findings: [{finding_id: "F01", status: "reported", statement: "A measured change."}]},
  });
  const budget = used => ({tool_calls_used: used, tool_calls_limit: 8, tool_calls_remaining: 8 - used});
  return normalizeTranscript({run_id: "synthetic-run", events: [
    {type: "task_started", task_id: "test-task", model: "test-model", timestamp: "2026-10-19T12:00:00Z"},
    {type: "task_pre_hook_completed", metadata: {
      documents: ["R01", "S01"], budgets: {max_tool_calls: 8, output_token_budget: 100},
    }},
    {type: "message_added", message: {role: "user", content: "Investigate the evidence."}},
    {type: "message_added", message: {role: "assistant", reasoning_content: "Read both documents.", tool_calls: [docA, docB]}},
    {type: "token_usage", input_tokens: 20, output_tokens: 3},
    {type: "tool_call_started", tool_call: docA},
    {type: "tool_call_started", tool_call: docB},
    done("b", {ok: true, tool: "request_document", budget: budget(2), data: {doc_id: "S01", title: "Second record"}}),
    done("a", {ok: true, tool: "request_document", budget: budget(1), data: {doc_id: "R01", title: "First record"}}),
    {type: "token_usage", input_tokens: 40, output_tokens: 7},
    {type: "message_added", message: {role: "assistant", tool_calls: [submit]}},
    {type: "tool_call_started", tool_call: submit},
    done("submit", {ok: true, tool: "submit_findings", budget: budget(3), data: {status: "accepted_and_frozen"}}),
    {type: "scoring", scoring: {score: 1, metadata: {
      outcome: "complete", provisional: true, score_semantics: "Completion only; not quality.",
    }}},
    {type: "task_completed", status: "passed"},
  ]});
}

test("synthetic replay preserves parallel results, out-of-order budgets and cumulative tokens", () => {
  const parsed = syntheticReplay(), state = end(parsed);
  const group = parsed.beats.find(beat => beat.kind === "parallel");
  assert.equal(parsed.runId, "synthetic-run");
  assert.equal(parsed.meta.model, "test-model");
  assert.equal(parsed.meta.taskId, "test-task");
  assert.equal(parsed.meta.startTime, Date.parse("2026-10-19T12:00:00Z"));
  assert.equal(parsed.meta.outputTokenBudget, 100);
  assert.equal(parsed.meta.brief, "Investigate the evidence.");
  assert.deepEqual(group.calls.map(call => call.station), ["R01", "S01"]);
  assert.equal(parsed.beats.filter(beat => beat.kind === "parallel").length, 1);
  assert.equal(parsed.beats.filter(beat => beat.kind === "walk" && beat.tool === "request_document").length, 0);
  assert.equal(parsed.beats.filter(beat => beat.kind === "result" && beat.groupId === group.groupId).length, 2);
  const beforeSubmit = parsed.beats.findIndex(beat => beat.kind === "result" && beat.tool === "submit_findings") - 1;
  assert.equal(snapshotAt(parsed.beats, beforeSubmit, parsed.meta).toolUsed, 2);
  assert.equal(state.toolUsed, 3);
  assert.equal(state.toolLimit, 8);
  assert.equal(state.inputTokens, 60);
  assert.equal(state.outputTokens, 10);
  assert.deepEqual(state.inventory, ["S01", "R01"]);
  assert.equal(state.findings[0].finding_id, "F01");
  assert.equal(state.score.score, 1);
  assert.equal(state.completed, true);
});

test("synthetic backward seeks restore inventory, findings, errors, tokens and completion", () => {
  const parsed = syntheticReplay();
  const beforeResults = parsed.beats.findIndex(beat => beat.kind === "result") - 1;
  const checkpoint = snapshotAt(parsed.beats, beforeResults, parsed.meta);
  assert.equal(checkpoint.inputTokens, 20);
  assert.equal(checkpoint.outputTokens, 3);
  assert.equal(checkpoint.toolUsed, 0);
  assert.deepEqual(checkpoint.inventory, []);
  assert.deepEqual(checkpoint.findings, []);
  assert.equal(checkpoint.submitted, false);
  assert.equal(checkpoint.completed, false);
  assert.equal(checkpoint.score, null);
  assert.equal(end(parsed).completed, true);
  assert.deepEqual(snapshotAt(parsed.beats, beforeResults, parsed.meta), checkpoint);
  const initial = snapshotAt(parsed.beats, -1, parsed.meta);
  assert.equal(initial.inputTokens, 0);
  assert.equal(initial.outputTokens, 0);
  assert.equal(initial.toolLimit, 8);
  assert.equal(initial.errors, 0);
});

test("synthetic live ledger preserves evidence, failed retries and submission without invented reasoning", () => {
  const budget = used => ({tool_calls_used: used, tool_calls_limit: 5});
  const records = [
    {tool: "list_documents", request_id: "r1", recorded_at: "2026-10-19T12:00:00Z", args: {}, outcome_code: "OK",
      envelope: {ok: true, budget: budget(1), data: {documents: [{doc_id: "R01", title: "Frequency"}]}}},
    {tool: "request_document", request_id: "r2", args: {doc_id: "R01"}, outcome_code: "OK",
      envelope: {ok: true, budget: budget(2), data: {doc_id: "R01", content: "Measured evidence."}}},
    {tool: "submit_findings", request_id: "r3", args: {submission: {findings: [{finding_id: "invalid"}]}},
      outcome_code: "VALIDATION_FAILED", envelope: {ok: false, budget: budget(3),
        error: {message: "Citation needs repair."}, data: {}}},
    {tool: "submit_findings", request_id: "r4",
      args: {submission: {findings: [{finding_id: "F01", status: "reported"}]}}, outcome_code: "OK",
      envelope: {ok: true, budget: budget(4), data: {status: "accepted_and_frozen"}}},
  ];
  const beats = normalizeTrace(records.map(record => JSON.stringify(record)).join("\n") + "\n");
  assert.equal(beats.length, 8);
  assert.equal(beats[0].time, Date.parse("2026-10-19T12:00:00Z"));
  assert.equal(beats.filter(beat => beat.kind === "think" || beat.kind === "tokens").length, 0);
  assert.ok(beats.filter(beat => beat.kind === "walk").every(beat => beat.text === "…"));
  const rejected = snapshotAt(beats, 5);
  assert.equal(rejected.errors, 1);
  assert.equal(rejected.submitted, false);
  assert.deepEqual(rejected.findings, []);
  const state = snapshotAt(beats, beats.length - 1);
  assert.deepEqual(state.inventory, ["R01"]);
  assert.equal(state.documents[0].title, "Frequency");
  assert.equal(state.toolUsed, 4);
  assert.equal(state.toolLimit, 5);
  assert.equal(state.findings[0].finding_id, "F01");
  assert.equal(state.submitted, true);
  assert.equal(state.completed, false);
  assert.equal(state.score, null);
  assert.equal(state.inputTokens, 0);
  assert.equal(state.outputTokens, 0);
  assert.equal(beats[5].outcome, "VALIDATION_FAILED");
});

// ---------------------------------------------------------------------------
// System-response task (manifest v2): new tools, dynamic evidence, budgets, live.
// Synthetic runs build the envelopes the episode ledger records; no out/ needed.

const SR_DOCS = ["R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08", "R10", "S01", "S03", "S04", "S05", "S06", "S07", "S12"];
const SR_LISTED = SR_DOCS.filter(id => !["S05", "S06"].includes(id));
const SR_TOOLS = ["list_documents", "request_document", "query_frequency", "query_asset_log", "query_control_log",
  "interview_witness", "request_data_return", "run_python", "submit_findings"];
const category = id => ({R01: "measurement_data", R02: "measurement_data", R03: "network_records", S01: "generator_records",
  S07: "system_operator_records", S05: "distribution_records"})[id] || "analysis_records";
const fail = (code, message, details = []) => ({ok: false, error: {code, message, details}});
const window = {start: "2019-08-09T16:52:30+01:00", end: "2019-08-09T16:52:34+01:00", rule: "start inclusive, end exclusive"};
const SR_CALLS = [
  ["list_documents", {}, {data: {documents: SR_LISTED.map(id => ({doc_id: id, title: `${id} record`, category: category(id)})),
    categories: ["measurement_data", "network_records"], total: 14,
    asset_logs: [{asset_id: "ESW-400", title: "Eaton Socon - Wymondley Main 400 kV circuit"}, {asset_id: "HORNSEA-ONE", title: "Hornsea One offshore wind farm"}],
    control_logs: [{room_id: "ESO-ENCC", title: "ESO control centre"}],
    witnesses: [{persona_id: "eso-control-engineer", role: "Control engineer", organisation: "National Grid ESO", evidence_id: "S09"},
      {persona_id: "dno-control-engineer", role: "DNO control engineer", organisation: "Distribution Network Operators", evidence_id: "S09"}],
    data_returns: [{party: "DNO", data_type: "lfdd_returns"}, {party: "METEOGROUP", data_type: "lightning_stroke_records"}]}}],
  ["query_frequency", {start: window.start, end: window.end}, {evidence: ["R01"], next: "cursor-1", data: {doc_id: "R01",
    window, rows: [[751, "2019-08-09T16:52:30+01:00", 50.006], [752, "2019-08-09T16:52:31+01:00", 49.9]],
    total_rows: 4, offset: 0, returned: 2, page_size: 2, unit: "Hz", resolution_s: 1}}],
  ["query_frequency", {start: window.start, end: window.end, cursor: "cursor-1"}, {evidence: ["R01"], data: {doc_id: "R01",
    window, rows: [[753, "2019-08-09T16:52:32+01:00", 49.5], [754, "2019-08-09T16:52:33+01:00", 49.2]],
    total_rows: 4, offset: 2, returned: 2, page_size: 2, unit: "Hz", resolution_s: 1}}],
  ["query_asset_log", {asset_id: "ESW-400", start: "2019-08-09T15:50:00Z", end: "2019-08-09T16:00:00Z"}, {evidence: ["R03"], data: {
    asset_id: "ESW-400", title: "Eaton Socon - Wymondley Main 400 kV circuit", window, total_rows: 2, offset: 0, returned: 2,
    rows: [{event_id: "R03-B3", evidence_id: "R03", recorded_time: "16:52:33", signal: "event", value: null, text: "lightning strikes", value_status: "reported"},
      {event_id: "R03-C1", evidence_id: "R03", recorded_time: "16:52:33.490", signal: "current", value: 21, unit: "kA", value_status: "reported"}]}}],
  ["query_control_log", {room: "ESO-ENCC", start: "2019-08-09T15:52:00Z", end: "2019-08-09T15:58:00Z"}, {evidence: ["S07"], data: {
    room: "ESO-ENCC", window, total_rows: 1, offset: 0, returned: 1,
    rows: [{entry_id: "S07-T01", evidence_id: "S07", recorded_time: "16:53", from: "ESO-ENCC", to: "NGET", text: "Call about the trip", value_status: "reported"}]}}],
  ["interview_witness", {persona_id: "eso-control-engineer", question: "What loss were you securing?"}, {evidence: ["S09"], data: {
    persona_id: "eso-control-engineer", role: "Control engineer", organisation: "National Grid ESO", matched: true,
    response_id: "S09-ESO-01", topics: ["securing"], response_text: "The largest secured loss."}}],
  ["interview_witness", {persona_id: "dno-control-engineer", question: "What was the weather?"}, {data: {
    persona_id: "dno-control-engineer", role: "DNO control engineer", organisation: "Distribution Network Operators",
    matched: false, response_id: null, topics: [], response_text: "Not known to me."}}],
  ["interview_witness", {persona_id: "eso-control-engineer", question: "How were trains affected?"},
    fail("AMBIGUOUS_REQUEST", "the question does not match exactly one topic; nothing was answered",
      [{topics: ["frequency recovery", "system stability"]}, {topics: ["securing"]}])],
  ["request_data_return", {party: "DNO", data_type: "lfdd_returns"}, {evidence: ["S05"], data: {doc_id: "S05", title: "DNO returns",
    category: "distribution_records", content: "S05 text", party: "DNO", data_type: "lfdd_returns", return_status: "available",
    message: "Per-area returns."}}],
  ["request_data_return", {party: "METEOGROUP", data_type: "lightning_stroke_records"},
    fail("NOT_HELD", "METEOGROUP / lightning_stroke_records: Not held in this evidence pack.",
      [{party: "METEOGROUP", data_type: "lightning_stroke_records", status: "not_held"}])],
  ["request_data_return", {party: "RWE", data_type: "internal_review"},
    fail("REFUSED", "RWE / internal_review: refused.", [{party: "RWE", data_type: "internal_review", status: "refused"}])],
  ["request_data_return", {party: "../private", data_type: "answer_key"}, fail("UNKNOWN_ID", "no data return is registered",
    [{path: "party", valid: [{party: "DNO", data_type: "lfdd_returns"}, {party: "METEOGROUP", data_type: "lightning_stroke_records"}]}])],
  ["request_document", {party: "National Grid ESO", description: "control room log"}, {evidence: ["S07"], data: {doc_id: "S07",
    title: "ESO control room log", category: "system_operator_records", content: "S07 text",
    matched_by: {matcher_version: "doc-tokens-2", party: "National Grid ESO", description: "control room log", description_score: 1, party_score: 1}}}],
  ["request_document", {party: "ESO", description: "records"}, fail("AMBIGUOUS_REQUEST", "the request matches 2 documents equally",
    [{doc_id: "R06", title: "Response holding"}, {doc_id: "S12", title: "Engineering analysis"}])],
  ["request_document", {party: "../private", description: "answer key"}, fail("UNKNOWN_ID", "no listed document matches",
    [{path: "description", message: "no matching document"}])],
  ["request_document", {doc_id: "S06"}, fail("UNKNOWN_ID", "no document has ID 'S06'", [{path: "doc_id", message: "unknown ID", valid: SR_LISTED}])],
  ["submit_findings", {submission: {findings: [{finding_id: "F01", status: "reported", statement: "A recorded fact."}]}},
    {data: {status: "accepted_and_frozen", findings_count: 1}}],
];

function srEnvelope(tool, used, spec) {
  return {ok: spec.ok !== false, request_id: `req-${String(used).padStart(3, "0")}`, tool, evidence_ids: spec.evidence || [],
    data: spec.data ?? null, error: spec.error ?? null, next_cursor: spec.next ?? null,
    budget: {tool_calls_used: used, tool_calls_limit: 150, tool_calls_remaining: 150 - used}};
}

function srTranscript({calls = SR_CALLS, outputBudget = 80000, tokens = {}, scoring = null, preHookBudgets = true} = {}) {
  const events = [
    {type: "task_started", run_id: "sr-synthetic", task_id: "gb-2019-system-response", model: "test-model", timestamp: "2026-10-20T10:00:00Z"},
    {type: "task_pre_hook_completed", metadata: {manifest_version: 2, tool_names: SR_TOOLS, documents: SR_DOCS,
      ...(preHookBudgets ? {budgets: {max_tool_calls: 150, output_token_budget: outputBudget}} : {})}},
  ];
  calls.forEach(([tool, args, spec], i) => {
    const id = `c${i + 1}`, envelope = srEnvelope(tool, i + 1, spec);
    events.push({type: "message_added", message: {role: "assistant", tool_calls: [call(id, tool, args)]}});
    if (tokens[i + 1]) events.push({type: "token_usage", input_tokens: 100, output_tokens: tokens[i + 1]});
    events.push({type: "tool_call_started", tool_call: call(id, tool, args)});
    events.push(done(id, envelope, {structuredContent: envelope}));
  });
  if (scoring) events.push({type: "scoring", scoring}, {type: "task_completed", status: scoring.score ? "passed" : "failed"});
  return {run_id: "sr-synthetic", events};
}

function srTrace(calls = SR_CALLS) {
  return calls.map(([tool, args, spec], i) => {
    const envelope = srEnvelope(tool, i + 1, spec);
    return {seq: i + 1, request_id: envelope.request_id, tool, args, counted: true,
      outcome_code: envelope.error ? envelope.error.code : "OK", envelope, recorded_at: `2026-10-20T10:00:${String(i).padStart(2, "0")}Z`};
  });
}

const resultsOf = beats => beats.filter(beat => beat.kind === "result");
const {worldOf} = globalThis.AgentWorldData;

test("system-response tools normalise to their own stations, records and outcomes", () => {
  const parsed = normalizeTranscript(srTranscript()), results = resultsOf(parsed.beats);
  assert.equal(results.length, SR_CALLS.length);
  assert.deepEqual(results.map(beat => beat.station), ["catalogue", "frequency", "frequency", "assets", "control",
    "interview", "interview", "interview", "returns", "returns", "returns", "returns", "enquiry", "enquiry", "enquiry", "S06", "submit"]);
  assert.deepEqual(results.map(beat => beat.errorKind), [null, null, null, null, null, null, null, "clarify", null,
    "refusal", "refusal", "error", null, "clarify", "error", "error", null]);
  assert.deepEqual(results.map(beat => beat.docId), [null, "R01", "R01", null, null, null, null, null, "S05",
    null, null, null, "S07", null, null, null, null]);
  // Paging: the first page returns a cursor; the continuation reports its rows.
  assert.equal(results[1].nextCursor, "cursor-1");
  assert.match(results[1].text, /Rows 1–2 of 4 · more rows: a next_cursor was returned/);
  assert.match(results[2].text, /Rows 3–4 of 4 · last page/);
  assert.match(results[3].title, /ESW-400 · 2 rows/);
  assert.match(results[3].text, /R03-C1 \[reported\]/);
  assert.match(results[4].title, /ESO-ENCC · 1 row$/);
  assert.match(results[5].title, /S09-ESO-01/);
  assert.equal(results[6].notKnown, true);
  assert.equal(results[6].title, "Witness: not known");
  assert.match(results[7].text, /Topic choices:\n• frequency recovery; system stability\n• securing/);
  assert.equal(results[9].outcome, "NOT_HELD");
  assert.match(results[9].text, /Not held in this evidence pack/);
  assert.equal(results[10].outcome, "REFUSED");
  assert.match(results[12].title, /S07 received by description/);
  assert.match(results[12].text, /Matched National Grid ESO · “control room log” → S07 \(matcher doc-tokens-2\)/);
  assert.match(results[13].text, /Candidates:\n• R06 — Response holding\n• S12 — Engineering analysis/);
  const walks = parsed.beats.filter(beat => beat.kind === "walk");
  assert.equal(walks.find(beat => beat.tool === "request_document" && beat.args.party).station, "enquiry");
  assert.match(walks.find(beat => beat.tool === "interview_witness").text, /eso-control-engineer: What loss/);
});

test("system-response snapshot tallies obtained documents, records, witnesses, returns and refusals", () => {
  const parsed = normalizeTranscript(srTranscript()), state = end(parsed);
  assert.equal(state.toolUsed, 17);
  assert.equal(state.toolLimit, 150);
  assert.equal(state.outputLimit, 80000);
  assert.deepEqual(state.inventory, ["R01", "S05", "S07"]);
  assert.deepEqual(state.routes, {R01: ["query_frequency"], S05: ["request_data_return"], S07: ["request_document"]});
  assert.deepEqual(state.records, {event: 2, entry: 1, response: 1, frequencyRows: 4});
  assert.equal(state.errors, 7);
  assert.equal(state.refusals, 2);
  assert.equal(state.clarifications, 2);
  assert.deepEqual(state.enquiries, {asked: 3, matched: 1, ambiguous: 1, failed: 1});
  assert.deepEqual({...state.witnesses["eso-control-engineer"]}, {persona_id: "eso-control-engineer", role: "Control engineer",
    organisation: "National Grid ESO", asked: 2, answered: 1, notKnown: 0, ambiguous: 1, failed: 0, responses: ["S09-ESO-01"]});
  assert.equal(state.witnesses["dno-control-engineer"].notKnown, 1);
  assert.deepEqual(state.returns.map(item => [item.party, item.outcome, item.docId]),
    [["DNO", "OK", "S05"], ["METEOGROUP", "NOT_HELD", null], ["RWE", "REFUSED", null], ["../private", "UNKNOWN_ID", null]]);
  assert.deepEqual(state.frequency.queries, 2);
  assert.equal(state.frequency.last.next, null);
  assert.equal(state.assets["ESW-400"].rows, 2);
  assert.equal(state.rooms["ESO-ENCC"].rows, 1);
  assert.equal(state.catalogue.documents.length, 14);
  assert.deepEqual(state.catalogue.assets, ["ESW-400", "HORNSEA-ONE"]);
  assert.equal(state.submitted, true);
  assert.equal(state.findings[0].finding_id, "F01");
  assert.equal(state.documents.find(doc => doc.doc_id === "S05").title, "DNO returns");
  assert.equal(state.documents.find(doc => doc.doc_id === "S05").content, undefined, "document text stays out of the snapshot");
});

test("evidence inventory comes from the run, not a five-document baseline", () => {
  const parsed = normalizeTranscript(srTranscript()), world = worldOf(parsed.beats, parsed.meta);
  assert.deepEqual(world.documents.map(doc => doc.doc_id), SR_DOCS);
  assert.deepEqual(world.documents.filter(doc => doc.access === "data_return").map(doc => doc.doc_id), ["S05", "S06"]);
  assert.equal(world.documents.find(doc => doc.doc_id === "R01").access, "listed");
  assert.deepEqual(world.tools.slice().sort(), SR_TOOLS.slice().sort());
  assert.deepEqual(world.witnesses.map(person => person.persona_id), ["eso-control-engineer", "dno-control-engineer"]);
  assert.deepEqual(world.assets.map(asset => asset.asset_id), ["ESW-400", "HORNSEA-ONE"]);
  assert.deepEqual(world.rooms.map(room => room.room_id), ["ESO-ENCC"]);
  assert.ok(world.dataReturns.some(item => item.party === "RWE"), "a requested pair joins the registry");
  assert.equal(world.features.enquiry, true);
  // Without a catalogue listing, the IDs an UNKNOWN_ID reports as valid still mark return-only records.
  const probe = normalizeTranscript(srTranscript({calls: [SR_CALLS[15]]}));
  assert.deepEqual(worldOf(probe.beats, probe.meta).documents.filter(doc => doc.access === "data_return").map(doc => doc.doc_id), ["S05", "S06"]);
  // Any document count works: three listed documents, no metadata, no legacy cabinets.
  const small = normalizeTranscript({events: [done("x", {ok: true, tool: "list_documents", data: {documents: [
    {doc_id: "A1", category: "x"}, {doc_id: "B2", category: "y"}, {doc_id: "C3", category: "y"}]}})]});
  const smallWorld = worldOf(small.beats, small.meta);
  assert.deepEqual(smallWorld.documents.map(doc => doc.doc_id), ["A1", "B2", "C3"]);
  assert.deepEqual(smallWorld.categories, ["x", "y"]);
  assert.equal(smallWorld.features.enquiry, false, "description requests need a manifest-v2 task");
  assert.ok(smallWorld.tools.includes("submit_findings"), "older transcripts offered the MVP tools");
  assert.equal(globalThis.AgentWorldData.stationFor("request_document", {doc_id: "../private/key"}), "archive");
  assert.equal(globalThis.AgentWorldData.stationFor("request_document", {party: "ESO", description: "log"}), "enquiry");
});

test("budgets come from task metadata: 150 calls and the 80k or 30k output budget", () => {
  const tokens = {16: 20000, 17: 16364};
  for (const [budget, over] of [[80000, false], [30000, true]]) {
    const parsed = normalizeTranscript(srTranscript({outputBudget: budget, tokens}));
    const accepted = parsed.beats.findIndex(beat => beat.kind === "result" && beat.submitted);
    const state = snapshotAt(parsed.beats, accepted, parsed.meta);
    assert.equal(parsed.meta.toolLimit, 150);
    assert.equal(parsed.meta.outputTokenBudget, budget);
    assert.match(parsed.beats.find(beat => beat.title === "Office ready").text, new RegExp(`${budget.toLocaleString("en-GB")}-token output budget`));
    assert.equal(state.outputTokens, 36364);
    assert.equal(state.overOutputBudget, over);
    assert.equal(state.submittedOverBudget, over);
  }
  // Older pre-hooks without budgets: the scorer's transcript summary supplies them.
  const fallback = normalizeTranscript(srTranscript({preHookBudgets: false, calls: SR_CALLS.slice(0, 1), scoring: {score: 1, metadata: {
    outcome: "complete", transcript_summary: {budgets: {tool_calls_limit: 150, output_token_budget: 80000}}}}}));
  assert.equal(fallback.meta.toolLimit, 150);
  assert.equal(fallback.meta.outputTokenBudget, 80000);
  assert.equal(snapshotAt(fallback.beats, 0, fallback.meta).outputLimit, 80000);
  // A refused call over the tool budget is recorded but not counted.
  const exhausted = normalizeTrace([{tool: "list_documents", request_id: "r151", counted: false, outcome_code: "BUDGET_EXCEEDED",
    envelope: {ok: false, tool: "list_documents", error: {code: "BUDGET_EXCEEDED", message: "used up"}}}]);
  const spent = snapshotAt(exhausted, 1);
  assert.equal(spent.budgetExhausted, true);
  assert.equal(spent.toolUsed, 0);
  assert.equal(exhausted[1].errorKind, "error");
});

test("an accepted submission over the output budget ends incomplete with the budget reason", () => {
  const calls = [...SR_CALLS.slice(0, 16),
    ["submit_findings", {submission: {findings: [{finding_id: "bad"}]}}, fail("VALIDATION_FAILED", "Submission rejected with 1 problem")],
    SR_CALLS[16]];
  const parsed = normalizeTranscript(srTranscript({calls, outputBudget: 30000, tokens: {17: 21840, 18: 14524}, scoring: {score: 0, metadata: {
    outcome: "incomplete_submission", incomplete_reason: "output_token_budget_exhausted", incomplete_reasons: ["output_token_budget_exhausted"],
    transcript_summary: {output_tokens_before_freeze: 36364, output_tokens_total: 37909}}}}));
  const rejected = parsed.beats.findIndex(beat => beat.kind === "result" && beat.outcome === "VALIDATION_FAILED");
  const accepted = parsed.beats.findIndex(beat => beat.kind === "result" && beat.submitted);
  const atRejected = snapshotAt(parsed.beats, rejected, parsed.meta);
  assert.equal(atRejected.submitted, false);
  assert.deepEqual(atRejected.findings, []);
  assert.equal(atRejected.overOutputBudget, false);
  const atAccepted = snapshotAt(parsed.beats, accepted, parsed.meta);
  assert.equal(atAccepted.submitted, true);
  assert.equal(atAccepted.submittedOverBudget, true);
  assert.equal(atAccepted.completed, false, "the outcome is not known before the scoring event");
  assert.equal(atAccepted.reason, null);
  const state = end(parsed);
  assert.equal(state.completed, false);
  assert.equal(state.reason, "output_token_budget_exhausted");
  assert.equal(state.tokensBeforeFreeze, 36364);
  assert.equal(state.score.score, 0);
  assert.equal(parsed.beats.at(-1).title, "Run ended incomplete · output-token budget exhausted");
  assert.equal(parsed.beats.at(-2).title, "Run incomplete · output-token budget exhausted");
  // Backward seeks recompute everything: no findings or outcome leak from later events.
  assert.deepEqual(snapshotAt(parsed.beats, rejected, parsed.meta), atRejected);
});

test("backward seeks over system-response state are deterministic and leak nothing", () => {
  const parsed = normalizeTranscript(srTranscript()), forward = [];
  for (let i = 0; i < parsed.beats.length; i++) forward.push(snapshotAt(parsed.beats, i, parsed.meta));
  for (let i = parsed.beats.length - 1; i >= 0; i--) assert.deepEqual(snapshotAt(parsed.beats, i, parsed.meta), forward[i]);
  const beforeWitness = parsed.beats.findIndex(beat => beat.kind === "result" && beat.tool === "interview_witness") - 1;
  assert.deepEqual(forward[beforeWitness].witnesses, {});
  assert.equal(forward[beforeWitness].records.response, 0);
  const beforeReturn = parsed.beats.findIndex(beat => beat.kind === "result" && beat.tool === "request_data_return") - 1;
  assert.equal(forward[beforeReturn].refusals, 0);
  assert.deepEqual(forward[beforeReturn].inventory, ["R01"]);
  assert.deepEqual(forward[beforeReturn].returns, []);
});

test("live trace records for the new tools normalise like the finished transcript", () => {
  const replay = resultsOf(normalizeTranscript(srTranscript()).beats);
  const records = srTrace(), beats = normalizeTrace(records.map(record => JSON.stringify(record)).join("\n") + "\n");
  const live = resultsOf(beats);
  const view = beat => [beat.tool, beat.station, beat.docId, beat.errorKind, beat.outcome, beat.notKnown, beat.title, beat.nextCursor];
  assert.deepEqual(live.map(view), replay.map(view));
  assert.ok(beats.filter(beat => beat.kind === "walk").every(beat => beat.text === "…" && beat.live));
  assert.equal(beats.filter(beat => beat.kind === "think" || beat.kind === "tokens").length, 0);
  const liveState = snapshotAt(beats, beats.length - 1), replayState = end(normalizeTranscript(srTranscript()));
  for (const key of ["toolUsed", "toolLimit", "inventory", "routes", "records", "refusals", "clarifications", "witnesses",
    "returns", "enquiries", "submitted", "findings"]) assert.deepEqual(liveState[key], replayState[key], key);
  assert.equal(liveState.outputTokens, 0);
  assert.equal(liveState.outputLimit, null, "live mode cannot know the output budget");
  // Records arriving across polls give the same beats and state as one read.
  const split = [...normalizeTrace(records.slice(0, 5)), ...normalizeTrace(records.slice(5))];
  assert.deepEqual(split, normalizeTrace(records));
  // Live furniture: the listed documents plus records obtained so far.
  const world = worldOf(beats, {toolNames: SR_TOOLS});
  assert.equal(world.documents.length, 15);
  assert.equal(world.documents.find(doc => doc.doc_id === "S05").access, "data_return");
});

test("unknown future tools and records stay inspectable in replay and live", () => {
  const beats = normalizeTrace([{tool: "future_tool", request_id: "r9", args: {x: 1}, outcome_code: "OK",
    envelope: {ok: true, tool: "future_tool", data: {value: 1}}}, {kind: "heartbeat"}]);
  assert.deepEqual(beats.map(beat => [beat.kind, beat.station]), [["walk", "think"], ["result", "think"], ["generic", "think"]]);
  assert.equal(beats[1].title, "future_tool result");
  assert.match(beats[1].text, /"value": 1/);
  assert.ok(worldOf(beats, {}).tools.includes("future_tool"));
  assert.equal(snapshotAt(beats, 2).toolUsed, 1);
});

// Saved system-response runs supplement the synthetic coverage when present.
for (const [relative, results, budget, completed, reason, inventory, refusals, clarify] of [
  ["panel_sr80k/opus55-001", 47, 80000, true, null, 16, 6, 5],
  ["panel_sr80k/haiku45-001", 17, 80000, true, null, 9, 0, 0],
  ["panel_sr_30k/opus55-001", 38, 30000, false, "output_token_budget_exhausted", 15, 4, 3],
  ["sr", 48, 30000, true, null, 16, 2, 0],
]) {
  test(`actual system-response run ${relative} keeps budgets, evidence and outcome`,
    optionalFixture(path.join(relative, "transcript.json")), () => {
    const parsed = normalizeTranscript(load(relative)), state = end(parsed), world = worldOf(parsed.beats, parsed.meta);
    assert.equal(resultsOf(parsed.beats).length, results);
    assert.equal(state.toolUsed, results);
    assert.equal(state.toolLimit, 150);
    assert.equal(state.outputLimit, budget);
    assert.equal(state.completed, completed);
    assert.equal(state.reason, reason);
    assert.equal(state.inventory.length, inventory);
    assert.equal(state.refusals, refusals);
    assert.equal(state.clarifications, clarify);
    assert.equal(world.documents.length, 16);
    assert.deepEqual(world.documents.filter(doc => doc.access === "data_return").map(doc => doc.doc_id).sort(), ["S05", "S06"]);
    assert.equal(world.tools.length, 9);
    if (!completed) assert.equal(state.submittedOverBudget, true);
    const artifacts = fs.readdirSync(path.join(root, relative)).find(name => name.endsWith("_artifacts"));
    const gradeFile = artifacts && path.join(root, relative, artifacts, "grade.json");
    if (gradeFile && fs.existsSync(gradeFile)) {
      const recorded = JSON.parse(fs.readFileSync(gradeFile, "utf8")).trace?.records_by_kind;
      if (recorded) assert.deepEqual({event: state.records.event, entry: state.records.entry, response: state.records.response}, recorded);
    }
  });
}

test("actual system-response isolation probe classifies every hostile call",
  optionalFixture("sr/isolation_probe/transcript.json"), () => {
  const results = resultsOf(normalizeTranscript(load("sr/isolation_probe")).beats);
  const tally = {};
  results.forEach(beat => { tally[beat.outcome || "OK"] = (tally[beat.outcome || "OK"] || 0) + 1; });
  assert.deepEqual(tally, {OK: 12, UNKNOWN_ID: 21, AMBIGUOUS_REQUEST: 3, INVALID_ARGUMENT: 2});
  assert.equal(results.filter(beat => beat.notKnown).length, 2);
  assert.equal(results.filter(beat => beat.errorKind === "clarify").length, 3);
  assert.ok(results.every(beat => beat.station !== "think"));
});

test("actual system-response live trace matches its transcript",
  optionalFixture("panel_sr80k/opus55-001/gb2019-sr80k-opus55-001_artifacts/episode/trace.jsonl"), () => {
  const trace = fs.readFileSync(path.join(root, "panel_sr80k/opus55-001/gb2019-sr80k-opus55-001_artifacts/episode/trace.jsonl"), "utf8");
  const beats = normalizeTrace(trace), live = snapshotAt(beats, beats.length - 1), replay = end(normalizeTranscript(load("panel_sr80k/opus55-001")));
  for (const key of ["toolUsed", "toolLimit", "records", "refusals", "clarifications", "witnesses", "returns", "submitted"]) {
    assert.deepEqual(live[key], replay[key], key);
  }
  assert.deepEqual(live.inventory.slice().sort(), replay.inventory.slice().sort());
  assert.equal(live.findings.length, 45);
});

// ---------------------------------------------------------------------------
// Seeking never shows what the agent had not been shown yet. The layout comes from
// the whole run (so cabinets do not move); labels, categories, access, witness roles
// and asset or room names come from snapshot.revealed at the selected event.

test("labels, categories and access are revealed only by the event that returns them", () => {
  const {beats, meta} = normalizeTranscript(srTranscript());
  const at = index => snapshotAt(beats, index, meta).revealed;
  const resultOf = tool => beats.findIndex(beat => beat.kind === "result" && beat.tool === tool);
  const listing = resultOf("list_documents"), before = at(listing - 1);
  // The task names its document IDs up front; nothing else is known before the catalogue.
  assert.deepEqual(before.documents.map(doc => doc.doc_id), SR_DOCS);
  assert.ok(before.documents.every(doc => doc.access === "unknown" && doc.category === undefined && doc.title === doc.doc_id));
  assert.deepEqual([before.categories, before.witnesses, before.assets, before.rooms, before.dataReturns], [[], [], [], [], []]);
  const listed = at(listing);
  assert.deepEqual(listed.documents.filter(doc => doc.access === "data_return").map(doc => doc.doc_id), ["S05", "S06"]);
  assert.deepEqual(listed.witnesses.map(person => [person.role, person.organisation]),
    [["Control engineer", "National Grid ESO"], ["DNO control engineer", "Distribution Network Operators"]]);
  assert.deepEqual(listed.assets.map(asset => asset.asset_id), ["ESW-400", "HORNSEA-ONE"]);
  assert.deepEqual(listed.rooms.map(room => room.room_id), ["ESO-ENCC"]);
  // S05 is not in the catalogue: its title and category arrive with its data return.
  const received = resultOf("request_data_return"), s05 = index => at(index).documents.find(doc => doc.doc_id === "S05");
  assert.deepEqual([s05(received - 1).title, s05(received - 1).category], ["S05", undefined]);
  assert.deepEqual([s05(received).title, s05(received).category], ["DNO returns", "distribution_records"]);
  // Without a catalogue, a room is named by the log query that returns it, and an
  // UNKNOWN_ID reply's valid IDs mark the return-only records from that event on.
  const probe = normalizeTranscript(srTranscript({calls: [SR_CALLS[4], SR_CALLS[15]]}));
  const results = probe.beats.flatMap((beat, i) => beat.kind === "result" ? [i] : []);
  const probeAt = index => snapshotAt(probe.beats, index, probe.meta).revealed;
  assert.deepEqual([probeAt(results[0] - 1).rooms, probeAt(results[0]).rooms.map(room => room.room_id)], [[], ["ESO-ENCC"]]);
  const returnOnly = index => probeAt(index).documents.filter(doc => doc.access === "data_return").map(doc => doc.doc_id);
  assert.deepEqual([returnOnly(results[1] - 1), returnOnly(results[1])], [[], ["S05", "S06"]]);
  // The whole run still fixes the slots, and the end of the run reveals everything.
  assert.deepEqual(worldOf(beats, meta).documents.map(doc => doc.doc_id), before.documents.map(doc => doc.doc_id));
  assert.deepEqual(at(beats.length - 1), worldOf(beats, meta));
});

test("actual opus 80k run reveals no catalogue metadata before its listing",
  optionalFixture("panel_sr80k/opus55-001/transcript.json"), () => {
  const {beats, meta} = normalizeTranscript(load("panel_sr80k/opus55-001"));
  const listing = beats.findIndex(beat => beat.kind === "result" && beat.tool === "list_documents" && !beat.error);
  const before = snapshotAt(beats, listing - 1, meta).revealed, after = snapshotAt(beats, listing, meta).revealed;
  assert.equal(before.documents.length, 16);
  assert.ok(before.documents.every(doc => doc.access === "unknown" && doc.category === undefined));
  assert.deepEqual([before.categories.length, before.witnesses.length, before.assets.length, before.rooms.length], [0, 0, 0, 0]);
  assert.deepEqual(after.documents.filter(doc => doc.access === "data_return").map(doc => doc.doc_id).sort(), ["S05", "S06"]);
  assert.deepEqual([after.witnesses.length, after.assets.length, after.rooms.length], [5, 3, 1]);
  assert.ok(after.witnesses.every(person => person.role && person.organisation));
});

test("actual isolation probe names rooms and categories only after the calls that return them",
  optionalFixture("sr/isolation_probe/transcript.json"), () => {
  const {beats, meta} = normalizeTranscript(load("sr/isolation_probe"));
  const early = snapshotAt(beats, 16, meta).revealed;
  assert.deepEqual(early.rooms, []);
  assert.deepEqual(early.documents.filter(doc => doc.category).map(doc => doc.doc_id), []);
  // The first UNKNOWN_ID reply lists the requestable IDs; only from then are S05 and S06 return-only.
  const valid = beats.findIndex(beat => beat.outcome === "UNKNOWN_ID" && beat.envelope?.error?.details?.[0]?.valid);
  const returnOnly = index => snapshotAt(beats, index, meta).revealed.documents.filter(doc => doc.access === "data_return").map(doc => doc.doc_id);
  assert.deepEqual([returnOnly(valid - 1), returnOnly(valid)], [[], ["S05", "S06"]]);
  // The room is first named by a control-log reply (an error's list of valid rooms counts).
  const room = beats.findIndex(beat => beat.kind === "result" && beat.tool === "query_control_log" && JSON.stringify(beat.envelope).includes("ESO-ENCC"));
  assert.ok(room > 16);
  assert.deepEqual(snapshotAt(beats, room - 1, meta).revealed.rooms, []);
  assert.deepEqual(snapshotAt(beats, room, meta).revealed.rooms.map(item => item.room_id), ["ESO-ENCC"]);
});

// ---------------------------------------------------------------------------
// Scene and controller rules, exercised without a browser: the canvas is a no-op
// context and the controller runs against a minimal fake DOM.

const scripts = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map(match => match[1]);
const sceneSource = scripts.find(source => source.includes("globalThis.AgentWorldScene ="));
const fakeContext = () => new Proxy({}, {get: (target, key) => key in target ? target[key] : () => {},
  set: (target, key, value) => { target[key] = value; return true; }});
const fakeCanvas = () => ({width: 0, height: 0, style: {}, title: "", getContext: fakeContext, addEventListener() {},
  getBoundingClientRect: () => ({left: 0, top: 0, width: 640, height: 360})});
const sceneContext = vm.createContext({});
vm.runInContext(sceneSource, sceneContext);
const {AgentWorldScene} = sceneContext;
const newScene = () => new AgentWorldScene(fakeCanvas());
// Record what a scene method draws, by wrapping it on the instance.
function spy(scene, method) {
  const calls = [], original = scene[method];
  scene[method] = function (...args) { calls.push(args); return original.apply(this, args); };
  return calls;
}
const glyphWidth = text => String(text).length*4 - 1;
const inside = (box, [x, y, w, h]) => box[0] >= x && box[1] >= y && box[0] + box[2] <= x + w && box[1] + box[3] <= y + h;
const overlaps = (a, b) => a[0] < b[0] + b[2] && b[0] < a[0] + a[2] && a[1] < b[1] + b[3] && b[1] < a[1] + a[3];
const CATEGORIES = ["measurement_data", "network_records", "generator_records", "personnel_accounts",
  "system_operator_records", "distribution_records", "requirements", "analysis_records"];
function largeWorld(docs, witnesses, assets) {
  return {documents: Array.from({length: docs}, (_, i) => ({doc_id: `${"RS"[i % 2]}${String(i + 1).padStart(2, "0")}`,
    category: CATEGORIES[i % CATEGORIES.length], access: i % 7 ? "listed" : "data_return"})),
  categories: CATEGORIES, tools: SR_TOOLS, features: {enquiry: true}, rooms: [{room_id: "ROOM-1"}],
  witnesses: Array.from({length: witnesses}, (_, i) => ({persona_id: `witness-${i + 1}`, role: `Role ${i + 1}`,
    organisation: `Organisation ${i + 1} (ORG${i + 1})`})),
  assets: Array.from({length: assets}, (_, i) => ({asset_id: `ASSET-${i + 1}`, title: `Asset ${i + 1}`}))};
}

for (const [docs, witnesses, assets] of [[16, 5, 3], [30, 10, 8], [80, 14, 12]]) {
  test(`${docs} documents, ${witnesses} witnesses and ${assets} assets stay inside their furniture and legible`, () => {
    const scene = newScene(), world = largeWorld(docs, witnesses, assets);
    scene.setWorld(world);
    const fixed = id => scene.fixed.find(station => station.id === id).box;
    const room = [11, 13, 618, 333], archive = [132, 36, 406, 58], bench = fixed("interview"), panel = [18, 257, 106, 25];
    const shelves = [...scene.cabinets, ...(scene.drawer ? [scene.drawer] : [])];
    const groups = [[shelves, archive], [scene.personas, bench], [[...scene.assetIcons, ...(scene.assetMore ? [scene.assetMore] : [])], panel]];
    for (const [stations, bounds] of groups) {
      for (const station of stations) {
        assert.ok(inside(station.box, bounds) && inside(station.box, room), `${station.id} ${station.box} inside ${bounds}`);
        for (const other of stations) if (other !== station) assert.ok(!overlaps(station.box, other.box), `${station.id} overlaps ${other.id}`);
      }
    }
    for (const shelf of shelves) {
      for (const id of ["catalogue", "enquiry"]) assert.ok(!overlaps(shelf.box, fixed(id)), `${shelf.id} overlaps ${id}`);
      const cab = shelf.cab;
      assert.ok(inside([cab.x, cab.y - 3, cab.w, cab.h + 3], archive), `${shelf.id} drawn inside the archive`);
    }
    // Every full ID fits its plate; every document has a cabinet or is filed in the drawer.
    for (const cabinet of scene.cabinets) assert.ok(glyphWidth(cabinet.id) <= cabinet.cab.w - 4, `${cabinet.id} is legible`);
    const filed = scene.drawer ? scene.drawer.moreDocs.map(doc => doc.doc_id) : [];
    assert.deepEqual([...scene.cabinets.map(cabinet => cabinet.id), ...filed].sort(), world.documents.map(doc => doc.doc_id).sort());
    for (const id of filed) assert.equal(scene.station("request_document", {doc_id: id}).id, "archive-more");
    if (scene.drawer) assert.ok(glyphWidth(`+${filed.length}`) <= scene.drawer.cab.w - 4);
    assert.equal(scene.cabinetRows, docs <= 16 ? 1 : 2);
    assert.equal(Boolean(scene.drawer), docs > 40);
    assert.equal(Boolean(scene.assetMore), assets > 5);
    // Once everything is revealed, every visible ID, organisation tag and overflow count is drawn in full.
    const texts = spy(scene, "text");
    const snapshot = snapshotAt([], -1, {});
    snapshot.revealed = world;
    scene.render({snapshot, progress: .6, reducedMotion: true});
    const drawn = new Set(texts.map(([text]) => String(text)));
    for (const cabinet of scene.cabinets) assert.ok(drawn.has(cabinet.id), `${cabinet.id} plate`);
    const seated = scene.personas.filter(person => person.persona);
    for (const person of seated) assert.ok(drawn.has(person.persona.organisation.match(/\((.+)\)/)[1]), `${person.id} tag`);
    assert.equal(seated.length, Math.min(witnesses, witnesses > 10 ? 9 : 10));
    if (witnesses > 10) assert.ok(drawn.has(`+${witnesses - 9}`));
    if (scene.drawer) assert.ok(drawn.has(`+${filed.length}`));
    if (scene.assetMore) assert.ok(drawn.has(`+${assets - 4}`));
    // Name tags on one line never run together.
    for (const row of [0, 1]) {
      const line = seated.filter(person => person.row === row).map(person => ({cx: person.cx,
        w: glyphWidth(person.persona.organisation.match(/\((.+)\)/)[1])})).sort((a, b) => a.cx - b.cx);
      for (let i = 1; i < line.length; i++) assert.ok(line[i].cx - line[i - 1].cx >= (line[i].w + line[i - 1].w)/2 + 2, "tags apart");
    }
  });
}

test("the office shows only what the agent had been shown at the selected event", () => {
  const {beats, meta} = normalizeTranscript(srTranscript()), scene = newScene();
  scene.setWorld(worldOf(beats, meta));
  const draw = index => {
    const texts = spy(scene, "text"), locks = spy(scene, "padlock");
    scene.render({beat: beats[index], snapshot: snapshotAt(beats, index, meta), progress: .6, reducedMotion: true});
    return {texts: texts.map(([text]) => String(text)), locks: locks.length};
  };
  const listing = beats.findIndex(beat => beat.kind === "result" && beat.tool === "list_documents");
  const before = draw(listing - 1), after = draw(listing);
  // Category bands, witness organisations and the room plate wait for the catalogue.
  for (const label of ["DATA", "NET", "SO", "ESO", "DNO", "ESO-ENCC"]) {
    assert.ok(!before.texts.includes(label), `${label} before the catalogue`);
    assert.ok(after.texts.includes(label), `${label} after the catalogue`);
  }
  assert.ok(before.texts.includes("NO ROOM YET"));
  assert.ok(["R01", "S05", "S12"].every(id => before.texts.includes(id)), "the task's document IDs are known from the start");
  assert.deepEqual([before.locks, after.locks], [0, 2], "S05 and S06 are padlocked once the catalogue omits them");
  // Hover labels and clicks follow the same rule: unlisted slots open their station.
  const s01 = scene.cabinets.find(cabinet => cabinet.id === "S01"), person = scene.personas[0], asset = scene.assetIcons[0];
  scene.reveal(snapshotAt(beats, listing - 1, meta));
  assert.deepEqual([scene.describe(s01).label, scene.describe(person).id, scene.describe(asset).id], ["S01 cabinet", "interview", "assets"]);
  assert.doesNotMatch(scene.describe(person).label, /Control engineer|ESO/);
  scene.reveal(snapshotAt(beats, listing, meta));
  assert.equal(scene.describe(s01).label, "S01 cabinet · S01 record");
  assert.deepEqual([scene.describe(person).id, scene.describe(person).label], ["persona:eso-control-engineer", "Control engineer · National Grid ESO"]);
  assert.equal(scene.describe(asset).label, "ESW-400 · Eaton Socon - Wymondley Main 400 kV circuit");
});

test("the mailbox lands only accepted findings and never celebrates a rejected or over-budget submission", () => {
  const card = {finding_id: "F01", status: "reported"};
  const accepted = {kind: "result", tool: "submit_findings", submitted: true, findings: [card], envelope: {ok: true}};
  const rejected = {kind: "result", tool: "submit_findings", submitted: false, error: true, errorKind: "error",
    outcome: "VALIDATION_FAILED", findings: [{finding_id: "bad"}, {finding_id: "worse"}], envelope: {ok: false}};
  // Arrays made inside the scene's context are copied out for strict comparison.
  const view = state => [Array.from(state.findings, item => item.finding_id), state.accepted, state.landed, state.returned, state.celebrate];
  const mailbox = (beat, snapshot) => view(AgentWorldScene.mailboxState(beat, snapshot));
  assert.deepEqual(mailbox(rejected, {findings: [], submitted: false}), [[], false, false, true, false]);
  for (const outcome of ["INVALID_ARGUMENT", "EPISODE_CLOSED"]) {
    assert.deepEqual(mailbox({...rejected, outcome}, {findings: [card], submitted: true}), [["F01"], true, false, true, false],
      `${outcome} keeps only the findings already accepted`);
  }
  assert.deepEqual(mailbox(accepted, {findings: [card], submitted: true}), [["F01"], true, true, false, true]);
  assert.deepEqual(mailbox(accepted, {findings: [card], submitted: true, submittedOverBudget: true}), [["F01"], true, true, false, false]);
  assert.deepEqual(mailbox({kind: "walk", tool: "submit_findings"}, {findings: [card], submitted: true}), [["F01"], true, false, false, false]);
  assert.deepEqual(mailbox(null, {}), [[], false, false, false, false]);
  // On recorded beats: the rejected attempt is returned, stamped, and its cards stay out of the tray.
  const calls = [...SR_CALLS.slice(0, 16), ["submit_findings", {submission: {findings: [{finding_id: "bad"}]}}, fail("VALIDATION_FAILED", "rejected")], SR_CALLS[16]];
  const {beats, meta} = normalizeTranscript(srTranscript({calls}));
  const index = beats.findIndex(beat => beat.kind === "result" && beat.outcome === "VALIDATION_FAILED"), snapshot = snapshotAt(beats, index, meta);
  assert.deepEqual(view(AgentWorldScene.mailboxState(beats[index], snapshot)), [[], false, false, true, false]);
  const scene = newScene(), texts = spy(scene, "text");
  scene.setWorld(worldOf(beats, meta));
  scene.render({beat: beats[index], snapshot, progress: 1, reducedMotion: true});
  assert.ok(texts.some(([text]) => text === "RETURNED"));
});

test("stations for tools the run did not offer are closed", () => {
  const scene = newScene(), closed = () => Array.from(scene.fixed.filter(station => station.closed), station => station.id);
  scene.setWorld({tools: ["list_documents", "request_document", "run_python", "submit_findings"]});
  assert.deepEqual(closed(), ["enquiry", "frequency", "interview", "assets", "control", "returns"]);
  scene.setWorld({tools: SR_TOOLS, features: {enquiry: true}});
  assert.deepEqual(closed(), []);
  assert.equal(scene.archive.closed, false);
});

// A minimal DOM: enough for the controller to load runs, render the sidebar and poll live.
class FakeNode {
  constructor(tag, text = "") {
    Object.assign(this, {tagName: tag, nodes: [], own: text, dataset: {}, style: {}, attributes: {}, listeners: {},
      hidden: false, value: "", title: "", disabled: false, selectors: new Map()});
    const names = new Set();
    this.classList = {toggle: (name, on = !names.has(name)) => (on ? names.add(name) : names.delete(name), on),
      add: (...list) => list.forEach(name => names.add(name)), remove: (...list) => list.forEach(name => names.delete(name)),
      contains: name => names.has(name)};
  }
  get children() { return this.nodes.filter(node => node.tagName !== "#text"); }
  get textContent() { return this.own + this.nodes.map(node => node.textContent).join(""); }
  set textContent(value) { this.own = String(value); this.nodes = []; }
  get firstElementChild() { return this.querySelector(":first-child"); }
  append(...nodes) { for (const node of nodes) this.nodes.push(typeof node === "string" ? new FakeNode("#text", node) : node); }
  replaceChildren(...nodes) { this.nodes = []; this.own = ""; this.append(...nodes); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  addEventListener(type, listener) { (this.listeners[type] ||= []).push(listener); }
  click() { for (const listener of this.listeners.click || []) listener({target: this, preventDefault() {}}); }
  querySelector(selector) {
    const value = selector.match(/^\[value="(.*)"\]$/);
    if (value) return this.descendants().find(node => node.value === value[1]) || null;
    if (!this.selectors.has(selector)) this.selectors.set(selector, new FakeNode("span"));
    return this.selectors.get(selector);
  }
  descendants() { return this.nodes.flatMap(node => [node, ...node.descendants()]); }
  closest() { return null; }
  focus() { FakeNode.focused = this; }
  getBoundingClientRect() { return {left: 0, top: 0, width: 640, height: 360}; }
  getContext() { return fakeContext(); }
}
// A route may answer {__status, body} to send an error status with a JSON body.
function loadViewer(route, {pathname = "/", hash = ""} = {}) {
  const elements = new Map(), timers = [], requests = [];
  const byId = id => { if (!elements.has(id)) elements.set(id, new FakeNode("div")); return elements.get(id); };
  const tabs = ["story", "raw", "findings"].map(name => Object.assign(byId(`tab-${name}`), {dataset: {tab: name}}));
  const views = ["office", "report", "grades"].map(name => Object.assign(byId(`view-${name}`), {dataset: {view: name}}));
  const document = {getElementById: byId, createElement: tag => new FakeNode(tag), createTextNode: text => new FakeNode("#text", text),
    querySelectorAll: selector => selector === "[data-tab]" ? tabs : selector === "[data-view]" ? views : [], addEventListener() {}};
  const location = {protocol: "http:", pathname, hash, search: "", href: `http://127.0.0.1:8765${pathname}${hash}`};
  const history = {replaceState(state, title, url) { const at = String(url).indexOf("#"); location.hash = at >= 0 ? String(url).slice(at) : ""; }};
  const context = vm.createContext({document, window: {addEventListener() {}}, location, history, URLSearchParams,
    matchMedia: () => ({matches: false, addEventListener() {}}), requestAnimationFrame() {},
    setTimeout: fn => timers.push(fn), clearTimeout() {}});
  const parse = vm.runInContext("JSON.parse", context);
  context.fetch = async url => {
    requests.push(url);
    const value = route(url), status = value === undefined ? 404 : value?.__status ?? 200;
    const body = value?.__status ? value.body : value;
    return {ok: status < 400, status, json: async () => parse(JSON.stringify(body ?? {error: "missing"}))};
  };
  for (const source of scripts) vm.runInContext(source, context);
  return {$: byId, timers, requests, location, viewer: context.agentWorld};
}
const settle = async () => { for (let i = 0; i < 40; i++) await new Promise(resolve => setImmediate(resolve)); };
const replayRoutes = transcript => url => url === "/api/config" ? {} :
  url === "/api/runs" ? {runs: [{path: "sr/transcript.json", run_id: "sr-synthetic", task_id: "gb-2019-system-response"}]} :
  url.startsWith("/api/file") ? transcript : undefined;

test("the backpack and inspectors carry no metadata from later events", async () => {
  const {$, viewer} = loadViewer(replayRoutes(srTranscript()));
  await settle();
  const backpack = () => Object.fromEntries($("inventory").children.map(item => [item.dataset.station, item]));
  const inspect = id => { viewer.inspect(id); return $("detail-body").textContent; };
  const listing = viewer.run.beats.findIndex(beat => beat.kind === "result" && beat.tool === "list_documents");
  viewer.select(listing - 1);
  let items = backpack();
  assert.deepEqual(Object.keys(items), SR_DOCS);
  assert.ok(Object.values(items).every(item => !item.hidden && !item.classList.contains("return-only")));
  assert.equal(items.S05.title, "S05: not obtained yet");
  assert.match(inspect("interview"), /No witnesses listed yet\./);
  assert.match(inspect("control"), /No control rooms listed yet\./);
  assert.match(inspect("assets"), /No asset logs listed yet\./);
  assert.doesNotMatch(inspect("archive"), /data return only/);
  viewer.select(listing);
  items = backpack();
  assert.deepEqual(Object.values(items).filter(item => item.classList.contains("return-only")).map(item => item.dataset.station), ["S05", "S06"]);
  assert.equal(items.S05.title, "S05 · data return only: not obtained yet");
  assert.equal(items.R03.title, "R03 · R03 record · network records: not obtained yet");
  assert.match(inspect("interview"), /Control engineer \(National Grid ESO\): not interviewed yet/);
  assert.match(inspect("control"), /ESO-ENCC: not queried yet/);
  assert.match(inspect("archive"), /S06 · data return only · not obtained yet/);
  // Stepping back withdraws it again.
  viewer.select(listing - 1);
  assert.equal(backpack().S05.classList.contains("return-only"), false);
});

test("a document the task did not name joins the backpack when the run first shows it", async () => {
  const transcript = srTranscript();
  transcript.events[1].metadata.documents = SR_DOCS.filter(id => id !== "S05");
  const {$, viewer} = loadViewer(replayRoutes(transcript));
  await settle();
  const received = viewer.run.beats.findIndex(beat => beat.kind === "result" && beat.docId === "S05");
  const s05 = () => $("inventory").children.find(item => item.dataset.station === "S05");
  viewer.select(received - 1);
  assert.equal(s05().hidden, true);
  assert.equal($("inventory-count").textContent, "1 / 15");
  viewer.select(received);
  assert.equal(s05().hidden, false);
  assert.ok(s05().classList.contains("found") && s05().classList.contains("return-only"));
  assert.equal($("inventory-count").textContent, "2 / 16");
});

test("a live trace reset withdraws the replay offer and restores the live-follow copy", async () => {
  const records = srTrace(), episode = {tool_names: SR_TOOLS, budgets: {tool_calls_limit: 150}};
  const polls = [
    {records: records.slice(0, 3), offset: 300, waiting: false, state: {run_id: "sr-live"}, episode,
      replay: {path: "sr/transcript.json", run_id: "sr-live"}},
    {reset: true, records: records.slice(0, 1), offset: 100, waiting: false, state: {run_id: "sr-live-2"}, episode},
  ];
  const {$, timers, viewer} = loadViewer(url => url === "/api/config" ? {live: true, episode_dir: "episode"} :
    url === "/api/runs" ? {runs: []} : url.startsWith("/api/live") ? polls.shift() || {records: [], offset: 100, waiting: false} : undefined);
  await settle();
  assert.equal(viewer.mode, "live");
  assert.equal(viewer.run.beats.length, 6);
  assert.equal($("full-replay").hidden, false);
  assert.equal($("live-copy").textContent, "The full transcript is ready, including reasoning and token usage.");
  timers.shift()();
  await settle();
  assert.equal(viewer.run.beats.length, 2);
  assert.equal($("full-replay").hidden, true);
  assert.match($("live-copy").textContent, /^Live follows tool calls every 500 ms\./);
  assert.doesNotMatch($("live-copy").textContent, /ready/);
});

// ---------------------------------------------------------------------------
// Full investigation (gb-2019-full-investigation): 22 documents in twelve categories,
// ten witnesses, four control rooms (three new), REMIT asset-log rows whose value may be
// null, many not-held data returns, the report sections, the 200k context cap and a
// grade the runner truncated. Synthetic envelopes as the ledger records them.

const FI_TASK = "gb-2019-full-investigation";
const FI_CATEGORY = {R01: "measurement_data", R02: "measurement_data", R03: "network_records", R04: "measurement_data",
  R05: "measurement_data", R06: "system_operator_records", R07: "distribution_records", R08: "system_operator_records",
  R09: "communications_records", R10: "requirements", R11: "transport_records", R12: "essential_services",
  S01: "generator_records", S03: "generator_records", S04: "personnel_accounts", S05: "distribution_records",
  S06: "distribution_records", S07: "system_operator_records", S08: "transport_records", S10: "compliance_records",
  S11: "essential_services", S12: "analysis_records"};
const FI_DOCS = Object.keys(FI_CATEGORY);
const FI_LISTED = FI_DOCS.filter(id => !["S05", "S06"].includes(id));
const FI_CATEGORIES = ["measurement_data", "network_records", "generator_records", "personnel_accounts",
  "system_operator_records", "distribution_records", "requirements", "analysis_records", "transport_records",
  "essential_services", "communications_records", "compliance_records"];
const FI_WITNESSES = [
  ["dno-control-engineer", "Control engineer, distribution network operator", "Distribution Network Operators"],
  ["eso-communications-lead", "Communications lead, National Grid ESO", "National Grid ESO"],
  ["eso-control-engineer", "Control engineer, ESO Electricity National Control Centre (ENCC)", "National Grid ESO"],
  ["gtr-fleet-engineer", "Fleet engineer, Govia Thameslink Railway (GTR) fleet control", "Govia Thameslink Railway (GTR)"],
  ["hospital-estates-manager", "Estates manager, Ipswich Hospital", "East Suffolk and North Essex NHS Foundation Trust"],
  ["network-rail-control-manager", "Control duty manager, Network Rail", "Network Rail"],
  ["nget-protection-engineer", "Protection engineer, transmission owner", "National Grid Electricity Transmission (NGET)"],
  ["orsted-hornsea-operations-engineer", "Operations engineer, Hornsea One offshore wind farm", "Ørsted"],
  ["rwe-lb-shift-charge-engineer", "Shift charge engineer, Little Barford power station", "RWE Generation"],
  ["ukpn-epn-spn-control-engineer", "Control engineer, UK Power Networks", "UK Power Networks"],
].map(([persona_id, role, organisation]) => ({persona_id, role, organisation, evidence_id: "S09"}));
const FI_ROOMS = [
  {room_id: "ESO-COMMS", title: "ESO communications: contacts with government and the regulator, media statements and public posts", evidence_ids: ["R09"]},
  {room_id: "ESO-ENCC", title: "ESO Electricity National Control Centre (ENCC)", evidence_ids: ["R06", "R08", "S07"]},
  {room_id: "GTR-FLEET-CONTROL", title: "GTR fleet control: technical-review entries with a printed clock time", evidence_ids: ["S08"]},
  {room_id: "NETWORK-RAIL-CONTROL", title: "Network Rail: delay-attribution incident records (TRUST), 9 August 2019", evidence_ids: ["R11"]},
];
const FI_ASSETS = [
  {asset_id: "ESW-400", title: "Eaton Socon - Wymondley Main 400 kV circuit: record entries"},
  {asset_id: "HORNSEA-ONE", title: "Hornsea One offshore wind farm: event log entries, BM unit data, REMIT messages and chart readings"},
  {asset_id: "LITTLE-BARFORD", title: "Little Barford power station: sequence-of-events entries, BM unit data and REMIT messages"},
];
const REMIT = "T_LBAR-1 REMIT declared available capacity for event window MW";
const FI_WINDOW = {start: "2019-08-09T16:00:00+00:00", end: "2019-08-09T17:30:00+00:00", rule: "index_time_utc >= start and < end"};
const entry = (entry_id, evidence_id, room_id, recorded_time, from, to, text) =>
  ({entry_id, evidence_id, room_id, recorded_time, from, to, text, value_status: "reported"});
const notHeld = (party, data_type) => fail("NOT_HELD", `${party} / ${data_type}: Not held in this evidence pack.`,
  [{party, data_type, status: "not_held"}]);
const FI_REPORT = {executive_summary: "At 16:52:33 BST a lightning strike caused a fault [F01]. Rail services were disrupted [F02].",
  sections: [{heading: "Chronology", body: "16:52:33 fault [F01]."}, {heading: "Recommendations", body: "GTR to review recovery procedures; verified by a drill [F02]."},
    {heading: "Further evidence requests", body: "Network Rail: train running records [F02]."}]};
const FI_FINDINGS = [{finding_id: "F01", status: "reported", statement: "A lightning strike caused the fault."},
  {finding_id: "F02", status: "reported", statement: "ORR reports 29 trains locked out."}];
const FI_CALLS = [
  ["list_documents", {}, {data: {documents: FI_LISTED.map(id => ({doc_id: id, title: `${id} record`, category: FI_CATEGORY[id]})),
    categories: FI_CATEGORIES, total: 20, asset_logs: FI_ASSETS, control_logs: FI_ROOMS, witnesses: FI_WITNESSES,
    data_returns: [{party: "NETWORK_RAIL", data_type: "train_running_records"}, {party: "DNO", data_type: "lfdd_disconnection_and_restoration_returns"}]}}],
  ["query_control_log", {room: "ESO-COMMS", start: FI_WINDOW.start, end: FI_WINDOW.end}, {evidence: ["R09"], data: {
    room: "ESO-COMMS", title: FI_ROOMS[0].title, window: FI_WINDOW, total_rows: 2, offset: 0, returned: 2,
    rows: [entry("R09-A2-1", "R09", "ESO-COMMS", "17:40", "ESO", "BEIS", "ESO contacted BEIS at 17:40 [reported]."),
      entry("R09-A2-2", "R09", "ESO-COMMS", "18:00", "ESO", "Ofgem", "ESO contacted Ofgem at 18:00 [reported].")]}}],
  ["query_control_log", {room: "NETWORK-RAIL-CONTROL", start: FI_WINDOW.start, end: FI_WINDOW.end}, {evidence: ["R11"], data: {
    room: "NETWORK-RAIL-CONTROL", title: FI_ROOMS[3].title, window: FI_WINDOW, total_rows: 1, offset: 0, returned: 1,
    rows: [entry("R11-NR-224917", "R11", "NETWORK-RAIL-CONTROL", "incident_start_datetime 09/08/2019 17:01", "Network Rail (TRUST delay attribution)",
      "responsible manager XQFM (North West)", "incident 224917 | reason XK (NATL GRID) | ROCK FERRY : BIRKENHEAD CENTRAL")]}}],
  ["query_control_log", {room: "GTR-FLEET-CONTROL", start: FI_WINDOW.start, end: FI_WINDOW.end}, {evidence: ["S08"], data: {
    room: "GTR-FLEET-CONTROL", title: FI_ROOMS[2].title, window: FI_WINDOW, total_rows: 1, offset: 0, returned: 1,
    rows: [entry("S08-G01", "S08", "GTR-FLEET-CONTROL", "17:28", "GTR fleet control", "GTR", "Technician dispatch entry [reported].")]}}],
  ["query_asset_log", {asset_id: "LITTLE-BARFORD", signal: REMIT, start: "2019-08-08T00:00:00Z", end: "2019-08-10T00:00:00Z"}, {evidence: ["R09"], data: {
    asset_id: "LITTLE-BARFORD", title: FI_ASSETS[2].title, signal: REMIT, window: FI_WINDOW, total_rows: 2, offset: 0, returned: 2,
    rows: [{event_id: "R09-REMIT-00056749-r1", evidence_id: "R09", recorded_time: "publishTime 2019-08-08T15:44:17Z", signal: REMIT,
      value: null, unit: "MW", value_status: "reported", text: "REMIT message published: publishTime 2019-08-08T15:44:17Z | T_LBAR-1 | status Active | event 2019-08-09T22:01:07Z to 2019-08-10T14:13:29Z | normal 735.0 MW, available 350.0 MW"},
    {event_id: "R09-REMIT-00056773-r1", evidence_id: "R09", recorded_time: "publishTime 2019-08-09T16:54:44Z", signal: REMIT,
      value: 0.0, unit: "MW", value_status: "reported", text: "REMIT message published: publishTime 2019-08-09T16:54:44Z | T_LBAR-1 | available 0.0 MW"}]}}],
  ["interview_witness", {persona_id: "gtr-fleet-engineer", question: "Which software versions were the units on?"}, {evidence: ["S09"], data: {
    ...FI_WITNESSES[3], matched: true, response_id: "S09-GTR-05", topics: ["software levels"], response_text: "Units at 3.25 or below needed a technician."}}],
  ["interview_witness", {persona_id: "ukpn-epn-spn-control-engineer", question: "What was the weather?"}, {data: {
    ...FI_WITNESSES[9], matched: false, response_id: null, topics: [], response_text: "Not known to me."}}],
  ["interview_witness", {persona_id: "hospital-estates-manager", question: "Was the hospital inside the LFDD zone?"}, {evidence: ["S09"], data: {
    ...FI_WITNESSES[4], matched: true, response_id: "S09-HOSP-01", topics: ["LFDD"], response_text: "The hospital was not disconnected by LFDD."}}],
  ["request_data_return", {party: "NETWORK_RAIL", data_type: "train_running_records"}, notHeld("NETWORK_RAIL", "train_running_records")],
  ["request_data_return", {party: "NEWCASTLE_AIRPORT", data_type: "airport_power_and_incident_logs"}, notHeld("NEWCASTLE_AIRPORT", "airport_power_and_incident_logs")],
  ["request_data_return", {party: "WATER_COMPANY", data_type: "pumping_station_and_treatment_works_logs"}, notHeld("WATER_COMPANY", "pumping_station_and_treatment_works_logs")],
  ["request_data_return", {party: "REFINERY_OPERATOR", data_type: "site_trip_and_shutdown_logs"}, notHeld("REFINERY_OPERATOR", "site_trip_and_shutdown_logs")],
  ["request_data_return", {party: "ELEXON", data_type: "physical_notifications_event_window"}, notHeld("ELEXON", "physical_notifications_event_window")],
  ["request_data_return", {party: "RWE", data_type: "grid_code_compliance_test_records"}, notHeld("RWE", "grid_code_compliance_test_records")],
  ["request_data_return", {party: "ORSTED", data_type: "grid_code_compliance_test_records"}, notHeld("ORSTED", "grid_code_compliance_test_records")],
  ["request_data_return", {party: "DNO", data_type: "lfdd_disconnection_and_restoration_returns"}, {evidence: ["S05"], data: {doc_id: "S05",
    title: "DNO returns", category: "distribution_records", content: "S05 text", party: "DNO", return_status: "available"}}],
  ["request_document", {doc_id: "S08"}, {evidence: ["S08"], data: {doc_id: "S08", title: "Rail fleet and service records", category: "transport_records", content: "S08 text"}}],
  ["request_document", {party: "Ofgem", description: "compliance process records"}, {evidence: ["S10"], data: {doc_id: "S10",
    title: "Generator and network compliance-process records", category: "compliance_records", content: "S10 text",
    matched_by: {matcher_version: "doc-tokens-2", party: "Ofgem", description: "compliance process records", description_score: 1, party_score: 1}}}],
  ["request_document", {doc_id: "R09"}, {evidence: ["R09"], data: {doc_id: "R09", title: "External communications records", category: "communications_records", content: "R09 text"}}],
  ["submit_findings", {submission: {findings: [{finding_id: "bad"}], report: {executive_summary: "Draft [F99].", sections: [{heading: "Draft", body: "x"}]}}},
    fail("VALIDATION_FAILED", "Submission rejected with 5 problems")],
  ["submit_findings", {submission: {findings: FI_FINDINGS, report: FI_REPORT}}, {data: {status: "accepted_and_frozen", findings_count: 2}}],
];
const FI_TRUNCATED = "{'status': 'graded', 'grade': {'grade_schema': 'gb2019-fi-grade/1', 'citations': [\n[... truncated: exceeded 1048576 characters ...]\n], 'task_id': 'gb-2019-full-investigation'}, 'grade_file': '/root_data/episode/grade.json'}";

// Input tokens per turn (before the numbered call): the context cap applies to one turn.
function fiTranscript({calls = FI_CALLS, tokens = {2: [60000, 1500], 10: [140000, 3000], 21: [175269, 9000]}, grading = FI_TRUNCATED,
  outcome = "complete"} = {}) {
  const events = [
    {type: "task_started", run_id: "fi-synthetic", task_id: FI_TASK, model: "test-model", timestamp: "2026-10-20T10:00:00Z"},
    {type: "task_pre_hook_completed", metadata: {task_id: FI_TASK, manifest_version: 2, tool_names: SR_TOOLS, documents: FI_DOCS,
      budgets: {max_tool_calls: 150, output_token_budget: 80000, context_cap_tokens: 200000, exec_summary_word_limit: 600}}},
  ];
  calls.forEach(([tool, args, spec], i) => {
    const id = `c${i + 1}`, envelope = srEnvelope(tool, i + 1, spec);
    events.push({type: "message_added", message: {role: "assistant", tool_calls: [call(id, tool, args)]}});
    if (tokens[i + 1]) events.push({type: "token_usage", input_tokens: tokens[i + 1][0], output_tokens: tokens[i + 1][1]});
    events.push({type: "tool_call_started", tool_call: call(id, tool, args)});
    events.push(done(id, envelope, {structuredContent: envelope}));
  });
  events.push({type: "scoring", scoring: {score: outcome === "complete" ? 1 : 0, metadata: {outcome, provisional: true, grading,
    transcript_summary: {budgets: {tool_calls_limit: 150, output_token_budget: 80000, context_cap_tokens: 200000}}}}},
  {type: "task_completed", status: outcome === "complete" ? "passed" : "failed"});
  return {run_id: "fi-synthetic", events};
}
const fiTrace = () => srTrace(FI_CALLS);

test("full-investigation rooms, REMIT rows, witnesses and refusals normalise to their stations and records", () => {
  const parsed = normalizeTranscript(fiTranscript()), results = resultsOf(parsed.beats), state = end(parsed);
  assert.equal(results.length, FI_CALLS.length);
  assert.deepEqual(results.slice(1, 5).map(beat => beat.station), ["control", "control", "control", "assets"]);
  assert.match(results[1].title, /^ESO-COMMS · 2 rows$/);
  assert.match(results[2].text, /R11-NR-224917 \[reported\]/);
  assert.match(results[3].title, /^GTR-FLEET-CONTROL · 1 row$/);
  // The renamed REMIT signal is shown whole; a null value is stated and its row text kept.
  const walk = parsed.beats.find(beat => beat.kind === "walk" && beat.tool === "query_asset_log");
  assert.ok(walk.text.includes(REMIT));
  assert.match(results[4].text, /1 row on this page has a unit but a null value\./);
  assert.match(results[4].text, /publishTime 2019-08-08T15:44:17Z · T_LBAR-1 REMIT declared available capacity for event window MW · value null · REMIT message published: .*available 350\.0 MW · R09-REMIT-00056749-r1 \[reported\]/);
  assert.match(results[4].text, /T_LBAR-1 REMIT declared available capacity for event window MW = 0 MW · R09-REMIT-00056773-r1/);
  assert.equal(results[6].notKnown, true);
  assert.deepEqual(results.slice(8, 15).map(beat => [beat.outcome, beat.errorKind]), Array(7).fill(["NOT_HELD", "refusal"]));
  assert.match(results[17].title, /S10 received by description/);
  assert.deepEqual(state.inventory, ["S05", "S08", "S10", "R09"]);
  assert.deepEqual(state.records, {event: 2, entry: 4, response: 2, frequencyRows: 0});
  assert.deepEqual(Object.fromEntries(Object.entries(state.rooms).map(([id, room]) => [id, room.rows])),
    {"ESO-COMMS": 2, "NETWORK-RAIL-CONTROL": 1, "GTR-FLEET-CONTROL": 1});
  assert.equal(state.assets["LITTLE-BARFORD"].rows, 2);
  assert.equal(state.refusals, 7);
  assert.deepEqual(state.witnesses["gtr-fleet-engineer"].responses, ["S09-GTR-05"]);
  assert.equal(state.witnesses["ukpn-epn-spn-control-engineer"].notKnown, 1);
  assert.equal(state.submissions.rejected, 1);
  assert.equal(state.completed, true);
});

test("full-investigation furniture comes from the run: 22 documents, twelve categories, ten witnesses, four rooms", () => {
  const parsed = normalizeTranscript(fiTranscript()), world = worldOf(parsed.beats, parsed.meta);
  assert.equal(parsed.meta.taskId, FI_TASK);
  assert.deepEqual(world.documents.map(doc => doc.doc_id), FI_DOCS);
  assert.deepEqual(world.documents.filter(doc => doc.access === "data_return").map(doc => doc.doc_id), ["S05", "S06"]);
  assert.deepEqual(world.categories.slice().sort(), FI_CATEGORIES.slice().sort());
  assert.equal(world.witnesses.length, 10);
  assert.deepEqual(world.rooms.map(room => room.room_id), FI_ROOMS.map(room => room.room_id));
  assert.deepEqual(world.assets.map(asset => asset.asset_id), ["ESW-400", "HORNSEA-ONE", "LITTLE-BARFORD"]);
  assert.ok(world.dataReturns.some(item => item.party === "WATER_COMPANY"), "a refused pair joins the registry");
  // Before the listing only the task's IDs are known; the rooms come with the catalogue.
  const listing = parsed.beats.findIndex(beat => beat.kind === "result" && beat.tool === "list_documents");
  const before = snapshotAt(parsed.beats, listing - 1, parsed.meta).revealed;
  assert.equal(before.documents.length, 22);
  assert.deepEqual([before.rooms, before.witnesses, before.categories], [[], [], []]);
  assert.equal(snapshotAt(parsed.beats, listing, parsed.meta).revealed.rooms.length, 4);
});

test("the context cap is per turn: the latest and largest turn are kept, and seeking recomputes them", () => {
  const parsed = normalizeTranscript(fiTranscript());
  assert.equal(parsed.meta.contextCap, 200000);
  assert.equal(parsed.meta.summaryWordLimit, 600);
  assert.match(parsed.beats.find(beat => beat.title === "Office ready").text, /80,000-token output budget · 200,000-token context cap/);
  const turn = n => parsed.beats.findIndex(beat => beat.kind === "tokens" && beat.tokens.input === n);
  const at = index => snapshotAt(parsed.beats, index, parsed.meta);
  assert.deepEqual([at(turn(60000) - 1).lastInputTokens, at(turn(60000) - 1).peakInputTokens, at(turn(60000) - 1).tokenTurns], [null, null, 0]);
  const middle = at(turn(140000));
  assert.deepEqual([middle.lastInputTokens, middle.peakInputTokens, middle.tokenTurns, middle.inputTokens], [140000, 140000, 2, 200000]);
  assert.equal(middle.contextLimit, 200000);
  assert.equal(middle.contextReached, false);
  const last = end(parsed);
  assert.deepEqual([last.lastInputTokens, last.peakInputTokens, last.tokenTurns, last.outputTokens], [175269, 175269, 3, 13500]);
  assert.deepEqual(at(turn(140000)), middle, "seeking back gives the same state");
  // The producer's rule: the latest turn meeting the cap reaches it, an earlier one does not count.
  const capped = normalizeTranscript(fiTranscript({tokens: {2: [200000, 10], 5: [150000, 10]}}));
  const peak = capped.beats.findIndex(beat => beat.kind === "tokens" && beat.tokens.input === 200000);
  assert.equal(snapshotAt(capped.beats, peak, capped.meta).contextReached, true);
  assert.deepEqual([end(capped).contextReached, end(capped).peakInputTokens], [false, 200000]);
});

test("the accepted report travels with its findings; a rejected attempt's report never shows", () => {
  const parsed = normalizeTranscript(fiTranscript());
  const rejected = parsed.beats.findIndex(beat => beat.kind === "result" && beat.outcome === "VALIDATION_FAILED");
  const accepted = parsed.beats.findIndex(beat => beat.kind === "result" && beat.submitted);
  assert.equal(snapshotAt(parsed.beats, rejected, parsed.meta).report, null);
  const state = snapshotAt(parsed.beats, accepted, parsed.meta);
  assert.equal(state.report.executive_summary, FI_REPORT.executive_summary);
  assert.deepEqual(state.report.sections.map(section => section.heading), ["Chronology", "Recommendations", "Further evidence requests"]);
  assert.equal(snapshotAt(parsed.beats, accepted - 1, parsed.meta).report, null, "seeking back withdraws it");
  assert.equal(normalizeTranscript(srTranscript()).beats.find(beat => beat.submitted).report, null, "a submission without a report has none");
});

test("a grade the runner truncated, or a grading error, is recognised from the scoring record and not read", () => {
  const truncated = normalizeTranscript(fiTranscript());
  assert.equal(truncated.meta.embeddedGrade, null);
  assert.deepEqual({...truncated.meta.gradingRecord}, {status: "graded", error: null, truncated: true, text: true});
  const failed = normalizeTranscript(fiTranscript({grading: {status: "error", error: "GradingError: cannot load the answer key"}}));
  assert.deepEqual([failed.meta.gradingRecord.status, failed.meta.gradingRecord.error], ["error", "GradingError: cannot load the answer key"]);
  const graded = normalizeTranscript(fiTranscript({grading: {status: "graded", grade: {grade_schema: "gb2019-fi-grade/1"}}}));
  assert.equal(graded.meta.embeddedGrade.grade_schema, "gb2019-fi-grade/1");
  assert.equal(normalizeTranscript(srTranscript()).meta.gradingRecord, null);
});

test("backward seeks over full-investigation state are deterministic and leak nothing", () => {
  const parsed = normalizeTranscript(fiTranscript()), forward = [];
  for (let i = 0; i < parsed.beats.length; i++) forward.push(snapshotAt(parsed.beats, i, parsed.meta));
  for (let i = parsed.beats.length - 1; i >= 0; i--) assert.deepEqual(snapshotAt(parsed.beats, i, parsed.meta), forward[i]);
  const beforeRail = parsed.beats.findIndex(beat => beat.kind === "result" && beat.args?.room === "NETWORK-RAIL-CONTROL") - 1;
  assert.deepEqual(Object.keys(forward[beforeRail].rooms), ["ESO-COMMS"]);
  const beforeReturns = parsed.beats.findIndex(beat => beat.kind === "result" && beat.tool === "request_data_return") - 1;
  assert.equal(forward[beforeReturns].refusals, 0);
  assert.deepEqual(forward[beforeReturns].returns, []);
});

test("a full-investigation live trace normalises like the finished transcript", () => {
  const replay = normalizeTranscript(fiTranscript()), records = fiTrace();
  const beats = normalizeTrace(records.map(record => JSON.stringify(record)).join("\n") + "\n");
  // Live envelopes carry no rendered content, so only the submission's text differs.
  const view = beat => [beat.tool, beat.station, beat.docId, beat.errorKind, beat.outcome, beat.notKnown, beat.title,
    beat.submitted ? "" : beat.text];
  assert.deepEqual(resultsOf(beats).map(view), resultsOf(replay.beats).map(view));
  const live = snapshotAt(beats, beats.length - 1), finished = end(replay);
  for (const key of ["toolUsed", "toolLimit", "inventory", "routes", "records", "refusals", "rooms", "assets", "witnesses",
    "returns", "enquiries", "submitted", "findings", "report"]) assert.deepEqual(live[key], finished[key], key);
  assert.deepEqual([live.contextLimit, live.lastInputTokens, live.outputLimit], [null, null, null], "live mode has no token data");
  assert.deepEqual(worldOf(beats, {toolNames: SR_TOOLS}).rooms.map(room => room.room_id), FI_ROOMS.map(room => room.room_id));
  assert.deepEqual([...normalizeTrace(records.slice(0, 7)), ...normalizeTrace(records.slice(7))], normalizeTrace(records));
});

test("the office fits the full investigation: twelve bays, ten named witnesses, four room screens, whole asset IDs", () => {
  const {beats, meta} = normalizeTranscript(fiTranscript()), scene = newScene(), world = worldOf(beats, meta);
  scene.setWorld(world);
  assert.equal(scene.cabinetRows, 2);
  assert.equal(scene.drawer, null, "22 documents need no overflow drawer");
  // Twelve category bays from the opening listing, plus one unnamed bay for the two
  // data-return documents, which no listing shows: S06 is never obtained and S05's
  // category comes only with its later data return, so it does not move S05's cabinet.
  assert.deepEqual(Array.from(scene.groups.filter(group => !group.category), group => Array.from(group.docs)), [["S05", "S06"]]);
  assert.equal(scene.groups.filter(group => group.category).length, 12);
  const control = scene.fixed.find(station => station.id === "control").box;
  assert.deepEqual(Array.from(scene.screens, screen => [screen.id, screen.tag]),
    [["room:ESO-COMMS", "COMMS"], ["room:ESO-ENCC", "ENCC"], ["room:GTR-FLEET-CONTROL", "FLEET"], ["room:NETWORK-RAIL-CONTROL", "RAIL"]]);
  for (const screen of scene.screens) {
    assert.ok(inside(screen.box, control), `${screen.id} inside the control room`);
    for (const other of scene.screens) if (other !== screen) assert.ok(!overlaps(screen.box, other.box));
    assert.ok(glyphWidth(screen.tag) <= screen.box[2] - 2, `${screen.tag} fits its screen`);
  }
  const draw = index => {
    const texts = spy(scene, "text");
    scene.render({beat: beats[index], snapshot: snapshotAt(beats, index, meta), progress: .6, reducedMotion: true});
    return texts.map(([text]) => String(text));
  };
  const listing = beats.findIndex(beat => beat.kind === "result" && beat.tool === "list_documents");
  const before = draw(listing - 1), after = draw(listing);
  for (const label of ["TRAN", "ESS", "COMM", "COMP", "COMMS", "ENCC", "FLEET", "RAIL", "UKPN", "NHS", "NR", "DNO", "GTR", "NGET", "ORSTED", "RWE"]) {
    assert.ok(!before.includes(label), `${label} before the catalogue`);
    assert.ok(after.includes(label), `${label} after the catalogue`);
  }
  assert.ok(!after.includes("UK"), "UK Power Networks is UKPN");
  // The plate and terminal carry whole IDs; a full refusal spike counts its slips.
  const rail = beats.findIndex(beat => beat.kind === "result" && beat.args?.room === "NETWORK-RAIL-CONTROL");
  assert.ok(draw(rail).includes("NETWORK-RAIL-CONTROL"));
  const remit = beats.findIndex(beat => beat.kind === "result" && beat.tool === "query_asset_log");
  assert.ok(draw(remit).includes("LITTLE-BARFORD"));
  const refusals = beats.findIndex(beat => beat.kind === "result" && beat.args?.party === "ORSTED");
  assert.ok(draw(refusals).includes("7"));
  assert.ok(!draw(refusals - 2).includes("7"), "the count appears only past six slips");
  // Room screens are inspectable once named; before that they open the control room.
  const screen = scene.screens.find(item => item.id === "room:NETWORK-RAIL-CONTROL");
  scene.reveal(snapshotAt(beats, listing - 1, meta));
  assert.deepEqual([scene.describe(screen).id, scene.describe(screen).label], ["control", "Control room · a room not listed yet"]);
  scene.reveal(snapshotAt(beats, listing, meta));
  assert.deepEqual([scene.describe(screen).id, scene.describe(screen).label],
    ["room:NETWORK-RAIL-CONTROL", `NETWORK-RAIL-CONTROL · ${FI_ROOMS[3].title}`]);
});

test("past four control rooms the last screen holds the rest, and increment A's single room still fits", () => {
  const scene = newScene(), rooms = Array.from({length: 6}, (_, i) => ({room_id: `ROOM-${i + 1}`}));
  scene.setWorld({tools: SR_TOOLS, rooms});
  assert.deepEqual(Array.from(scene.screens, screen => screen.id), ["room:ROOM-1", "room:ROOM-2", "room:ROOM-3", "control-more"]);
  assert.deepEqual(Array.from(scene.screens[3].moreRooms, room => room.room_id), ["ROOM-4", "ROOM-5", "ROOM-6"]);
  scene.reveal({revealed: {rooms: rooms.slice(0, 5)}});
  assert.deepEqual([scene.describe(scene.screens[3]).id, scene.describe(scene.screens[3]).label], ["control", "2 more control rooms · open the control-room list"]);
  const texts = spy(scene, "text");
  scene.render({snapshot: {revealed: {rooms: rooms.slice(0, 5)}, rooms: {}}, progress: .6, reducedMotion: true});
  assert.ok(texts.some(([text]) => text === "+2"));
  scene.setWorld({tools: SR_TOOLS, rooms: [{room_id: "ESO-ENCC"}]});
  assert.deepEqual(Array.from(scene.screens, screen => [screen.id, screen.tag]), [["room:ESO-ENCC", "ENCC"]]);
});

const fiGrade = (words = 570) => ({grade_schema: "gb2019-fi-grade/1", task_id: FI_TASK, status: "provisional",
  key: {review_status: "pending_domain_review"}, flags: {uncited_findings: [], needs_human_review: ["T10.01", "T15.02"],
    executive_summary: {words, limit: 600, within_limit: words <= 600}},
  content_coverage: {sources: {"T10.01": "pending", "T03.01": "auto"}}, provisional_reasons: ["answer key review status is 'pending_domain_review'"]});
const fiRoutes = (transcript, grade = fiGrade(), judge = null) => url => url === "/api/config" ? {} :
  url === "/api/runs" ? {runs: [{path: "fi/reference/transcript.json", run_id: "fi-synthetic", task_id: FI_TASK, grade, judge}]} :
  url.startsWith("/api/file") ? transcript : undefined;

test("grading notes appear only from the scoring event, with the full investigation's summary count", async () => {
  const {$, viewer} = loadViewer(fiRoutes(fiTranscript()));
  await settle();
  const scored = viewer.run.beats.findIndex(beat => beat.kind === "score");
  viewer.select(scored - 1);
  assert.match($("grade-note").textContent, /appear when the replay reaches the scoring event/);
  assert.equal($("grade-jump").hidden, false);
  assert.equal($("grade-flags").children.length, 0, "no flags before the scoring event");
  $("grade-jump").click();
  assert.equal(viewer.index, scored);
  assert.match($("grade-note").textContent, /^Grade provisional · answer key pending domain review\./);
  assert.match($("grade-note").textContent, /Executive summary 570 words \(limit 600\)\./);
  assert.match($("grade-note").textContent, /Content criteria: 1 awaiting a human decision \(1 with no judge value yet\) · 1 decided by automated checks\./);
  assert.match($("grade-judge").textContent, /No LLM judge proposals were recorded for this run\./);
  assert.ok($("grade-flags").children.some(badge => badge.textContent === "2 need human review"));
  assert.equal($("grade-jump").hidden, true);
  viewer.select(0);
  assert.doesNotMatch($("grade-note").textContent, /Executive summary/, "seeking back withdraws the grade");
  // Over the limit, and a judge recorded with per-topic requests. The judged grade
  // (the run's grade with the judge's proposals merged) supersedes the run's grade.
  const judged = loadViewer(fiRoutes(fiTranscript(), fiGrade(570), {judge_model: "openai/gpt-6.1-sol", rubric_version: "1.0.0",
    status: "judged", units: 20, scope: "topic", grade: {...fiGrade(640), content_coverage: {sources: {"T10.01": "judge", "T03.01": "auto"}}}}));
  await settle();
  judged.viewer.select(judged.viewer.run.beats.length - 1);
  assert.ok(judged.$("grade-flags").children.some(badge => badge.textContent === "summary over 600 words"));
  // A judge proposal still awaits a human decision, as the Grades tab counts it.
  assert.match(judged.$("grade-note").textContent, /Content criteria: 1 awaiting a human decision \(1 judge proposal\) · 1 decided by automated checks\./);
  assert.match(judged.$("grade-judge").textContent, /20 units, scoped per topic\./);
  assert.equal(judged.$("grade-open").hidden, false, "the grading panel opens the Grades tab");
});

test("an imported full-investigation transcript explains its truncated grade instead of hiding it", async () => {
  const {$, viewer} = loadViewer(fiRoutes(fiTranscript(), null));
  await settle();
  viewer.select(viewer.run.beats.length - 1);
  assert.match($("grade-note").textContent, /cut short by the runner's 1 MiB limit .* grade\.json holds the full grade\./);
  const failed = loadViewer(fiRoutes(fiTranscript({grading: {status: "error", error: "GradingError: no key"}}), null));
  await settle();
  failed.viewer.select(failed.viewer.run.beats.length - 1);
  assert.equal(failed.$("grade-note").textContent, "Grading failed when the run was scored: GradingError: no key");
});

test("the sidebar reports the context cap per turn and the inspector reaches each control room", async () => {
  const {$, viewer} = loadViewer(fiRoutes(fiTranscript()));
  await settle();
  const turn = viewer.run.beats.findIndex(beat => beat.kind === "tokens" && beat.tokens.input === 140000);
  viewer.select(turn);
  assert.equal($("context-count").textContent, "140,000 / 200,000");
  assert.equal($("input-tokens").textContent, "Largest turn so far 140,000 input tokens · 200,000 input tokens across 2 turns.");
  viewer.select(0);
  assert.equal($("context-count").textContent, "—");
  const listing = viewer.run.beats.findIndex(beat => beat.kind === "result" && beat.tool === "list_documents");
  viewer.select(listing);
  viewer.inspect("control");
  assert.match($("detail-body").textContent, /GTR-FLEET-CONTROL: not queried yet/);
  viewer.inspect("room:NETWORK-RAIL-CONTROL");
  assert.match($("detail-body").textContent, /No visits to this station at this point in the run\./);
  const rail = viewer.run.beats.findIndex(beat => beat.kind === "result" && beat.args?.room === "NETWORK-RAIL-CONTROL");
  viewer.select(rail);
  viewer.inspect("room:NETWORK-RAIL-CONTROL");
  const text = $("detail-body").textContent;
  assert.match(text, /NETWORK-RAIL-CONTROL · 1 row/);
  assert.match(text, /NETWORK-RAIL-CONTROL \(Network Rail: delay-attribution incident records \(TRUST\), 9 August 2019\): 1 query · 1 entry/);
  assert.doesNotMatch(text, /ESO-COMMS:/, "a room's inspector lists only that room");
});

test("the findings tab shows the accepted report's sections only once the submission is accepted", async () => {
  const {$, viewer} = loadViewer(fiRoutes(fiTranscript()));
  await settle();
  const accepted = viewer.run.beats.findIndex(beat => beat.kind === "result" && beat.submitted);
  $("tab-findings").click();
  viewer.select(accepted - 1);
  assert.doesNotMatch($("detail-body").textContent, /Report ·/);
  viewer.select(accepted);
  const text = $("detail-body").textContent;
  assert.match(text, /Report · executive summary \(word limit 600\)At 16:52:33 BST/);
  assert.match(text, /Report · RecommendationsGTR to review recovery procedures/);
  assert.match(text, /Report · Further evidence requests/);
  assert.match(text, /F02.*ORR reports 29 trains locked out\./);
  assert.doesNotMatch(text, /Draft \[F99\]/, "the rejected attempt's report never shows");
});

// Saved full-investigation runs (the Docker fake scenarios and the Opus pilot) when present.
for (const [relative, results, outcomes, completed, reason, inventory, findings] of [
  ["fi/reference", 42, {OK: 32, NOT_HELD: 10}, true, null, 14, 105],
  ["fi/repair", 43, {OK: 32, NOT_HELD: 10, VALIDATION_FAILED: 1}, true, null, 14, 105],
  ["fi/no_submission", 41, {OK: 31, NOT_HELD: 10}, false, "final_message_without_submission", 14, 0],
  ["fi/isolation_probe", 43, {OK: 12, UNKNOWN_ID: 26, INVALID_ARGUMENT: 2, AMBIGUOUS_REQUEST: 3}, true, null, 2, 0],
]) {
  test(`actual full-investigation run ${relative} keeps its furniture, outcomes and recorded tallies`,
    optionalFixture(path.join(relative, "transcript.json")), () => {
    const parsed = normalizeTranscript(load(relative)), state = end(parsed), world = worldOf(parsed.beats, parsed.meta);
    const tally = {};
    resultsOf(parsed.beats).forEach(beat => { tally[beat.outcome] = (tally[beat.outcome] || 0) + 1; });
    assert.equal(parsed.meta.taskId, FI_TASK);
    assert.deepEqual(tally, outcomes);
    assert.equal(state.toolUsed, results);
    assert.deepEqual([state.toolLimit, state.outputLimit, state.contextLimit], [150, 80000, 200000]);
    assert.deepEqual([state.completed, state.reason, state.inventory.length, state.findings.length], [completed, reason, inventory, findings]);
    assert.deepEqual(world.documents.map(doc => doc.doc_id).sort(), FI_DOCS.slice().sort());
    assert.deepEqual(world.rooms.map(room => room.room_id), FI_ROOMS.map(room => room.room_id));
    assert.deepEqual([world.witnesses.length, world.assets.length], [10, 3]);
    if (findings) assert.deepEqual(state.report.sections.map(section => section.heading),
      ["Chronology", "Findings", "Consequences", "Uncertainties", "Recommendations", "Further evidence requests"]);
    const artifacts = fs.readdirSync(path.join(root, relative)).find(name => name.endsWith("_artifacts"));
    const grade = JSON.parse(fs.readFileSync(path.join(root, relative, artifacts, "grade.json"), "utf8"));
    assert.deepEqual({event: state.records.event, entry: state.records.entry, response: state.records.response}, grade.trace.records_by_kind);
    // The two complete reference-sized grades exceed the runner's metadata limit.
    if (findings) assert.equal(parsed.meta.gradingRecord.truncated, true);
  });
}

test("actual full-investigation live trace matches its transcript",
  optionalFixture("fi/reference/gb2019-fi-fake-reference_artifacts/episode/trace.jsonl"), () => {
  const trace = fs.readFileSync(path.join(root, "fi/reference/gb2019-fi-fake-reference_artifacts/episode/trace.jsonl"), "utf8");
  const beats = normalizeTrace(trace), live = snapshotAt(beats, beats.length - 1), replay = end(normalizeTranscript(load("fi/reference")));
  for (const key of ["toolUsed", "toolLimit", "records", "refusals", "rooms", "witnesses", "returns", "submitted", "report"]) {
    assert.deepEqual(live[key], replay[key], key);
  }
  assert.deepEqual(live.inventory.slice().sort(), replay.inventory.slice().sort());
});

test("actual full-investigation pilot reports its 175k-token peak and its grading error",
  optionalFixture("fi_pilot/transcript.json"), () => {
  const original = load("fi_pilot"), parsed = normalizeTranscript(original), state = end(parsed);
  const summary = original.events.find(event => event.type === "scoring").scoring.metadata.transcript_summary;
  assert.equal(state.peakInputTokens, summary.max_input_tokens);
  assert.equal(state.lastInputTokens, summary.last_input_tokens);
  assert.equal(state.contextReached, summary.context_cap_reached);
  assert.equal(state.outputTokens, summary.output_tokens_total);
  assert.equal(parsed.meta.gradingRecord.status, "error");
});

test("archive bays at the start do not depend on documents the run obtains later", () => {
  // A run without a catalogue listing: two documents are obtained late, each showing its
  // category only in its result. Their cabinets stay in the unnamed bay from the first
  // beat to the last, so the spacing at beat 0 cannot reveal what the run will obtain.
  const docResult = (id, category) => ({ok: true, data: {doc_id: id, title: `${id} record`, category, line_count: 3,
    text: "line one\nline two\nline three"}});
  const events = [
    {type: "task_started", run_id: "late-categories", task_id: FI_TASK, model: "test-model", timestamp: "2026-10-20T10:00:00Z"},
    {type: "task_pre_hook_completed", metadata: {task_id: FI_TASK, manifest_version: 2, tool_names: SR_TOOLS, documents: FI_DOCS,
      budgets: {max_tool_calls: 150}}},
  ];
  [["c1", "R12", "essential_services_records"], ["c2", "S08", "rail_records"]].forEach(([id, doc, category]) => {
    const args = {doc_id: doc}, envelope = docResult(doc, category);
    events.push({type: "message_added", message: {role: "assistant", tool_calls: [call(id, "request_document", args)]}});
    events.push({type: "tool_call_started", tool_call: call(id, "request_document", args)});
    events.push(done(id, envelope, {structuredContent: envelope}));
  });
  const {beats, meta} = normalizeTranscript({run_id: "late-categories", events});
  const whole = worldOf(beats, meta), opening = worldOf(beats.slice(0, 2), meta);
  // the categories are known by the end, for labels
  assert.equal(whole.documents.find(doc => doc.doc_id === "S08").category, "rail_records");
  const bays = world => {
    const scene = newScene();
    scene.setWorld(world);
    return Array.from(scene.groups, group => [group.category, Array.from(group.docs)]);
  };
  assert.deepEqual(bays(whole), bays(opening));
  assert.deepEqual(bays(whole).map(([category]) => category), [""]);
  // the labels still follow what was shown by the selected event
  assert.equal(snapshotAt(beats, 1, meta).revealed.documents.find(doc => doc.doc_id === "S08").category, undefined);
  assert.equal(end({beats, meta}).revealed.documents.find(doc => doc.doc_id === "S08").category, "rail_records");
  // with an opening listing, a later filtered listing moves no cabinet either
  const listed = fiTranscript(), parsed = normalizeTranscript(listed);
  const atListing = parsed.beats.findIndex(beat => beat.kind === "result" && beat.tool === "list_documents");
  assert.deepEqual(bays(worldOf(parsed.beats, parsed.meta)), bays(worldOf(parsed.beats.slice(0, atListing + 1), parsed.meta)));
});

// ---------------------------------------------------------------------------
// Results: the Report, Grades and Compare views. Synthetic submission and grade in the
// shapes the grader writes (grade.json with criteria, layers, assertions, citations and
// flags), runnable without out/; saved runs below are optional.

const R = globalThis.AgentWorldData;
const RESULT_SHA = "a".repeat(64);
const RESULT_SUBMISSION = {schema_version: "3.0", report: {
  executive_summary: "Lightning hit the circuit [F01]. The totals differ by basis [F02, F03]. See also [F99].",
  sections: [
    {heading: "Chronology", body: "## Times\n- 16:52:33 fault [F01]\n- **Trip** at 16:52:35 [F02]\n  continued on the next line\n\n3. third\n4. fourth\n\n| Loss | MW |\n|---|---|\n| Hornsea | 737 [F02] |"},
    {heading: "Uncertainties", body: "Little Barford causes are unknown.\nA second line <b>stays text</b>."},
  ]},
  findings: [
    {finding_id: "F01", statement: "Fault at 16:52:33.", status: "reported", event_time: "2019-08-09T16:52:33+01:00",
      citations: [{evidence_id: "R03", locator: "L36-L40"}, {evidence_id: "R03", locator: "L999"}]},
    {finding_id: "F02", statement: "Hornsea lost 737 MW.", status: "observed", quantity: {value: 737, unit: "MW", basis: "reported"},
      citations: [{evidence_id: "S06", locator: "L58-L61"}]},
    {finding_id: "F03", statement: "Causes may be <script>unknown</script>.", status: "hypothesis", derivation: "799 - 62", citations: []},
  ]};
const RESULT_GRADE = {grade_schema: "gb2019-sr-grade/1", status: "provisional", grader_version: "0.1.0",
  key: {key_id: "test-key", key_version: "0.1.0", review_status: "pending_domain_review"},
  provisional_reasons: ["answer key review status is 'pending_domain_review'"],
  interpretation: "No pass threshold, overall score, task total or ranking is computed.",
  run: {outcome: "complete", budgets: {tool_calls_limit: 150, output_token_budget: 80000, context_cap_tokens: 200000},
    tokens: {output_total: 27588, output_before_freeze: 25812, last_input: 160959}},
  trace: {calls_used: 47}, bundle: {bundle_sha256: RESULT_SHA}, tasks: ["T02", "T10"],
  criteria: [
    {criterion_id: "T10.01", task: "T10", assessment_mode: "auto_numeric", title: "Ten: a numeric landmark",
      content: {value: 1, source: "auto"}, evidence_support: {value: 1, source: "auto"}, matched_finding_ids: ["F01"]},
    {criterion_id: "T02.01", task: "T02", assessment_mode: "judge", title: "Hornsea loss 737 MW kept on its basis",
      content: {value: 1, source: "judge", auto_proposal: 0.5, judge_proposal: 1, basis: "judge proposal: F02 keeps the basis."},
      evidence_support: {value: 1, source: "judge", auto_proposal: 1, judge_proposal: 1, basis: "cites keyed evidence S06 L58-L61"},
      judge_finding_ids: ["F02"], matched_finding_ids: ["F02"],
      layers: {auto: {basis: "partial: hornsea_only", content: 0.5}, caps: [],
        judge: {content: 1, evidence_support: 1, rationale: "F02 keeps the basis.",
          supporting_spans: [{evidence_id: "S06", locator: "L58-L61", quote: "E7 section 4.2: the net effect", shown_in: ["C3"]}]}}},
    {criterion_id: "T02.02", task: "T02", assessment_mode: "auto_assisted_human", title: "Second",
      content: {value: null, source: "pending", auto_proposal: 0}, evidence_support: {value: null, source: "not_applicable"},
      judge_note: {content: 1, ignored: true, rationale: "Judge would credit F02."}},
    {criterion_id: "T02.03", task: "T02", assessment_mode: "auto_assisted_human", title: "Third",
      content: {value: null, source: "pending"}, evidence_support: {value: null, source: "pending"},
      layers: {caps: [{kind: "severe_suspected", flag_id: "SF1", note: "suspected severe flag SF1 (applies unless adjudicated false)"}]}},
    {criterion_id: "T02.04", task: "T02", assessment_mode: "auto_assisted_human", title: "Fourth",
      content: {value: 0.5, source: "human"}, evidence_support: {value: 0, source: "human"}},
  ],
  assertion_quality: {assertions: [
    {assertion_id: "F01", dimension: "T10", kind: "finding", status: "reported", source: "judge", verdict: "supported",
      judge_proposal: "supported", auto_proposal: "contradicted", layers: {judge: {rationale: "C1 supports it.", supporting_spans: []}}},
    {assertion_id: "F02", dimension: "T02", kind: "finding", status: "observed", source: "pending", verdict: null, auto_proposal: "unsupported"},
    {assertion_id: "F03", dimension: "T02", kind: "finding", status: "hypothesis", source: "labelled_hypothesis_or_unknown", verdict: null},
    {assertion_id: "J-T02-1", dimension: "T02", kind: "report_text", text: "The totals differ by basis [F02, F03].", source: "judge",
      verdict: "contradicted", judge_proposal: "contradicted"},
  ]},
  citations: [
    {finding_id: "F01", index: 0, evidence_id: "R03", locator: "L36-L40", normalized: "L36-L40", resolvable: true,
      retrieved_during_episode: true, retrieval_routes: ["request_document"]},
    {finding_id: "F01", index: 1, evidence_id: "R03", locator: "L999", resolvable: false, error: "R03 has 107 lines; L999 is out of range",
      retrieved_during_episode: true},
    {finding_id: "F02", index: 0, evidence_id: "S06", locator: "L58-L61", normalized: "L58-L61", resolvable: true,
      retrieved_during_episode: false, retrieval_routes: []},
  ],
  flags: {uncited_findings: ["F03"], findings_not_referenced_in_report: [],
    labelling: [{finding_id: "F03", issue: "hedged wording with a factual status", status: "hypothesis", terms: ["may"]}],
    accounting_traps: [{finding_id: "F02", type: "misattributed", excerpt: "737 mw as reported", figure_id: "GEN_737"}],
    cited_but_never_retrieved: ["S06 L58-L61"], cited_but_never_retrieved_findings: ["F02"],
    unresolvable_citations: [{finding_id: "F01", index: 1, evidence_id: "R03", locator: "L999", resolvable: false, error: "out of range"}],
    executive_summary: {words: 14, limit: 600, within_limit: true}},
  severe_flags: [{flag_id: "SF1", finding_id: "F03", excerpt: "the root cause was", detected_by: "heuristic", source: "pending"}],
  judge: {judge_model: "openai/gpt-6.1-sol", rubric_version: "1.0.0", severe_flag_suggestions: []},
};

test("report text keeps headings, lists, tables and bold, and links only real finding references", () => {
  assert.deepEqual(R.findingRefs("a [F01] b [F02, F03] c [not, a ref"), ["F01", "F02", "F03"]);
  const known = new Set(["F01", "F02"]);
  const blocks = R.reportBlocks(RESULT_SUBMISSION.report.sections[0].body, known);
  assert.deepEqual(blocks.map(block => block.type), ["heading", "list", "list", "table"]);
  assert.equal(blocks[0].level, 2);
  assert.equal(blocks[1].items.length, 2, "an indented line continues its item");
  assert.deepEqual(blocks[2], {...blocks[2], ordered: true, start: 3});
  assert.equal(blocks[3].rows.length, 2, "the separator row is not a row");
  const trip = blocks[1].items[1];
  assert.deepEqual(trip[0], {strong: [{text: "Trip"}]});
  const group = trip.find(token => token.refs).refs;
  assert.deepEqual(group, [{text: "["}, {ref: "F02", known: true}, {text: "]"}]);
  const unknown = R.reportBlocks("See [F02, F99].", known)[0].lines[0].find(token => token.refs).refs;
  assert.deepEqual(unknown.filter(token => token.ref), [{ref: "F02", known: true}, {ref: "F99", known: false}]);
  const report = R.reportOf(RESULT_SUBMISSION);
  assert.deepEqual(report.sections.map(section => section.heading), ["Executive summary", "Chronology", "Uncertainties"]);
  assert.deepEqual(report.referencedIn.get("F02"), ["Executive summary", "Chronology"]);
  assert.equal(report.referencedIn.has("F99"), false);
  assert.equal(report.words, 15, "counted here by whitespace; the grade's own count is shown when present");
});

test("each value names its source: automated, judge or pre-screen proposal, human, pending", () => {
  const cases = [
    [{value: 1, source: "auto"}, {value: 1, source: "auto", proposal: false}, {value: 1, source: "auto"}],
    [{value: 0.5, source: "human"}, {value: 0.5, source: "human", proposal: false}, {value: 0.5, source: "human"}],
    [{value: 0, source: "severe_flag"}, {value: 0, source: "severe_flag", proposal: false}, {value: 0, source: "severe_flag"}],
    [{value: 1, source: "judge", auto_proposal: 0.5}, {value: 1, source: "judge", proposal: true}, {value: null, source: "pending"}],
    [{value: null, source: "pending", auto_proposal: 0}, {value: 0, source: "prescreen", proposal: true}, {value: null, source: "pending"}],
    [{value: null, source: "pending"}, {value: null, source: "pending", proposal: false}, {value: null, source: "pending"}],
    [{value: null, source: "not_applicable"}, {value: null, source: "not_applicable", proposal: false}, {value: null, source: "not_applicable"}],
  ];
  for (const [field, best, decided] of cases) {
    const a = R.attribute(field), d = R.attribute(field, true);
    assert.deepEqual({value: a.value, source: a.source, proposal: a.proposal}, best, JSON.stringify(field));
    assert.deepEqual({value: d.value, source: d.source}, decided, JSON.stringify(field));
  }
  assert.equal(R.attributeAssertion({source: "labelled_hypothesis_or_unknown"}).cls, "not_checked");
  assert.deepEqual(R.attributeAssertion({source: "pending", auto_proposal: "unsupported"}),
    {cls: "unsupported", source: "prescreen", verdict: "unsupported", proposal: true});
  assert.equal(R.attributeAssertion({source: "judge", verdict: "contradicted"}, true).cls, "pending");
  assert.deepEqual(R.disagreementOf({auto_proposal: 0.5, judge_proposal: 1}), {judge: 1, prescreen: 0.5});
  assert.equal(R.disagreementOf({auto_proposal: 1, judge_proposal: 1}), null);
});

test("topics count full, half, zero and pending per measure, kept separate and never summed", () => {
  const content = R.topicSummaries(RESULT_GRADE);
  assert.deepEqual(content.map(topic => topic.topic), ["T02", "T10"], "T02 sorts before T10");
  assert.deepEqual(content[0].counts, {full: 1, half: 1, zero: 1, pending: 1});
  assert.deepEqual(content[0].proposed, {full: 1, half: 0, zero: 1, pending: 0});
  assert.deepEqual(content[0].sources, {judge: 1, prescreen: 1, pending: 1, human: 1});
  assert.deepEqual(content[1].counts, {full: 1, half: 0, zero: 0, pending: 0});
  // Three T02 values still await a human (a judge proposal, a pre-screen proposal and
  // one with no proposal); the human decision does not.
  assert.deepEqual([content[0].awaiting, content[1].awaiting], [3, 0]);
  const decided = R.topicSummaries(RESULT_GRADE, {decidedOnly: true});
  assert.deepEqual(decided[0].counts, {full: 0, half: 1, zero: 0, pending: 3});
  assert.deepEqual(decided[0].sources, content[0].sources, "a proposal left out of the count still names its source");
  assert.equal(decided[0].awaiting, 3);
  const evidence = R.topicSummaries(RESULT_GRADE, {measure: "evidence"});
  assert.deepEqual(evidence[0].counts, {supported: 1, unsupported: 1, not_applicable: 1, pending: 1});
  const assertions = R.topicSummaries(RESULT_GRADE, {measure: "assertions"});
  assert.deepEqual(assertions[0].counts, {supported: 0, unsupported: 1, contradicted: 1, not_checked: 1, pending: 0});
  assert.deepEqual(assertions[1].counts, {supported: 1, unsupported: 0, contradicted: 0, not_checked: 0, pending: 0});
  const totals = R.measureCounts(RESULT_GRADE);
  assert.deepEqual(totals.counts, {full: 2, half: 1, zero: 1, pending: 1});
  assert.equal(totals.total, 5);
  assert.equal(totals.awaiting, 3);
  assert.deepEqual(Object.keys(totals).sort(), ["awaiting", "counts", "proposed", "sources", "total"], "counts only: no score, sum or weight");
  assert.deepEqual(R.barSegments(content[0]).map(s => [s.cls, s.proposal, s.count]),
    [["full", true, 1], ["half", false, 1], ["zero", true, 1], ["pending", false, 1]]);
  // The server's compact projection keeps the grade's schema, so it counts the same.
  const slim = {criteria: RESULT_GRADE.criteria.map(c => ({criterion_id: c.criterion_id, task: c.task,
    assessment_mode: c.assessment_mode, content: c.content, evidence_support: c.evidence_support}))};
  assert.deepEqual(R.topicSummaries(slim), content);
});

test("a criterion's detail keeps the judge rationale, disagreements, unapplied notes, caps and findings", () => {
  const judged = R.criterionDetail(RESULT_GRADE.criteria[1]);
  assert.equal(judged.modeLabel, "LLM judge proposes, a human decides");
  assert.deepEqual([judged.content.cls, judged.content.source, judged.content.decided.cls], ["full", "judge", "pending"]);
  assert.deepEqual(judged.content.disagreement, {judge: 1, prescreen: 0.5});
  assert.equal(judged.evidence.disagreement, null);
  assert.equal(judged.prescreenBasis, "partial: hornsea_only");
  assert.deepEqual(judged.judge.spans, [{evidence_id: "S06", locator: "L58-L61", quote: "E7 section 4.2: the net effect"}]);
  assert.deepEqual(judged.findings, {matched: ["F02"], judge: ["F02"], human: []});
  const noted = R.criterionDetail(RESULT_GRADE.criteria[2]);
  assert.deepEqual(noted.judgeNote, {rationale: "Judge would credit F02.", content: 1});
  assert.deepEqual([noted.content.source, noted.evidence.cls], ["prescreen", "not_applicable"]);
  assert.equal(R.criterionDetail(RESULT_GRADE.criteria[3]).caps[0].flag_id, "SF1");
  const checks = R.citationChecks(RESULT_GRADE);
  assert.equal(checks.get("F01#1").resolvable, false);
  assert.equal(checks.get("F02#0").retrieved, false);
  const flags = R.findingFlags(RESULT_GRADE);
  assert.deepEqual(flags.get("F03").map(flag => flag.kind), ["uncited", "labelling"]);
  assert.deepEqual(flags.get("F02").map(flag => flag.kind), ["unretrieved", "accounting"]);
  assert.deepEqual(R.criteriaByFinding(RESULT_GRADE).get("F02").map(item => item.id), ["T02.01"]);
  assert.equal(R.topicHints(RESULT_GRADE).T02, "Hornsea loss 737 MW kept on its basis");
});

const compareRun = (path, model, task, grade, metrics = {outcome: "complete"}) => ({path, run_id: path, model, task_id: task,
  grade, grade_source: grade ? "run" : null, metrics});
const COMPARE = {runs: [
  compareRun("panel/b/transcript.json", "openrouter/zeta/model", "gb-2019-system-response", RESULT_GRADE),
  compareRun("panel/a/transcript.json", "openrouter/alpha/model", "gb-2019-system-response",
    {...RESULT_GRADE, criteria: RESULT_GRADE.criteria.slice(1, 3)}),
  compareRun("archive/old/transcript.json", "openrouter/alpha/model", "gb-2019-system-response", RESULT_GRADE),
  compareRun("panel_30k/c/transcript.json", "openrouter/alpha/model", "gb-2019-full-investigation",
    {criteria: [], measures_note: "run outcome is 'incomplete_submission'"},
    {outcome: "incomplete_submission", incomplete_reason: "output_token_budget_exhausted"}),
  compareRun("fi/none/transcript.json", "fake", "gb-2019-full-investigation", null),
], topic_hints: {"gb-2019-system-response": {T02: "Hornsea loss"}}};

test("compare groups runs by task as a runs × topics matrix, ordered by model, never by a measure", () => {
  const groups = R.compareGroups(COMPARE);
  assert.deepEqual(groups.map(group => group.task), ["gb-2019-full-investigation", "gb-2019-system-response"]);
  const sr = groups[1];
  assert.deepEqual(sr.topics, ["T02", "T10"]);
  assert.deepEqual(sr.rows.map(row => row.run.path), ["archive/old/transcript.json", "panel/a/transcript.json", "panel/b/transcript.json"]);
  assert.deepEqual(sr.rows[2].cells.T02.counts, {full: 1, half: 1, zero: 1, pending: 1});
  assert.equal(sr.rows[1].cells.T10, undefined, "a topic missing from a run's grade stays empty");
  assert.equal(sr.hints.T02, "Hornsea loss");
  const fi = groups[0];
  assert.deepEqual(fi.rows.map(row => row.note), [
    "Not graded for content: the run is incomplete (output-token budget exhausted).", "No grade.json for this run."]);
  assert.deepEqual(R.compareGroups(COMPARE, {archived: false})[1].rows.map(row => row.run.path),
    ["panel/a/transcript.json", "panel/b/transcript.json"]);
  assert.deepEqual(R.compareGroups(COMPARE, {model: "fake"}).map(group => group.rows.length), [1]);
  assert.deepEqual(R.compareGroups(COMPARE, {task: "gb-2019-system-response", decidedOnly: true})[0].rows[2].cells.T02.counts,
    {full: 0, half: 1, zero: 0, pending: 3});
  assert.deepEqual(R.compareGroups(COMPARE, {measure: "assertions"})[1].rows[2].cells.T10.counts,
    {supported: 1, unsupported: 0, contradicted: 0, not_checked: 0, pending: 0});
});

// A judge proposal an automated check lowered, as the grader records it: source "judge",
// the capped value, the judge's own value in judge_proposal and the cap in the basis.
const CAPPED_GRADE = {...RESULT_GRADE, tasks: ["T02", "T07"], criteria: [
  {criterion_id: "T07.01", task: "T07", assessment_mode: "judge", title: "ST1C tripped on a speed-signal discrepancy",
    content: {value: 1, source: "judge", auto_proposal: 1, judge_proposal: 1, basis: "judge proposal: F09 states it."},
    evidence_support: {value: 1, source: "judge", auto_proposal: 1, judge_proposal: 1, basis: "cites keyed evidence"},
    layers: {auto: {basis: "full: st1c", content: 1}, caps: [], judge: {content: 1, evidence_support: 1, rationale: "F09 states it."}}},
  {criterion_id: "T07.04", task: "T07", assessment_mode: "judge", title: "Underlying causes remain unestablished",
    content: {value: 0, source: "judge", auto_proposal: 0, judge_proposal: 1,
      basis: "judge proposal (judge proposed 1; capped to 0 by automated check(s) SF1): F09 keeps both causes open."},
    evidence_support: {value: null, source: "not_applicable", judge_proposal: 1, basis: "content is 0"},
    layers: {auto: {basis: "suspected severe flag SF1", content: 0},
      caps: [{effect: "zero", flag_id: "SF1", id: "SF1", kind: "severe_suspected", note: "suspected severe flag SF1 (applies unless adjudicated false)"},
        {effect: "zero", id: "C2", kind: "contradiction", binding: false, finding_id: "F09", note: "a pre-screen flag; it bounds nothing"}],
      judge: {content: 1, evidence_support: 1, rationale: "F09 keeps both causes open."}}},
  {criterion_id: "T02.06", task: "T02", assessment_mode: "judge", title: "Ofgem's 1,990 MW kept on its own basis",
    content: {value: 0.5, source: "judge", auto_proposal: 0, judge_proposal: 1,
      basis: "judge proposal (judge proposed 1; capped to 0.5 by automated check(s) ofgem_1990_on_wrong_basis): F16 and F17 keep the bases apart."},
    evidence_support: {value: 1, source: "judge", auto_proposal: 1, judge_proposal: 1, basis: "cites keyed evidence"},
    layers: {auto: {basis: "accounting ofgem_1990_on_wrong_basis (F17)", content: 0},
      caps: [{effect: "cap_half", finding_id: "F17", id: "ofgem_1990_on_wrong_basis", kind: "accounting", note: "Ofgem's figure on another stage"}],
      judge: {content: 1, evidence_support: 1, rationale: "F16 and F17 keep the bases apart."}}},
]};

test("a judge value an automated check capped is attributed to the cap, never to the judge", () => {
  const [plain, severe, accounting] = CAPPED_GRADE.criteria;
  assert.deepEqual(R.attribute(plain.content), {value: 1, source: "judge", proposal: true});
  assert.deepEqual(R.attribute(severe.content), {value: 0, source: "capped", proposal: true, judge: 1});
  assert.deepEqual(R.attribute(severe.content, true), {value: null, source: "pending", proposal: false, awaiting: "capped"});
  assert.deepEqual(R.attribute(accounting.content), {value: 0.5, source: "capped", proposal: true, judge: 1});
  // Only binding caps lowered it: a pre-screen flag (binding: false) is not named.
  const cap = R.capOf(severe);
  assert.deepEqual([cap.judge, cap.value, cap.suspected, cap.by.map(item => item.label)], [1, 0, true, ["suspected severe flag SF1"]]);
  assert.deepEqual(R.capOf(accounting).by.map(item => item.label), ["accounting cap ofgem_1990_on_wrong_basis (F17)"]);
  assert.equal(R.capOf(accounting).suspected, false);
  assert.equal(R.capOf(plain), null);
  // Without layers (the compare page's compact grade), the grade's basis names the check.
  const slim = {criterion_id: "T07.04", task: "T07", content: severe.content};
  assert.deepEqual(R.capOf(slim).by.map(item => item.label), ["suspected severe flag SF1"]);
  const detail = R.criterionDetail(severe);
  assert.deepEqual([detail.content.cls, detail.content.source, detail.content.decided.cls], ["zero", "capped", "pending"]);
  assert.equal(detail.content.basis, severe.content.basis);
  // Counted under their own source: capped zeros are not judge proposals.
  const summaries = R.topicSummaries(CAPPED_GRADE);
  const t07 = summaries.find(summary => summary.topic === "T07");
  assert.deepEqual(t07.sources, {judge: 1, capped: 1});
  assert.deepEqual([t07.counts.full, t07.counts.zero, t07.proposed.zero, t07.awaiting], [1, 1, 1, 2]);
  assert.deepEqual(R.measureCounts(CAPPED_GRADE).sources, {judge: 1, capped: 2});
  const slimGrade = {criteria: CAPPED_GRADE.criteria.map(c => ({criterion_id: c.criterion_id, task: c.task, content: c.content, evidence_support: c.evidence_support}))};
  assert.deepEqual(R.topicSummaries(slimGrade), summaries, "the compare page counts the compact grade the same way");
  assert.deepEqual(R.topicSummaries(CAPPED_GRADE, {decidedOnly: true}).find(summary => summary.topic === "T07").sources, {judge: 1, capped: 1});
});

// The panel's MVP opus55-002 executive summary nests a list inside an item and then
// returns to that item with an indented paragraph.
const NESTED_SUMMARY = "The fault set off two separate generation losses:\n" +
  "- **Hornsea One (offshore wind farm).** Output fell from 799 MW to 62 MW [F05, F06].\n" +
  "- **Little Barford (gas-fired combined-cycle station).** The station lost 641 MW in three steps [F10]:\n" +
  "  - the steam turbine, 244 MW, at about 16:52:35.2 BST;\n" +
  "  - gas turbine GT1A, 210 MW, at about 16:53:31.6 BST;\n" +
  "  - gas turbine GT1B, 187 MW, at about 16:53:58.6 BST.\n" +
  "  The steam turbine trip is reported to come from a discrepancy between its speed sensors [F11]. The cause of the pressure excursions is also unresolved [F12]. The UPS alarms are not believed to be related [F13].\n" +
  "\nThese records account for 1,378 MW of lost generation [F14].";
// References in an item's own text, not in the lists nested inside it.
const refsOf = tokens => tokens.flatMap(token => token.refs ? token.refs.filter(item => item.ref).map(item => item.ref) :
  token.strong ? refsOf(token.strong) : []);

test("a nested list stays inside its item, and an indented paragraph after it returns to that item", () => {
  const blocks = R.reportBlocks(NESTED_SUMMARY);
  assert.deepEqual(blocks.map(block => block.type), ["paragraph", "list", "paragraph"]);
  const list = blocks[1];
  assert.equal(list.items.length, 2, "nested bullets are not siblings of their parent");
  const barford = list.items[1], at = barford.findIndex(token => token.list), nested = barford[at].list;
  assert.deepEqual(nested.items.map(item => item.map(token => token.text || "").join("").split(",")[0]),
    ["the steam turbine", "gas turbine GT1A", "gas turbine GT1B"]);
  assert.deepEqual(refsOf(nested.items[2]), [], "the GT1B bullet keeps only its own text");
  assert.doesNotMatch(nested.items[2].map(token => token.text || "").join(""), /discrepancy/);
  assert.deepEqual(refsOf(barford), ["F10", "F11", "F12", "F13"], "the paragraph after the nested list belongs to Little Barford");
  assert.ok(barford.findIndex(token => token.refs?.some(item => item.ref === "F11")) > at, "and follows the nested list");
  assert.deepEqual(refsOf(list.items[0]), ["F05", "F06"]);
  // Deeper levels, numbered parents and a continuation of the nested item itself.
  const deep = R.reportBlocks("1. one\n   - sub\n     more sub\n   back to one\n2. two\n- next list");
  assert.deepEqual(deep.map(block => [block.type, block.ordered, block.items.length]), [["list", true, 2], ["list", false, 1]]);
  const one = deep[0].items[0], sub = one.find(token => token.list).list;
  assert.equal(sub.items[0].map(token => token.text || "").join(""), "sub more sub");
  assert.equal(one.at(-1).text, "back to one");
  // The flat case is unchanged: an indented line continues its own item.
  assert.equal(R.reportBlocks("- a\n  still a\n- b")[0].items[0].map(token => token.text).join(""), "a still a");
});

// The controller, against the fake DOM.
const RESULT_PATHS = {transcript: "panel/run/transcript.json", submission: "panel/run/r_artifacts/episode/submission.json",
  grade: "panel/run/r_artifacts/grade.json", judged: "panel/run/r_artifacts/episode/judge/grade.json"};
const descendants = node => node.descendants();
const textOfNode = node => node.textContent;
function resultRoutes({run = {}, evidence = null, bundles = [{bundle_id: "test", bundle_version: "0.1.0", bundle_sha256: RESULT_SHA}],
  transcript = fiTranscript(), results = COMPARE, grade = RESULT_GRADE, submission = RESULT_SUBMISSION} = {}) {
  const meta = {path: RESULT_PATHS.transcript, run_id: "results-synthetic", task_id: "gb-2019-system-response",
    model: "openrouter/test/model", submission_path: RESULT_PATHS.submission, grade_path: RESULT_PATHS.grade,
    judge: {path: RESULT_PATHS.judged, judge_model: "openai/gpt-6.1-sol", grade: {status: "provisional", flags: {}}},
    bundle: {bundle_id: "test", bundle_version: "0.1.0", bundle_sha256: RESULT_SHA},
    metrics: {outcome: "complete", tool_calls: 47, peak_input_tokens: 160959, output_tokens: 27588}, ...run};
  return url => {
    if (url === "/api/config") return {};
    if (url === "/api/runs") return {runs: [meta]};
    if (url === "/api/results") return results;
    if (url === "/api/bundles") return {bundles};
    if (url.startsWith("/api/evidence")) return evidence || {resolved: true, evidence_id: "S06", kind: "lines", normalized: "L58-L61",
      document: {doc_id: "S06", title: "DNO returns", access: "data_return"}, line_count: 120,
      lines: [{n: 57, text: "before", cited: false}, {n: 58, text: "E7 section 4.2: the net effect", cited: true}, {n: 61, text: "end", cited: true}],
      bundle: {bundle_id: "test", bundle_version: "0.1.0", bundle_sha256: RESULT_SHA}};
    if (url.startsWith("/api/file")) {
      const path = new URLSearchParams(url.split("?")[1]).get("path");
      if (path === RESULT_PATHS.transcript) return transcript;
      if (path === RESULT_PATHS.submission && meta.submission_path) return submission;
      if (path === RESULT_PATHS.judged) return grade;
      if (path === RESULT_PATHS.grade) return {...RESULT_GRADE, criteria: [], measures_note: "the run grade, superseded"};
    }
    return undefined;
  };
}
const buttons = (root, className) => descendants(root).filter(node => node.tagName === "button" && String(node.className || "").split(" ").includes(className));

test("the Report tab renders the frozen submission as text, links findings and marks flagged citations", async () => {
  const {$, viewer, location} = loadViewer(resultRoutes());
  await settle();
  viewer.setView("report");
  await settle();
  assert.equal(viewer.view, "report");
  assert.equal($("office-view").hidden, true);
  assert.equal($("report-view").hidden, false);
  const body = $("report-body"), text = textOfNode(body);
  assert.match(text, /3 findings · executive summary 14 words as the grader counted them \(limit 600\) · read from panel\/run\/r_artifacts\/episode\/submission\.json/);
  for (const piece of ["Executive summary", "Chronology", "Times", "third", "Hornsea", "Fault at 16:52:33.", "737 MW · reported", "799 - 62"]) {
    assert.ok(text.includes(piece), piece);
  }
  assert.ok(text.includes("Causes may be <script>unknown</script>."), "statements stay text");
  assert.ok(text.includes("A second line <b>stays text</b>."), "report markup stays text");
  const refs = buttons(body, "linkish").filter(node => node.textContent === "F02");
  assert.ok(refs.length >= 2);
  assert.equal(descendants(body).filter(node => node.className === "ref-unknown").map(textOfNode)[0], "F99");
  refs[0].click();
  const card = descendants(body).find(node => node.dataset?.finding === "F02");
  assert.ok(card.classList.contains("highlight"));
  assert.match(location.hash, /view=report/);
  assert.match(location.hash, /finding=F02/);
  const cites = buttons(body, "cite");
  const unresolved = cites.find(node => node.textContent.startsWith("R03 · L999"));
  assert.ok(unresolved.classList.contains("unresolved"));
  assert.match(unresolved.textContent, /does not resolve/);
  const unretrieved = cites.find(node => node.textContent.startsWith("S06 · L58-L61"));
  assert.ok(unretrieved.classList.contains("unretrieved"));
  assert.match(unretrieved.getAttribute("aria-label"), /did not obtain during the run/);
  assert.match(text, /No citations/);
  assert.match(text, /Not referenced in the report text|Referenced in: Executive summary/);
  // A matched criterion opens the Grades tab at that criterion.
  buttons(body, "linkish").find(node => node.textContent === "T02.01").click();
  await settle();
  assert.equal(viewer.view, "grades");
  assert.match(location.hash, /topic=T02&criterion=T02\.01/);
});

test("the evidence drawer reads the cited span from the run's bundle and repeats the grade's flags", async () => {
  const {$, viewer, requests} = loadViewer(resultRoutes());
  await settle();
  viewer.setView("report");
  await settle();
  buttons($("report-body"), "cite").find(node => node.textContent.startsWith("S06 · L58-L61")).click();
  await settle();
  assert.equal($("evidence-drawer").hidden, false);
  assert.equal($("drawer-title").textContent, "S06 · L58-L61");
  const asked = requests.find(url => url.startsWith("/api/evidence"));
  assert.deepEqual(Object.fromEntries(new URLSearchParams(asked.split("?")[1])),
    {bundle: RESULT_SHA, evidence_id: "S06", locator: "L58-L61", context: "3"});
  const text = $("drawer-body").textContent;
  assert.match(text, /never obtained: the agent cited it without retrieving it/);
  assert.match(text, /S06 — DNO returns/);
  assert.match(text, /data return only/);
  assert.match(text, /Lines 58–61 of 120, cited lines highlighted/);
  assert.match(text, /E7 section 4\.2: the net effect/);
  viewer.closeDrawer();
  assert.equal($("evidence-drawer").hidden, true);
  // A run whose bundle is not on disk is explained, and nothing is fetched for it.
  const missing = loadViewer(resultRoutes({run: {bundle: {bundle_id: "gb-2019-08-09-electrical-mvp", bundle_version: "1.0.0", bundle_sha256: "5".repeat(64)}}}));
  await settle();
  missing.viewer.openEvidence({evidence_id: "R03", locator: "L1"});
  await settle();
  assert.match(missing.$("drawer-body").textContent, /This run used gb-2019-08-09-electrical-mvp 1\.0\.0 .* not on disk\. The viewer holds test 0\.1\.0\. Lines can differ between versions/);
  assert.equal(missing.requests.some(url => url.startsWith("/api/evidence")), false);
});

test("the Grades tab keeps three measures apart, names every value's source and highlights disagreements", async () => {
  const {$, viewer, requests} = loadViewer(resultRoutes());
  await settle();
  viewer.setView("grades");
  await settle();
  assert.ok(requests.includes(`/api/file?path=${encodeURIComponent(RESULT_PATHS.judged)}`), "the judged grade is read");
  assert.equal(requests.includes(`/api/file?path=${encodeURIComponent(RESULT_PATHS.grade)}`), false, "the run grade is superseded");
  let text = $("grades-body").textContent;
  assert.match(text, /Provisional — awaiting human sign-off\. No pass threshold, overall score or ranking is computed/);
  assert.match(text, /Completed — provisional/);
  assert.match(text, /47 \/ 150 tool calls/);
  assert.match(text, /Output tokens 27,588 \/ 80,000 \(25,812 before the submission froze\)/);
  assert.match(text, /Context, largest turn 160,959 \/ 200,000/);
  assert.match(text, /Key 0\.1\.0 · pending domain review/);
  assert.match(text, /Judged grade.*episode\/judge\/grade\.json supersedes the run’s grade\.json\./);
  // Best available counts proposals in their class; the class with no value holds only
  // values with nothing proposed, and the awaiting line keeps proposals visible as undecided.
  assert.match(text, /Content coverage.*2 full · 1 half · 1 zero · 1 no proposal \(5 criteria\)/);
  assert.match(text, /3 of 5 awaiting a human decision \(1 judge proposal · 1 pre-screen proposal · 1 with no proposal\) · 1 automated decision · 1 human decision/);
  assert.match(text, /Evidence support.*2 supported · 1 not supported · 1 not applicable · 1 no proposal/);
  assert.match(text, /Assertion quality.*1 supported · 1 unsupported · 1 contradicted · 1 not checked · 0 no proposal \(4 assertions\)/);
  assert.match(text, /3 of 4 awaiting a human decision \(2 judge proposals · 1 pre-screen proposal\) · 1 labelled hypothesis or unknown/);
  assert.match(text, /2 of 5 awaiting a human decision \(1 judge proposal · 1 with no proposal\) · 1 automated decision · 1 human decision · 1 not applicable/);
  assert.doesNotMatch(text, /\d pending/, "nothing is called pending while proposals are counted");
  assert.match(text, /No proposalBest available: no value and nothing proposed yet/);
  assert.match(text, /PendingDecided only: anything not yet decided by an automated check or a human, proposals included/);
  assert.doesNotMatch(text, /%|winner|ranked|overall: \d|total score/i);
  assert.ok(text.indexOf("T02") < text.indexOf("T10"));
  viewer.toggleTopic("T02");
  text = $("grades-body").textContent;
  assert.match(text, /Judge and pre-screen disagree\. Content coverage: the judge proposed Full \(1\), the pre-screen Half \(0\.5\)\. A human decides\./);
  assert.match(text, /Judge rationale \(a proposal awaiting human sign-off\)F02 keeps the basis\./);
  assert.match(text, /S06 · L58-L61quoted by the judgeE7 section 4\.2: the net effect/);
  assert.match(text, /Judge comment, not applied/);
  assert.match(text, /severe_suspected SF1: suspected severe flag SF1/);
  assert.match(text, /Counting decided values only: pending\./);
  assert.match(text, /Severe flags \(1\)/);
  assert.match(text, /Accounting \(1\)/);
  assert.match(text, /Cited but never obtained \(1\)/);
  assert.match(text, /Citations that do not resolve \(1\)/);
  viewer.setMeasure("content", true);
  text = $("grades-body").textContent;
  assert.match(text, /1 full · 1 half · 0 zero · 3 pending \(5 criteria\)/, "only automated and human decisions count");
  assert.match(text, /3 of 5 awaiting a human decision \(1 judge proposal · 1 pre-screen proposal · 1 with no proposal\)/, "the same in either count mode");
  assert.match(text, /T02\.01Hornsea loss 737 MW kept on its basisPendingJudge proposal not counted/);
  viewer.setMeasure("assertions");
  viewer.toggleTopic("T10");
  text = $("grades-body").textContent;
  assert.match(text, /judge ≠ pre-screen/);
  assert.match(text, /The judge proposed supported, the pre-screen contradicted\. A human decides\./);
});

test("a hash opens a run's Grades tab at a topic, as the compare page links it", async () => {
  const hash = `#${new URLSearchParams({run: RESULT_PATHS.transcript, view: "grades", topic: "T02", criterion: "T02.01"})}`;
  const {$, viewer, location} = loadViewer(resultRoutes(), {hash});
  await settle();
  assert.equal(viewer.view, "grades");
  const opened = descendants($("grades-body")).find(node => node.id === "criterion-T02.01");
  assert.equal(opened.open, true);
  assert.match(location.hash, /view=grades/);
  assert.match(location.hash, /topic=T02/);
});

test("the compare page shows the provisional banner and opens a run's Grades tab at the clicked topic", async () => {
  const {$, viewer, location} = loadViewer(resultRoutes(), {pathname: "/compare"});
  await settle();
  assert.ok(viewer.compare, "the compact results were loaded");
  assert.equal($("compare-view").hidden, false);
  assert.equal($("office-view").hidden, true);
  assert.equal($("run-controls").hidden, true);
  const text = $("compare-body").textContent;
  assert.match(text, /Provisional — awaiting human sign-off\. Each cell counts one run’s criteria in one topic\. There is no overall score, threshold, ranking or winner/);
  assert.ok(text.indexOf("gb-2019-full-investigation") < text.indexOf("gb-2019-system-response"));
  assert.match(text, /Not graded for content: the run is incomplete \(output-token budget exhausted\)\./);
  assert.match(text, /The numbers under each bar read full · half · zero · no proposal; the line below counts the values awaiting a human decision\./);
  const cells = buttons($("compare-body"), "cell");
  assert.ok(cells.length > 0);
  assert.match(cells[0].getAttribute("aria-label"), /T02: 1 full · 1 half · 1 zero · 1 no proposal\. 3 of 4 awaiting a human decision \(1 judge proposal · 1 pre-screen proposal · 1 with no proposal\) · 1 human decision\. Open this run’s Grades tab at T02\./);
  assert.equal(cells[0].textContent, "1·1·1·13 awaiting", "the counts, then the values awaiting a human");
  cells[0].click();
  assert.equal(location.href, `/#${new URLSearchParams({run: "archive/old/transcript.json", view: "grades", topic: "T02"})}`);
});

test("the Grades tab shows a capped judge value as capped, with what the judge proposed and why", async () => {
  const {$, viewer} = loadViewer(resultRoutes({grade: CAPPED_GRADE}));
  await settle();
  viewer.setView("grades");
  await settle();
  let text = $("grades-body").textContent;
  assert.match(text, /3 of 3 awaiting a human decision \(1 judge proposal · 2 judge proposals capped by automated checks\)/);
  assert.match(text, /▸T07.*1 full · 0 half · 1 zero · 0 no proposal2 of 2 awaiting a human decision \(1 judge proposal · 1 judge proposal capped by an automated check\)/);
  viewer.toggleTopic("T07");
  text = $("grades-body").textContent;
  assert.match(text, /T07\.04Underlying causes remain unestablishedZeroCapped by automated checkjudge proposed Fulljudge ≠ pre-screen/);
  assert.doesNotMatch(text, /T07\.04Underlying causes remain unestablishedZeroJudge proposal/, "the judge did not propose Zero");
  assert.match(text, /Capped by an automated check\. Content coverage: the judge proposed Full \(1\); suspected severe flag SF1 caps it to Zero \(0\)\. A suspected severe flag applies unless a reviewer rejects it\. The value shown is the capped one, not the judge’s; neither is a decision\. A human decides\./);
  // The grade's own basis, with its cap note, is shown beside the pre-screen basis.
  assert.match(text, /Automated \(pre-screen\) basissuspected severe flag SF1/);
  assert.match(text, /Content basis, as grade\.json records itjudge proposal \(judge proposed 1; capped to 0 by automated check\(s\) SF1\): F09 keeps both causes open\./);
  // An uncapped judge value repeats no basis: its rationale is shown once.
  assert.equal(text.split("F09 states it.").length - 1, 1);
  viewer.toggleTopic("T02");
  assert.match($("grades-body").textContent, /T02\.06Ofgem's 1,990 MW kept on its own basisHalfCapped by automated checkjudge proposed Full/);
  assert.match($("grades-body").textContent, /the judge proposed Full \(1\); accounting cap ofgem_1990_on_wrong_basis \(F17\) caps it to Half \(0\.5\)\. The value shown/);
  viewer.setMeasure("content", true);
  assert.match($("grades-body").textContent, /T07\.04Underlying causes remain unestablishedPendingCapped judge proposal not counted/);
});

test("controls that rebuild a view keep the keyboard focus on the control that was used", async () => {
  const fire = (node, type, target) => node.listeners[type].forEach(listener => listener({target}));
  const keyedIn = (root, key) => descendants(root).find(node => node.dataset?.focusKey === key);
  // Compare: the count toggle, a filter select and the archive checkbox.
  const compare = loadViewer(resultRoutes(), {pathname: "/compare"});
  await settle();
  const body = compare.$("compare-body");
  let used = buttons(body, "").find(node => node.textContent === "Decided only");
  used.click();
  assert.notEqual(FakeNode.focused, used, "the page was rebuilt");
  assert.equal(FakeNode.focused, keyedIn(body, "count:true"));
  assert.equal(FakeNode.focused.getAttribute("aria-pressed"), "true");
  fire(keyedIn(body, "measure"), "change", {value: "evidence"});
  assert.equal(FakeNode.focused, keyedIn(body, "measure"));
  assert.equal(FakeNode.focused.value, "evidence");
  fire(keyedIn(body, "archived"), "change", {checked: false});
  assert.equal(FakeNode.focused, keyedIn(body, "archived"));
  assert.equal(FakeNode.focused.checked, false);
  // Grades: the count toggle and a measure card's button.
  const {$, viewer} = loadViewer(resultRoutes());
  await settle();
  viewer.setView("grades");
  await settle();
  used = buttons($("grades-body"), "").find(node => node.textContent === "Decided only");
  used.click();
  assert.equal(FakeNode.focused, keyedIn($("grades-body"), "count:true"));
  assert.notEqual(FakeNode.focused, used);
  buttons($("grades-body"), "").find(node => node.dataset.focusKey === "show:evidence").click();
  assert.equal(FakeNode.focused, keyedIn($("grades-body"), "show:evidence"));
  assert.equal(FakeNode.focused.textContent, "Shown by topic below");
  // Report: a status filter.
  viewer.setView("report");
  await settle();
  used = keyedIn($("report-body"), "status:observed");
  used.click();
  assert.equal(FakeNode.focused, keyedIn($("report-body"), "status:observed"));
  assert.notEqual(FakeNode.focused, used);
  assert.equal(FakeNode.focused.getAttribute("aria-pressed"), "true");
});

test("the Report renders a nested list inside its item, with the item's paragraph after it", async () => {
  const submission = {...RESULT_SUBMISSION, report: {executive_summary: NESTED_SUMMARY, sections: []}};
  const {$, viewer} = loadViewer(resultRoutes({submission}));
  await settle();
  viewer.setView("report");
  await settle();
  const list = descendants($("report-body")).find(node => node.tagName === "ul");
  assert.equal(list.children.length, 2);
  const barford = list.children[1], nested = barford.children.find(node => node.tagName === "ul");
  assert.equal(nested.children.length, 3);
  assert.doesNotMatch(nested.children[2].textContent, /discrepancy|F11/);
  assert.match(barford.textContent, /GT1B, 187 MW, at about 16:53:58\.6 BST\. The steam turbine trip is reported to come from a discrepancy/);
  assert.ok(barford.nodes.indexOf(nested) < barford.nodes.findIndex(node => /F11/.test(node.textContent)));
});

test("the report fits a 390 px screen: its column can shrink and long chips and reference groups wrap", () => {
  const css = html.match(/<style>([\s\S]*?)<\/style>/)[1];
  const media = width => css.match(new RegExp(`@media\\(max-width:${width}px\\)\\{([^@]*)\\}`, "g")).join("");
  // A 1fr track cannot shrink below its content; minmax(0,1fr) can.
  assert.match(media(800), /\.report-grid\{grid-template-columns:minmax\(0,1fr\)\}/);
  assert.match(css, /\.finding-card \.meta-line \.chip\{white-space:normal\}/, "flag chips wrap inside the finding card");
  assert.match(css, /\.finding-card \.meta-line>\*\{min-width:0;max-width:100%;overflow-wrap:anywhere\}/);
  assert.match(media(520), /\.refs\{white-space:normal\}/, "a long [F..] group wraps on a phone");
});

test("live mode and runs without a submission explain what the results views can show", async () => {
  const records = srTrace();
  const live = loadViewer(url => url === "/api/config" ? {live: true, episode_dir: "episode"} : url === "/api/runs" ? {runs: []} :
    url.startsWith("/api/live") ? {records: records.slice(0, 2), offset: 100, waiting: false, state: {}, episode: {}} : undefined);
  await settle();
  live.viewer.setView("report");
  assert.match(live.$("report-body").textContent, /appears once the run is saved under out\//);
  const bare = {run_id: "no-submission", events: [
    {type: "task_started", task_id: "gb-2019-system-response", model: "m", timestamp: "2026-10-20T10:00:00Z"},
    {type: "scoring", scoring: {score: 0, metadata: {outcome: "incomplete_submission", incomplete_reason: "final_message_without_submission"}}}]};
  const none = loadViewer(resultRoutes({transcript: bare, run: {submission_path: null, grade_path: null, judge: null,
    metrics: {outcome: "incomplete_submission", incomplete_reason: "final_message_without_submission"}}}));
  await settle();
  none.viewer.setView("report");
  await settle();
  assert.match(none.$("report-body").textContent, /No accepted submission in this run \(run incomplete — ended without an accepted submission\)/);
  none.viewer.setView("grades");
  await settle();
  assert.match(none.$("grades-body").textContent, /No grade\.json accompanies this run\./);
});

// Saved runs, when present: the decision log's pilot count and the grader's own flags.
test("actual full-investigation pilot: 83 full, 21 half, 2 zero best available; 13 judge-mode disagreements",
  optionalFixture("fi_pilot/gb2019-fi-pilot-opus55-001_artifacts/episode/judge/grade.json"), () => {
  const grade = JSON.parse(fs.readFileSync(path.join(root, "fi_pilot/gb2019-fi-pilot-opus55-001_artifacts/episode/judge/grade.json"), "utf8"));
  assert.deepEqual(R.measureCounts(grade).counts, {full: 83, half: 21, zero: 2, pending: 0});
  assert.deepEqual(R.measureCounts(grade, {decidedOnly: true}).counts, {full: 4, half: 0, zero: 0, pending: 102});
  assert.deepEqual(R.measureCounts(grade).sources, {prescreen: 49, judge: 53, auto: 4});
  const disagreements = R.criteriaOf(grade).filter(c => c.assessment_mode === "judge" && R.disagreementOf(c.content));
  assert.equal(disagreements.length, 13);
  assert.equal(R.topicSummaries(grade).length, 20);
});

for (const [relative, disagreements] of [
  ["panel_sr80k/opus55-001/gb2019-sr80k-opus55-001_artifacts/episode/judge/grade.json", 6],
  ["panel_sr80k/haiku45-001/gb2019-sr80k-haiku45-001_artifacts/episode/judge/grade.json", 8],
]) {
  test(`actual judged grade ${relative.split("/")[1]} lists its judge and pre-screen disagreements`, optionalFixture(relative), () => {
    const grade = JSON.parse(fs.readFileSync(path.join(root, relative), "utf8"));
    assert.equal(R.criteriaOf(grade).filter(c => R.disagreementOf(c.content)).length, disagreements);
    const counts = R.measureCounts(grade).counts;
    assert.equal(counts.full + counts.half + counts.zero + counts.pending, 60);
  });
}

for (const relative of ["panel/opus55-002/gb2019-v2-opus55-002_artifacts", "panel_sr80k/sonnet55-001/gb2019-sr80k-sonnet55-001_artifacts",
  "fi_pilot/gb2019-fi-pilot-opus55-001_artifacts", "fi/reference/gb2019-fi-fake-reference_artifacts"]) {
  test(`actual report references in ${relative.split("/")[0]} match the grader's unreferenced-findings flag`,
    optionalFixture(path.join(relative, "episode/submission.json")), () => {
    const submission = JSON.parse(fs.readFileSync(path.join(root, relative, "episode/submission.json"), "utf8"));
    const gradePath = [path.join(relative, "episode/judge/grade.json"), path.join(relative, "grade.json")].find(file => fs.existsSync(path.join(root, file)));
    const grade = JSON.parse(fs.readFileSync(path.join(root, gradePath), "utf8"));
    const report = R.reportOf(submission);
    const unreferenced = report.findings.map(f => String(f.finding_id)).filter(id => !report.referencedIn.has(id));
    assert.deepEqual(unreferenced, grade.flags.findings_not_referenced_in_report);
    const checks = R.citationChecks(grade);
    assert.equal(checks.size, grade.citations.length);
  });
}

// The judged panel runs: capped judge values are counted under their own source, and the
// values awaiting a human match the grade's own judge and pending counts.
for (const [relative, capped] of [
  ["panel_fi/opus55-001/gb2019-fi-opus55-001_artifacts/episode/judge/grade.json", ["T07.04", "T07.05", "T14.02", "T17.01", "T20.03", "T20.06"]],
  ["panel_sr80k/sonnet55-001/gb2019-sr80k-sonnet55-001_artifacts/episode/judge/grade.json", ["T02.06", "T07.04", "T07.05", "T17.01"]],
  ["fi_pilot/gb2019-fi-pilot-opus55-001_artifacts/episode/judge/grade.json", []],
]) {
  test(`actual judged grade ${relative.split("/")[0]} names ${capped.length} capped values and its values awaiting a human`, optionalFixture(relative), () => {
    const grade = JSON.parse(fs.readFileSync(path.join(root, relative), "utf8"));
    assert.deepEqual(R.criteriaOf(grade).filter(c => R.attribute(c.content).source === "capped").map(c => c.criterion_id), capped);
    for (const id of capped) {
      const detail = R.criterionDetail(R.criteriaOf(grade).find(c => c.criterion_id === id));
      assert.ok(detail.content.cap.judge > detail.content.cap.value, id);
      assert.ok(detail.content.cap.by.length > 0, `${id} names its cap`);
    }
    const tally = section => Object.values(grade[section].by_task).reduce((acc, task) => {
      for (const [source, n] of Object.entries(task.by_source || {})) acc[source] = (acc[source] || 0) + n;
      return acc;
    }, {});
    for (const [measure, section] of [["content", "content_coverage"], ["evidence", "evidence_support"]]) {
      const own = tally(section), counts = R.measureCounts(grade, {measure});
      assert.equal(counts.awaiting, own.judge + own.pending, `${measure}: the grade's judge and pending values await a human`);
      assert.equal(R.measureCounts(grade, {measure, decidedOnly: true}).awaiting, counts.awaiting);
    }
    const own = grade.assertion_quality.counts_all_tasks.by_source;
    assert.equal(R.measureCounts(grade, {measure: "assertions"}).awaiting, own.judge + own.pending);
    const sources = R.measureCounts(grade).sources;
    assert.equal((sources.judge || 0) + (sources.capped || 0), tally("content_coverage").judge);
  });
}

test("actual MVP opus55-002 executive summary keeps Little Barford's steps nested and its causes on its own item",
  optionalFixture("panel/opus55-002/gb2019-v2-opus55-002_artifacts/episode/submission.json"), () => {
  const submission = JSON.parse(fs.readFileSync(path.join(root, "panel/opus55-002/gb2019-v2-opus55-002_artifacts/episode/submission.json"), "utf8"));
  const summary = R.reportOf(submission).sections[0], list = summary.blocks.find(block => block.type === "list");
  assert.equal(list.items.length, 2);
  const barford = list.items[1], nested = barford.find(token => token.list).list;
  assert.equal(nested.items.length, 3);
  assert.deepEqual(refsOf(nested.items[2]), []);
  assert.deepEqual(refsOf(barford), ["F10", "F11", "F12", "F13"]);
});
