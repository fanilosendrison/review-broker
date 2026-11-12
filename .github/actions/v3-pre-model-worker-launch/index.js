'use strict';

const { spawnSync } = require('node:child_process');
const path = require('node:path');
const { constants } = require('node:os');

const ALLOWED = Object.freeze([
  'PATH', 'HOME', 'LANG', 'TMPDIR',
  'GITHUB_REPOSITORY', 'GITHUB_REPOSITORY_ID', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT',
  'GITHUB_JOB', 'GITHUB_WORKFLOW', 'GITHUB_WORKFLOW_REF', 'GITHUB_WORKFLOW_SHA',
  'GITHUB_SHA', 'GITHUB_REF', 'GITHUB_EVENT_NAME', 'GITHUB_ACTOR', 'GITHUB_ACTOR_ID',
  'GITHUB_TRIGGERING_ACTOR', 'GITHUB_API_URL', 'GITHUB_SERVER_URL',
  'ACTIONS_RUNTIME_TOKEN', 'ACTIONS_RUNTIME_URL', 'ACTIONS_RESULTS_URL',
  'GITHUB_TOKEN', 'REVIEW_BROKER_SOURCE_TOKEN', 'REVIEW_BROKER_SOURCE_APP_SLUG',
  'REVIEW_BROKER_SOURCE_INSTALLATION_ID', 'REVIEW_BROKER_ARTIFACT_HELPER_ROOT',
]);

function plan() {
  if (process.env.REVIEW_BROKER_SOURCE_APP_PRIVATE_KEY || process.env.INPUT_PRIVATE_KEY || process.env['INPUT_PRIVATE-KEY']) {
    throw new Error('SOURCE_PRIVATE_KEY_FORBIDDEN');
  }
  const request = process.env['INPUT_REQUEST-ID'];
  const reservation = process.env['INPUT_RESERVATION-ID'];
  const generation = process.env.INPUT_GENERATION;
  if (!/^request:sha256:[0-9a-f]{64}$/.test(request || '') ||
      !/^preparation-dispatch:sha256:[0-9a-f]{64}$/.test(reservation || '') ||
      generation !== '1') {
    throw new Error('INITIAL_WORKER_INPUTS_REQUIRED');
  }
  for (const key of ['ACTIONS_RUNTIME_TOKEN', 'ACTIONS_RESULTS_URL', 'GITHUB_TOKEN',
    'REVIEW_BROKER_SOURCE_TOKEN', 'REVIEW_BROKER_ARTIFACT_HELPER_ROOT']) {
    if (!process.env[key]) throw new Error('WORKER_RUNNER_CONTEXT_MISSING');
  }
  if (!path.isAbsolute(process.execPath)) throw new Error('NODE_EXECUTABLE_NOT_ABSOLUTE');
  const environment = {};
  for (const key of ALLOWED) {
    if (process.env[key] !== undefined) environment[key] = process.env[key];
  }
  // This value is never taken from workflow input, PATH or ambient environment.
  environment.REVIEW_BROKER_NODE_EXECUTABLE = process.execPath;
  return {
    executable: 'python',
    args: ['-m', 'review_broker.cli', 'internal-v3-pre-model-worker',
      '--request-id', request, '--reservation-id', reservation, '--generation', generation],
    environment,
  };
}

function launch(spawn = spawnSync) {
  const invocation = plan();
  // One call only. No shell, provider I/O, packet work or continuation after exit.
  const child = spawn(invocation.executable, invocation.args, {
    env: invocation.environment, stdio: 'inherit', shell: false,
  });
  if (Number.isInteger(child.status)) return child.status;
  if (child.signal) return 128 + (constants.signals[child.signal] || 0);
  return 1;
}

module.exports = { plan, launch };
if (require.main === module) {
  try {
    process.exitCode = launch();
  } catch (_) {
    process.stderr.write('WORKER_LAUNCH_REJECTED\n');
    process.exitCode = 1;
  }
}
