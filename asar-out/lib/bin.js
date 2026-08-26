
#!/usr/bin/env node
import { spawn } from "node:child_process";
import { mkdirSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join, posix, resolve, win32 } from "node:path";
import { fileURLToPath } from "node:url";
import { Worker } from "node:worker_threads";
//#region src/lifecycle-events.ts
const EVIDENCE_DIRECTORY_NAME = "lifecycle-events";
const EVIDENCE_FILENAME = "startup.jsonl";
function desktopLifecycleEvidencePath(userDataDir) {
	return join(userDataDir, EVIDENCE_DIRECTORY_NAME, EVIDENCE_FILENAME);
}
/** Stop an export that cannot complete because its Worker or filesystem is wedged. */
const DIAGNOSTIC_EXPORT_TIMEOUT_MS = 6e4;
function workerEntryUrl() {
	const extension = import.meta.url.endsWith(".ts") ? "ts" : "js";
	return new URL(`./diagnostic-export-worker.${extension}`, import.meta.url);
}
/** Wait for one diagnostic Worker result and terminate it when it stops responding. */
function waitForDiagnosticExportWorker(worker, timeoutMs = DIAGNOSTIC_EXPORT_TIMEOUT_MS, signal) {
	return new Promise((resolve, reject) => {
		let settled = false;
		let timeout;
		const settle = (complete, terminate) => {
			if (settled) return;
			settled = true;
			if (timeout !== void 0) clearTimeout(timeout);
			signal?.removeEventListener("abort", abort);
			if (terminate) worker.terminate().catch(() => {});
			complete();
		};
		const abort = () => {
			settle(() => reject(new DOMException("Diagnostic export was cancelled.", "AbortError")), true);
		};
		timeout = setTimeout(() => {
			settle(() => reject(/* @__PURE__ */ new Error(`dsh-plugin-desktop: diagnostic export worker timed out after ${String(timeoutMs)}ms`)), true);
		}, timeoutMs);
		worker.once("message", (result) => {
			if (result.ok) settle(() => resolve(result.path), true);
			else settle(() => reject(new Error(result.error)), true);
		});
		worker.once("error", (cause) => settle(() => reject(cause), true));
		worker.once("exit", (code) => {
			settle(() => reject(/* @__PURE__ */ new Error(`dsh-plugin-desktop: diagnostic export worker exited with code ${String(code)}`)), false);
		});
		signal?.addEventListener("abort", abort, { once: true });
		if (signal?.aborted === true) abort();
	});
}
/** Write a diagnostics zip in a short-lived worker and return its published path. */
function exportDiagnosticsZip(logsDir, userDataDir, options) {
	const maxEvidenceBytes = options.maxEvidenceBytes ?? 52428800;
	if (!Number.isSafeInteger(maxEvidenceBytes) || maxEvidenceBytes <= 0) return Promise.reject(/* @__PURE__ */ new Error("dsh-plugin-desktop: diagnostic evidence byte limit must be a positive integer"));
	if (options.appVersion.length === 0 || options.appVersion.length > 512 || /[\0\r\n]/u.test(options.appVersion)) return Promise.reject(/* @__PURE__ */ new Error("dsh-plugin-desktop: diagnostic app version must be a single non-empty line"));
	return waitForDiagnosticExportWorker(new Worker(workerEntryUrl(), {
		name: "dsh-diagnostic-export",
		workerData: {
			logsDir,
			userDataDir,
			appVersion: options.appVersion,
			maxEvidenceBytes,
			...options.crashDumpsDir === void 0 ? {} : { crashDumpsDir: options.crashDumpsDir },
			...options.runStatePath === void 0 ? {} : { runStatePath: options.runStatePath },
			...options.lifecycleEvidencePath === void 0 ? {} : { lifecycleEvidencePath: options.lifecycleEvidencePath }
		},
		resourceLimits: { maxOldGenerationSizeMb: 256 }
	}), DIAGNOSTIC_EXPORT_TIMEOUT_MS, options.signal);
}
/** Export diagnostics directly from Desktop user data without booting Host, profiles, or a window. */
function exportDesktopDiagnostics(userDataDir, options) {
	const logsDir = join(userDataDir, "logs");
	mkdirSync(logsDir, { recursive: true });
	return exportDiagnosticsZip(logsDir, userDataDir, {
		appVersion: options.appVersion,
		crashDumpsDir: options.crashDumpsDir ?? join(userDataDir, "Crashpad"),
		runStatePath: join(userDataDir, "crash-evidence", "active-run.json"),
		lifecycleEvidencePath: desktopLifecycleEvidencePath(userDataDir),
		...options.maxEvidenceBytes === void 0 ? {} : { maxEvidenceBytes: options.maxEvidenceBytes },
		...options.signal === void 0 ? {} : { signal: options.signal }
	});
}
//#endregion
//#region src/bin.ts
/** Headless-safe npm launcher for the DSH Desktop Electron executable. */
/** Human-readable launcher help. */
const DESKTOP_CLI_HELP = `Usage: dsh-plugin-desktop [options]

Launch DSH Desktop with the selected Web-capable profile.

Options:
  --export-diagnostics  export logs and crash evidence without launching the app
  -h, --help            display help
  -V, --version         display version
`;
/**
* Parse the intentionally small npm-launcher argument set.
* @param argv - arguments after the executable and script path.
* @returns the requested action.
*/
function parseDesktopCli(argv) {
	if (argv.length === 0) return "launch";
	if (argv.length === 1 && argv[0] === "--export-diagnostics") return "export-diagnostics";
	if (argv.length === 1 && (argv[0] === "--help" || argv[0] === "-h")) return "help";
	if (argv.length === 1 && (argv[0] === "--version" || argv[0] === "-V")) return "version";
	throw new Error(`unknown arguments: ${argv.join(" ")}`);
}
/** Read the package version without importing Electron. */
function packageVersion() {
	const manifest = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
	if (typeof manifest.version !== "string") throw new Error("package.json has no string version");
	return manifest.version;
}
/** Resolve the Electron user-data location without importing Electron. */
function defaultDesktopUserDataDirectory(platform = process.platform, environment = process.env, homeDirectory = homedir()) {
	const path = platform === "win32" ? win32 : posix;
	if (platform === "win32") {
		const appData = environment.APPDATA;
		if (appData === void 0 || appData.length === 0) throw new Error("APPDATA is unavailable; cannot locate DSH Desktop diagnostics");
		return path.join(appData, "DSH Desktop");
	}
	if (platform === "darwin") return path.join(homeDirectory, "Library", "Application Support", "DSH Desktop");
	const config = environment.XDG_CONFIG_HOME;
	return path.join(config === void 0 || config.length === 0 ? path.join(homeDirectory, ".config") : config, "DSH Desktop");
}
/** Launch Electron and mirror its terminal exit status. */
async function launchElectron() {
	let electronPath;
	try {
		const candidate = (await import("electron")).default;
		if (typeof candidate !== "string") throw new Error("electron package did not provide its executable path");
		electronPath = candidate;
	} catch {
		process.stderr.write("dsh-plugin-desktop: electron is not available in this installation.\nInstall the desktop launcher globally (npm installs the electron peer automatically):\n  npm install -g dsh-plugin-desktop\nOr add electron to the profile before launching:\n  dsh plugin --profile <name> add electron\nOr use the packaged DSH Desktop application.\n");
		return 1;
	}
	const mainPath = fileURLToPath(new URL("./main.js", import.meta.url));
	return new Promise((resolveExit, reject) => {
		const child = spawn(electronPath, [mainPath], {
			stdio: "inherit",
			env: process.env,
			windowsHide: true
		});
		child.once("error", reject);
		child.once("exit", (code, signal) => {
			resolveExit(code ?? (signal === null ? 1 : 128));
		});
	});
}
/**
* Run the npm launcher.
* @param argv - arguments after the executable and script path.
* @returns process exit code.
*/
async function runDesktopCli(argv, options = {}) {
	let action;
	try {
		action = parseDesktopCli(argv);
	} catch (cause) {
		process.stderr.write(`dsh-plugin-desktop: ${cause instanceof Error ? cause.message : String(cause)}\n`);
		process.stderr.write(DESKTOP_CLI_HELP);
		return 1;
	}
	if (action === "help") {
		process.stdout.write(DESKTOP_CLI_HELP);
		return 0;
	}
	if (action === "version") {
		process.stdout.write(`${packageVersion()}\n`);
		return 0;
	}
	if (action === "export-diagnostics") {
		const path = await exportDesktopDiagnostics(options.userDataDir ?? defaultDesktopUserDataDirectory(), { appVersion: packageVersion() });
		process.stdout.write(`${path}\n`);
		return 0;
	}
	return launchElectron();
}
if ((process.argv[1] === void 0 ? void 0 : resolve(process.argv[1])) === fileURLToPath(import.meta.url)) runDesktopCli(process.argv.slice(2)).then((code) => {
	process.exitCode = code;
}, (cause) => {
	process.stderr.write(`dsh-plugin-desktop: ${cause instanceof Error ? cause.stack ?? cause.message : String(cause)}\n`);
	process.exitCode = 1;
});
//#endregion
export { DESKTOP_CLI_HELP, defaultDesktopUserDataDirectory, parseDesktopCli, runDesktopCli };

//# sourceMappingURL=bin.js.ma