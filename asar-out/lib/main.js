
import { n as DESKTOP_SETTINGS_NAMESPACE } from "./src-BPyeBlWF.js";
import { assertDesktopProfileName, beginDesktopProfileStartup, canDeleteDesktopProfile, createDesktopWebProfile, deleteDesktopProfile, listDesktopProfiles, readDesktopProfileState, selectDesktopProfile } from "./profile-manager.js";
import { a as desktopNetworkExposureForBrowserAccess, i as desktopLoopbackBrowserUrl, n as desktopBrowserAccessEnabled, r as desktopLanBrowserUrls, t as desktopBrowserAccessAvailable } from "./desktop-network-sx9NhTqd.js";
import { a as parseWindowsWindowMaterial, i as parseMacosWindowMaterial, s as windowsSupportsMica } from "./window-material-0cOktjGz.js";
import { installProfilePackageResolver } from "./module-resolution.js";
import { t as createDesktopBrowserAccess } from "./desktop-browser-access-B6cep7Gf.js";
import { t as packagedDependencyPath } from "./packaged-runtime-path-BeoaDxsK.js";
import { DesktopPluginsService, clearDesktopProfilePluginState, readDesktopProfileBundleInventory } from "./desktop-plugins.js";
import { _ as readDesktopMarketStateForUserData, a as desktopInstallAnchor, d as prepareDesktopProfile, g as desktopMarketSnapshotWithEffective, v as selectDesktopMarketProvider } from "./profile-gjCVauUF.js";
import { DesktopProfileService } from "./profile-service.js";
import { t as PNPM_IGNORE_MINIMUM_RELEASE_AGE } from "./pnpm-policy-Dj9BWmx3.js";
import { n as desktopLocaleFromLanguageTag, r as desktopRestartConfirmationCopy } from "./tray-locale-CyKag4v-.js";
import { _ as showDesktopMessageBox, b as auxiliaryWindowChromeOptions, c as diagnoseWindowsVolumes, d as createDesktopLifecycleRecorder, f as ElectronStderrLogger, g as showDesktopDialog, h as maskSecrets, i as desktopProductVersion, l as formatWindowsVolumeConcern, m as installDesktopUncaughtExceptionLogging, p as installDesktopChildProcessLogging, s as desktopNativeCopy, t as ElectronDesktopRuntime, u as exportDesktopDiagnostics, v as applicationNeedsReveal, x as auxiliaryWindowHasCustomFrame, y as revealApplication } from "./electron-runtime-BrK7KnYi.js";
import { s as getOrCreateDesktopInstallationId } from "./update-checker-Mw2EmLOX.js";
import { installDesktopDshRuntime, installDesktopPnpmRuntime } from "./desktop-runtime-environment.js";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createHash, randomBytes, randomUUID } from "node:crypto";
import { appendFileSync, chmodSync, closeSync, constants, existsSync, fstatSync, fsyncSync, lstatSync, mkdirSync, openSync, readFileSync, readSync, readdirSync, realpathSync, renameSync, rmSync, unlinkSync, writeFileSync, writeSync } from "node:fs";
import { basename, delimiter, dirname, extname, isAbsolute, join, relative, resolve } from "node:path";
import { PROFILE_PATCH_FILENAME, boot, installFailLoud, loadLayeredEnv, resolveProfileDir } from "@deepseek-ai/dsh-app-boot";
import { userInfo } from "node:os";
import { Logger, Service } from "@deepseek-ai/cordis";
import { resolveDshHome } from "@deepseek-ai/dsh-home-paths";
import { parseDocument } from "yaml";
import { mkdir, writeFile } from "node:fs/promises";
import { writeFileAtomic } from "@deepseek-ai/dsh-atomic-write";
import { BrowserWindow, app, crashReporter, screen, shell } from "electron";
import { execFile, spawn } from "node:child_process";
import { provideCmdline } from "@deepseek-ai/dsh-cmdline";
import { DSH_LAUNCH_ENVIRONMENT_KEY } from "@deepseek-ai/dsh-launch-environment";
import { DSH_ENV_PREFIX, SENSITIVE_ENV_PATTERN, scrubbedParentEnv } from "@deepseek-ai/dsh-subprocess";
/** Return whether one process invocation belongs to the installer quit handoff. */
function isDesktopInstallerQuitRequest(argv, platform) {
	return platform === "win32" && argv.includes("--dsh-installer-quit");
}
//#endregion
//#region src/crash-evidence.ts
const PRIVATE_DIRECTORY_MODE = 448;
const PRIVATE_FILE_MODE = 384;
/** Start local-only Crashpad collection for native main and child process failures. */
function startDesktopCrashReporting(reporter, metadata) {
	reporter.start({
		productName: metadata.productName,
		uploadToServer: false,
		globalExtra: {
			appVersion: metadata.version,
			platform: metadata.platform,
			arch: metadata.arch
		}
	});
}
function lstatOptional(filename) {
	try {
		return lstatSync(filename);
	} catch (cause) {
		if (cause.code === "ENOENT") return void 0;
		throw cause;
	}
}
function assertOwnedMarker(stats) {
	if (stats.isSymbolicLink() || !stats.isFile() || stats.nlink > 1) throw new Error("dsh-plugin-desktop: active run marker is invalid");
}
function readStoredRun(statePath) {
	const pathStats = lstatOptional(statePath);
	if (pathStats === void 0) return void 0;
	assertOwnedMarker(pathStats);
	const descriptor = openSync(statePath, constants.O_RDONLY | noFollowFlag());
	try {
		assertOwnedMarker(fstatSync(descriptor));
		const value = JSON.parse(readFileSync(descriptor, "utf8"));
		if (typeof value !== "object" || value === null) return { unreadable: true };
		const record = value;
		if (typeof record.startedAt !== "string" || typeof record.pid !== "number" || typeof record.version !== "string") return { unreadable: true };
		return {
			startedAt: record.startedAt,
			pid: record.pid,
			version: record.version,
			...typeof record.ownerId === "string" ? { ownerId: record.ownerId } : {}
		};
	} catch (cause) {
		if (cause instanceof SyntaxError) return { unreadable: true };
		throw cause;
	} finally {
		closeSync(descriptor);
	}
}
function unlinkTemporary(filename) {
	try {
		unlinkSync(filename);
	} catch (cause) {
		if (cause.code !== "ENOENT") throw cause;
	}
}
function writeCurrentRun(statePath, currentRun) {
	const directory = dirname(statePath);
	mkdirSync(directory, {
		recursive: true,
		mode: PRIVATE_DIRECTORY_MODE
	});
	const directoryStats = lstatSync(directory);
	if (directoryStats.isSymbolicLink() || !directoryStats.isDirectory()) throw new Error("dsh-plugin-desktop: active run directory is invalid");
	try {
		chmodSync(directory, PRIVATE_DIRECTORY_MODE);
	} catch {}
	const temporary = join(directory, `.${basename(statePath)}.${process.pid}.${randomUUID()}.tmp`);
	try {
		writeFileSync(temporary, `${JSON.stringify(currentRun)}\n`, {
			encoding: "utf8",
			flag: "wx",
			mode: PRIVATE_FILE_MODE
		});
		try {
			chmodSync(temporary, PRIVATE_FILE_MODE);
		} catch {}
		renameSync(temporary, statePath);
	} finally {
		unlinkTemporary(temporary);
	}
}
/** Persist this launch and return a marker left behind by an unclean exit. */
function beginDesktopRun(statePath, currentRun) {
	const storedPreviousRun = readStoredRun(statePath);
	const previousRun = storedPreviousRun === void 0 || "unreadable" in storedPreviousRun ? storedPreviousRun : {
		startedAt: storedPreviousRun.startedAt,
		pid: storedPreviousRun.pid,
		version: storedPreviousRun.version
	};
	const ownerId = randomUUID();
	writeCurrentRun(statePath, {
		...currentRun,
		ownerId
	});
	let clean = false;
	return {
		previousRun,
		markClean() {
			if (clean) return;
			const storedRun = readStoredRun(statePath);
			if (storedRun === void 0 || "unreadable" in storedRun || storedRun.ownerId !== ownerId) {
				clean = true;
				return;
			}
			unlinkSync(statePath);
			clean = true;
		}
	};
}
function noFollowFlag() {
	return process.platform === "win32" ? 0 : constants.O_NOFOLLOW;
}
//#endregion
//#region src/log-level.ts
const VERBOSITY = {
	error: 0,
	warn: 1,
	info: 2,
	debug: 3
};
/** Whether a message of `type` should be emitted at `threshold`. */
function shouldEmit(type, threshold) {
	return VERBOSITY[type] <= VERBOSITY[threshold];
}
/** Whether a message of `type` belongs in the per-day error log. */
function isErrorType(type) {
	return type === "warn" || type === "error";
}
//#endregion
//#region src/log-files.ts
const OWNED_LOG_FILE = /^dsh-\d{4}-\d{2}-\d{2}(?:\.error)?(?:\.\d+)?\.log$/u;
/** Return whether a leaf name belongs to the desktop diagnostic log set. */
function isDesktopLogFileName(name) {
	return OWNED_LOG_FILE.test(name);
}
function rotationSegment(name) {
	return Number(/\.(\d+)\.log$/u.exec(name)?.[1] ?? 0);
}
function truncateUtf8(text, maxBytes) {
	if (Buffer.byteLength(text) <= maxBytes) return text;
	let bytes = 0;
	let end = 0;
	for (const character of text) {
		const next = Buffer.byteLength(character);
		if (bytes + next > maxBytes) break;
		bytes += next;
		end += character.length;
	}
	return text.slice(0, end);
}
function localDateSuffix(date) {
	return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
/** Build the file name for one date, level kind, and rotation segment. */
function logFileName(suffix, error, segment) {
	const base = `dsh-${suffix}${error ? ".error" : ""}`;
	return segment === 0 ? `${base}.log` : `${base}.${segment}.log`;
}
/** Per-day file sink with synchronous appends, size rotation, and a directory cap. */
var LogFileSink = class {
	directory;
	maxFileBytes;
	maxDirectoryBytes;
	currentDate;
	allBytes = 0;
	errorBytes = 0;
	allSegment = 0;
	errorSegment = 0;
	directoryBytes;
	constructor(directory, options) {
		this.directory = directory;
		this.maxFileBytes = options.maxFileBytes;
		this.maxDirectoryBytes = options.maxDirectoryBytes;
		if (this.maxFileBytes < 2 || this.maxDirectoryBytes < 1) throw new Error("dsh-plugin-desktop: log size limits must be positive");
		if (!existsSync(directory)) mkdirSync(directory, { recursive: true });
		const directoryStats = lstatSync(directory);
		if (directoryStats.isSymbolicLink()) throw new Error("dsh-plugin-desktop: refusing linked log directory");
		if (!directoryStats.isDirectory()) throw new Error("dsh-plugin-desktop: log path is not a directory");
		this.directoryBytes = this.measureDirectoryBytes();
	}
	/** Append one rendered line, routing by level and rotating on size/date. */
	write(type, line) {
		const suffix = localDateSuffix(/* @__PURE__ */ new Date());
		if (suffix !== this.currentDate) this.rollDate(suffix);
		const masked = maskSecrets(line);
		this.append("all", masked);
		if (isErrorType(type)) this.append("error", masked);
		if (this.directoryBytes > this.maxDirectoryBytes) this.enforceDirectoryCap();
	}
	/** Write a startup header line to the current full-log file (before ordinary lines). */
	writeHeader(line) {
		const suffix = localDateSuffix(/* @__PURE__ */ new Date());
		if (suffix !== this.currentDate) this.rollDate(suffix);
		this.append("all", line);
		if (this.directoryBytes > this.maxDirectoryBytes) this.enforceDirectoryCap();
	}
	/** Delete log files modified more than `days` days ago. */
	purgeOlderThan(days) {
		const cutoff = Date.now() - days * 24 * 60 * 60 * 1e3;
		for (const entry of this.ownedFiles()) {
			if (entry.modifiedAt >= cutoff) continue;
			try {
				unlinkSync(entry.path);
			} catch {}
		}
		this.directoryBytes = this.measureDirectoryBytes();
	}
	/** Delete every file in the directory and reset the rotation state. */
	clear() {
		for (const entry of this.ownedFiles()) try {
			unlinkSync(entry.path);
		} catch {}
		this.directoryBytes = this.measureDirectoryBytes();
		this.resetState();
	}
	/** Reset the in-memory date/rotation state (files are closed after every append). */
	close() {
		this.resetState();
	}
	/** Delete oldest files until the directory is under the cap. */
	enforceDirectoryCap() {
		const entries = this.ownedFiles().sort((a, b) => a.modifiedAt - b.modifiedAt || rotationSegment(a.name) - rotationSegment(b.name));
		let total = entries.reduce((sum, entry) => sum + entry.bytes, 0);
		let deleted = false;
		for (const entry of entries) {
			if (total <= this.maxDirectoryBytes) break;
			try {
				unlinkSync(entry.path);
				total -= entry.bytes;
				deleted = true;
			} catch {}
		}
		this.directoryBytes = total;
		if (deleted && this.currentDate !== void 0) this.rollDate(this.currentDate);
	}
	resetState() {
		this.currentDate = void 0;
		this.allBytes = 0;
		this.errorBytes = 0;
		this.allSegment = 0;
		this.errorSegment = 0;
	}
	rollDate(suffix) {
		this.currentDate = suffix;
		const all = this.loadState(suffix, false);
		const error = this.loadState(suffix, true);
		this.allBytes = all.bytes;
		this.errorBytes = error.bytes;
		this.allSegment = all.segment;
		this.errorSegment = error.segment;
	}
	loadState(suffix, error) {
		const prefix = `dsh-${suffix}${error ? ".error" : ""}`;
		let current = {
			bytes: 0,
			segment: 0
		};
		for (const entry of this.ownedFiles()) {
			const name = entry.name;
			let segment;
			if (name === `${prefix}.log`) segment = 0;
			else if (name.startsWith(`${prefix}.`) && name.endsWith(".log")) {
				const value = name.slice(prefix.length + 1, -4);
				if (/^\d+$/u.test(value)) segment = Number(value);
			}
			if (segment === void 0 || segment < current.segment) continue;
			current = {
				bytes: entry.bytes,
				segment
			};
		}
		return current;
	}
	append(kind, line) {
		const isAll = kind === "all";
		let bytes = isAll ? this.allBytes : this.errorBytes;
		let segment = isAll ? this.allSegment : this.errorSegment;
		const renderedLine = truncateUtf8(line, this.maxFileBytes - 1);
		const lineBytes = Buffer.byteLength(renderedLine) + 1;
		if (bytes + lineBytes > this.maxFileBytes) {
			segment += 1;
			bytes = 0;
		}
		let path = join(this.directory, logFileName(this.currentDate, !isAll, segment));
		while (existsSync(path)) {
			const stats = lstatSync(path);
			if (stats.isFile() && !stats.isSymbolicLink()) break;
			segment += 1;
			bytes = 0;
			path = join(this.directory, logFileName(this.currentDate, !isAll, segment));
		}
		appendFileSync(path, `${renderedLine}\n`);
		this.directoryBytes += lineBytes;
		const nextBytes = bytes + lineBytes;
		if (isAll) {
			this.allSegment = segment;
			this.allBytes = nextBytes;
		} else {
			this.errorSegment = segment;
			this.errorBytes = nextBytes;
		}
	}
	measureDirectoryBytes() {
		return this.ownedFiles().reduce((total, entry) => total + entry.bytes, 0);
	}
	ownedFiles() {
		const entries = [];
		for (const name of readdirSync(this.directory)) {
			if (!isDesktopLogFileName(name)) continue;
			const path = join(this.directory, name);
			try {
				const stats = lstatSync(path);
				if (!stats.isFile()) continue;
				entries.push({
					name,
					path,
					bytes: stats.size,
					modifiedAt: stats.mtimeMs
				});
			} catch {}
		}
		return entries;
	}
};
//#endregion
//#region src/file-exporter.ts
function localTimestamp(ts) {
	const d = new Date(ts);
	const pad = (n) => String(n).padStart(2, "0");
	return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${String(d.getMilliseconds()).padStart(3, "0")}`;
}
/** Cordis exporter that forwards formatted messages to a `LogFileSink`. */
var FileExporter = class {
	sink;
	threshold;
	formatters = {};
	maxLength = 10240;
	levels = { default: 3 };
	constructor(sink, threshold = "info") {
		this.sink = sink;
		this.threshold = threshold;
	}
	/** Update the verbosity threshold in place on a hot-reloaded setting change. */
	setThreshold(level) {
		this.threshold = level;
	}
	export(message) {
		if (!shouldEmit(message.type, this.threshold)) return;
		this.sink.write(message.type, this.render(message));
	}
	/** Close the underlying sink (used by tests and shutdown). */
	close() {
		this.sink.close();
	}
	render(message) {
		const level = message.type.charAt(0).toUpperCase();
		const body = Logger.format(this, message);
		return `${localTimestamp(message.ts)} [${level}] [${message.name}] ${body}`;
	}
};
//#endregion
//#region src/shell-environment.ts
/** Recover selected login-shell exports for packaged Unix desktop launches. */
const DEFAULT_CAPTURE_TIMEOUT_MS = 2e3;
const MAX_CAPTURE_BYTES = 1024 * 1024;
const SUPPORTED_SHELL_ARGUMENTS = /* @__PURE__ */ new Map([
	["bash", ["-ilc"]],
	["fish", [
		"--login",
		"--interactive",
		"--command"
	]],
	["zsh", ["-ilc"]]
]);
/**
* Exported rc variables that Desktop may recover in addition to PATH.
*
* Keep this list deliberately narrow: shell startup files are trusted user
* code, but their complete exported environment is not an appropriate ambient
* API for Electron or model-facing subprocesses.
*/
const DESKTOP_SHELL_ENVIRONMENT_KEYS = /* @__PURE__ */ new Set([
	"ANDROID_HOME",
	"ANDROID_SDK_ROOT",
	"ASDF_DATA_DIR",
	"ASDF_DIR",
	"BUN_INSTALL",
	"CARGO_HOME",
	"CONDA_DEFAULT_ENV",
	"CONDA_PREFIX",
	"DENO_INSTALL",
	"DOTNET_ROOT",
	"FLUTTER_ROOT",
	"GEM_HOME",
	"GEM_PATH",
	"GOBIN",
	"GOMODCACHE",
	"GOPATH",
	"GOROOT",
	"HOMEBREW_CELLAR",
	"HOMEBREW_PREFIX",
	"HOMEBREW_REPOSITORY",
	"JAVA_HOME",
	"LANG",
	"LANGUAGE",
	"MISE_CACHE_DIR",
	"MISE_CONFIG_DIR",
	"MISE_DATA_DIR",
	"MISE_STATE_DIR",
	"NVM_BIN",
	"NVM_DIR",
	"NVM_INC",
	"PNPM_HOME",
	"PYENV_ROOT",
	"RBENV_ROOT",
	"RUSTUP_HOME",
	"SDKMAN_DIR",
	"SDKROOT",
	"TZ",
	"VIRTUAL_ENV",
	"VOLTA_HOME"
]);
/**
* Parse the NUL-delimited payload emitted by the shell capture command.
* @param payload - Captured bytes from the command's private file descriptor.
* @param startMarker - Random record that begins the environment payload.
* @param endMarker - Random record that ends the environment payload.
* @returns Environment entries found between the markers.
*/
function parseShellEnvironment(payload, startMarker, endMarker) {
	const start = `${startMarker}\0`;
	const end = `${endMarker}\0`;
	const text = payload.toString("utf8");
	const startIndex = text.indexOf(start);
	if (startIndex < 0) throw new Error("desktop shell environment did not emit its start marker");
	const bodyStart = startIndex + start.length;
	const endIndex = text.indexOf(end, bodyStart);
	if (endIndex < 0) throw new Error("desktop shell environment did not emit its end marker");
	const environment = {};
	for (const record of text.slice(bodyStart, endIndex).split("\0")) {
		if (record === "") continue;
		const separator = record.indexOf("=");
		if (separator <= 0) throw new Error("desktop shell environment emitted an invalid record");
		environment[record.slice(0, separator)] = record.slice(separator + 1);
	}
	return environment;
}
/**
* Capture one interactive login shell's exported environment without accepting
* startup-file stdout or stderr as environment records.
* @param shell - Absolute zsh, bash, or fish executable.
* @param home - Working directory for shell startup.
* @param environment - Already-scrubbed environment inherited by the shell.
* @param timeoutMs - Hard deadline before the shell is killed.
* @returns Environment printed after the shell startup files finish.
*/
async function captureLoginShellEnvironment(shell, home, environment, timeoutMs = DEFAULT_CAPTURE_TIMEOUT_MS) {
	if (!isAbsolute(shell)) throw new Error("desktop shell environment requires an absolute shell path");
	const shellArguments = SUPPORTED_SHELL_ARGUMENTS.get(basename(shell).toLowerCase());
	if (shellArguments === void 0) throw new Error("desktop shell environment does not support this shell");
	const nonce = randomBytes(16).toString("hex");
	const startMarker = `dsh-shell-env-start-${nonce}`;
	const endMarker = `dsh-shell-env-end-${nonce}`;
	const command = `/usr/bin/printf '%s\\0' '${startMarker}'; /usr/bin/env -0; /usr/bin/printf '%s\\0' '${endMarker}'`;
	const child = spawn(shell, [...shellArguments, command], {
		cwd: home,
		detached: true,
		env: environment,
		stdio: [
			"ignore",
			"pipe",
			"ignore"
		],
		windowsHide: true
	});
	const killShellTree = () => {
		try {
			if (child.pid === void 0) child.kill("SIGKILL");
			else process.kill(-child.pid, "SIGKILL");
		} catch {
			try {
				child.kill("SIGKILL");
			} catch {}
		}
	};
	const output = child.stdout;
	if (output === null) {
		const closed = new Promise((resolve) => {
			child.once("error", () => {});
			child.once("close", () => {
				resolve();
			});
		});
		killShellTree();
		await closed;
		throw new Error("desktop shell environment has no capture stream");
	}
	return await new Promise((resolve, reject) => {
		const chunks = [];
		let byteLength = 0;
		let failure;
		let reading = true;
		const stopReading = () => {
			if (!reading) return;
			reading = false;
			output.off("data", accept);
		};
		const failAndKill = (error) => {
			if (failure !== void 0) return;
			failure = error;
			stopReading();
			output.destroy();
			killShellTree();
		};
		const accept = (chunk) => {
			try {
				const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
				byteLength += buffer.byteLength;
				if (byteLength > MAX_CAPTURE_BYTES) {
					failAndKill(/* @__PURE__ */ new Error(`desktop shell environment exceeded ${String(MAX_CAPTURE_BYTES)} bytes`));
					return;
				}
				chunks.push(buffer);
			} catch (error) {
				failAndKill(error instanceof Error ? error : new Error(String(error)));
			}
		};
		output.on("data", accept);
		child.once("error", failAndKill);
		const timer = setTimeout(() => {
			failAndKill(/* @__PURE__ */ new Error(`desktop shell environment timed out after ${String(timeoutMs)}ms`));
		}, timeoutMs);
		child.once("close", () => {
			clearTimeout(timer);
			stopReading();
			if (failure !== void 0) {
				reject(failure);
				return;
			}
			try {
				resolve(parseShellEnvironment(Buffer.concat(chunks), startMarker, endMarker));
			} catch (error) {
				reject(error instanceof Error ? error : new Error(String(error)));
			}
		});
	});
}
function inheritedEnvironment(fallbackReason) {
	return {
		updates: {},
		source: "process",
		fallbackReason
	};
}
function isOfficiallyScrubbedName(name) {
	return !SENSITIVE_ENV_PATTERN.test(name) && !name.toUpperCase().startsWith(DSH_ENV_PREFIX);
}
function isSelectedShellEnvironmentName(name) {
	return name === "PATH" || name.startsWith("LC_") || DESKTOP_SHELL_ENVIRONMENT_KEYS.has(name);
}
/**
* Select safe, useful login-shell exports without overriding an explicit app
* launch environment. PATH is the sole exception: its login-shell value wins.
*/
function selectDesktopShellEnvironment(captured, inherited) {
	const updates = {};
	for (const [name, value] of Object.entries(captured)) {
		if (value === void 0 || !isOfficiallyScrubbedName(name) || !isSelectedShellEnvironmentName(name)) continue;
		if (name === "PATH") {
			if (value !== "") updates.PATH = value;
			continue;
		}
		if (inherited[name] === void 0) updates[name] = value;
	}
	return updates;
}
function resolveUserShell(options) {
	if (options.shell !== void 0) return options.shell;
	try {
		const accountShell = userInfo().shell;
		if (accountShell !== "" && accountShell !== null) return accountShell;
	} catch {}
	return options.environment.SHELL;
}
/**
* Resolve selected login-shell exports for a desktop Host launch.
* @param options - Platform, launch environment and optional capture seams.
* @returns Updates for packaged Unix desktops, otherwise an empty update set.
*/
async function resolveDesktopShellEnvironment(options) {
	if (!options.isPackaged) return inheritedEnvironment("not-packaged");
	if (options.platform === "win32") return inheritedEnvironment("windows");
	if (options.platform !== "darwin" && options.platform !== "linux") return inheritedEnvironment("unsupported-platform");
	const shell = resolveUserShell(options);
	if (shell === void 0 || shell === "") return inheritedEnvironment("missing-shell");
	if (!isAbsolute(shell) || !SUPPORTED_SHELL_ARGUMENTS.has(basename(shell).toLowerCase())) return inheritedEnvironment("unsupported-shell");
	try {
		const captureEnvironment = {
			...(options.scrubParent ?? scrubbedParentEnv)(),
			HOME: options.home,
			SHELL: shell
		};
		const updates = selectDesktopShellEnvironment(await (options.capture ?? captureLoginShellEnvironment)(shell, options.home, captureEnvironment, options.timeoutMs ?? DEFAULT_CAPTURE_TIMEOUT_MS), options.environment);
		if (updates.PATH === void 0) return inheritedEnvironment("missing-path");
		return {
			updates,
			source: "login-shell"
		};
	} catch {
		return inheritedEnvironment("capture-failed");
	}
}
//#endregion
//#region src/desktop-actions.ts
/** Narrow, generation-scoped native actions available to trusted Host plugins. */
/** Publish only terminal-open and restart operations for one Cordis generation. */
var DesktopActionsService = class extends Service {
	bootstrap;
	disposed = false;
	restartCompleted = false;
	restartOperation;
	constructor(ctx, bootstrap) {
		super(ctx, "desktopActions");
		this.bootstrap = bootstrap;
		ctx.effect(() => () => {
			this.disposed = true;
		}, "dsh-plugin-desktop: desktop actions lifetime");
	}
	openTerminal() {
		this.assertActive();
		this.bootstrap.openTerminal();
	}
	requestRestart() {
		try {
			this.assertActive();
			if (this.restartCompleted) return Promise.resolve();
			if (this.restartOperation !== void 0) return this.restartOperation;
			const operation = (async () => {
				this.assertActive();
				await this.bootstrap.requestRestart();
				this.restartCompleted = true;
			})();
			this.restartOperation = operation;
			operation.catch(() => {
				if (this.restartOperation === operation) this.restartOperation = void 0;
			});
			return operation;
		} catch (cause) {
			return Promise.reject(cause);
		}
	}
	assertActive() {
		if (this.disposed) throw new Error("dsh-plugin-desktop: desktopActions service disposed");
	}
};
//#endregion
//#region src/desktop-settings-controller.ts
/** Remove paths, bundle identities, and parser diagnostics from a profile. */
function projectDesktopSettingsProfile(profile, deletable = false) {
	return Object.freeze({
		name: profile.name,
		exists: profile.exists,
		webCapable: profile.webCapable,
		selectable: profile.exists && profile.webCapable && profile.problem === void 0,
		deletable
	});
}
function projectMarket(value, effective) {
	return Object.freeze({
		requested: value.requested,
		effective,
		legacyDefaulted: value.legacyDefaulted
	});
}
/**
* Generation-scoped controller for Profile and Market preferences.
*
* The provider composed at startup remains `effective` for this controller's
* lifetime. Persisting another provider changes only `requested` until the
* queued restart creates a new Host generation.
*/
var DesktopSettingsController = class {
	bootstrap;
	effectiveMarket;
	constructor(bootstrap) {
		this.bootstrap = bootstrap;
		this.effectiveMarket = bootstrap.readMarket().effective;
	}
	/** Read a fresh, renderer-safe settings projection. */
	read() {
		const web = this.bootstrap.readWeb();
		return Object.freeze({
			current: this.bootstrap.profiles.current.name,
			profiles: Object.freeze(this.bootstrap.profiles.list().map((profile) => projectDesktopSettingsProfile(profile, this.bootstrap.profiles.canDelete?.(profile.name) ?? false))),
			market: projectMarket(this.bootstrap.readMarket(), this.effectiveMarket),
			web: Object.freeze({
				localUrl: web.localUrl,
				lanUrls: Object.freeze([...web.lanUrls])
			})
		});
	}
	/** Create one safe profile without selecting it or requesting restart. */
	createProfile(name) {
		this.bootstrap.profiles.create(name);
		return this.read();
	}
	/** Delete one inactive user profile and return the fresh settings state. */
	async deleteProfile(name) {
		if (this.bootstrap.profiles.delete === void 0) throw new Error("dsh-plugin-desktop: profile deletion is unavailable");
		await this.bootstrap.profiles.delete(name);
		return this.read();
	}
	/** Persist a fresh compatible profile, deferring restart until after response. */
	async selectProfile(name) {
		const restartRequired = name !== this.bootstrap.profiles.current.name;
		if (restartRequired) {
			const profile = this.bootstrap.profiles.list().find((candidate) => candidate.name === name);
			if (profile === void 0 || !profile.webCapable || profile.problem !== void 0) throw new Error(`dsh-plugin-desktop: profile ${JSON.stringify(name)} is not selectable`);
			await this.bootstrap.persistProfileSelection(name);
		}
		return Object.freeze({
			response: Object.freeze({
				accepted: true,
				restartRequired
			}),
			...restartRequired ? { afterResponse: () => {
				this.bootstrap.scheduleRestart();
			} } : {}
		});
	}
	/** Persist a provider and defer restart until after the response is ended. */
	async selectMarket(provider) {
		await this.bootstrap.selectMarket(provider);
		const restartRequired = provider !== this.effectiveMarket;
		return Object.freeze({
			response: Object.freeze({
				accepted: true,
				restartRequired
			}),
			...restartRequired ? { afterResponse: () => {
				this.bootstrap.scheduleRestart();
			} } : {}
		});
	}
	/** Open the native terminal through the launcher-owned action. */
	openTerminal() {
		this.bootstrap.openTerminal();
		return Object.freeze({ accepted: true });
	}
	/** Acknowledge the renderer before queueing an orderly Desktop relaunch. */
	restart() {
		return Object.freeze({
			response: Object.freeze({ accepted: true }),
			afterResponse: () => {
				this.bootstrap.scheduleRestart();
			}
		});
	}
	/** Acknowledge the renderer before queueing a recovery-mode relaunch. */
	restartToRecovery() {
		return Object.freeze({
			response: Object.freeze({ accepted: true }),
			afterResponse: () => {
				this.bootstrap.scheduleRecoveryRestart();
			}
		});
	}
	/** Acknowledge the renderer before replacing its current document. */
	reloadRenderer() {
		return Object.freeze({
			response: Object.freeze({ accepted: true }),
			afterResponse: () => {
				this.bootstrap.reloadRenderer();
			}
		});
	}
	/** Toggle Developer Tools without exposing an Electron bridge to the page. */
	toggleDeveloperTools() {
		this.bootstrap.toggleDeveloperTools();
		return Object.freeze({ accepted: true });
	}
	/** Export diagnostics through the native confirmation and reveal flow. */
	async exportDiagnostics() {
		await this.bootstrap.exportDiagnostics();
		return Object.freeze({ accepted: true });
	}
	/** Open the native creator that creates, selects, and restarts safely. */
	openProfileCreator() {
		this.bootstrap.openProfileCreator();
		return Object.freeze({ accepted: true });
	}
};
//#endregion
//#region src/startup-recovery-controller.ts
/** Pre-Host recovery-window authority over one immutable Desktop generation. */
const BIN_NAME$6 = "dsh-plugin-desktop";
const PREVIEW_TTL_MS = 300 * 1e3;
const MAX_PREVIEWS = 256;
const BUNDLE_ID_PATTERN = /^bundle_[A-Za-z0-9_-]{32}$/u;
const UNINSTALL_PREVIEW_ID_PATTERN = /^uninstall_[A-Za-z0-9_-]{43}$/u;
const RESTORE_PREVIEW_ID_PATTERN = /^restore_[A-Za-z0-9_-]{43}$/u;
const OPAQUE_ID_PATTERN = /^[A-Za-z0-9._:-]{8,160}$/u;
const MAX_DIAGNOSTIC_DETAIL_CHARS = 24e3;
var DesktopStartupRecoveryControllerError = class extends Error {
	code;
	operationStage;
	diagnosticDetail;
	constructor(code, message, options = {}) {
		super(message);
		this.code = code;
		this.name = "DesktopStartupRecoveryControllerError";
		this.operationStage = options.operationStage;
		this.diagnosticDetail = options.diagnosticDetail;
	}
};
function safeCheckpoint(slot) {
	if (!slot.snapshotExists || slot.manifest === void 0) return {
		slotId: slot.slotId,
		status: "empty"
	};
	return {
		slotId: slot.slotId,
		status: "available",
		capturedAt: slot.manifest.capturedAt,
		appVersion: slot.manifest.appVersion,
		provider: slot.manifest.provider,
		fileCount: slot.manifest.files.filter((file) => file.present).length,
		...slot.pluginCount === void 0 ? {} : { pluginCount: slot.pluginCount },
		...slot.totalBytes === void 0 ? {} : { totalBytes: slot.totalBytes }
	};
}
var DesktopStartupRecoveryController = class {
	options;
	profileName;
	generationId;
	now;
	packageBundleIds = /* @__PURE__ */ new Map();
	bundlePackages = /* @__PURE__ */ new Map();
	uninstallPreviews = /* @__PURE__ */ new Map();
	restorePreviews = /* @__PURE__ */ new Map();
	operationActive = false;
	disposed = false;
	constructor(options) {
		this.options = options;
		assertDesktopProfileName(options.pluginState.profileName);
		if (!OPAQUE_ID_PATTERN.test(options.generationId)) throw new Error(`${BIN_NAME$6}: invalid startup recovery generation id`);
		for (const [label, value] of [["Harness home", options.pluginState.homeDir], ["plugin state path", options.pluginState.statePath]]) if (!isAbsolute(value) || value.includes("\0")) throw new Error(`${BIN_NAME$6}: startup recovery ${label} must be an absolute path without NUL`);
		this.profileName = options.pluginState.profileName;
		this.generationId = options.generationId;
		this.now = options.now ?? Date.now;
	}
	async snapshot() {
		this.assertCurrentGeneration();
		try {
			const inventory = readDesktopProfileBundleInventory(this.options.pluginState);
			const checkpoints = this.options.checkpoints.listSlots().map(safeCheckpoint);
			this.assertCurrentGeneration();
			return {
				profileName: this.profileName,
				bundles: this.projectBundles(inventory),
				checkpoints
			};
		} catch (cause) {
			if (cause instanceof DesktopStartupRecoveryControllerError) throw cause;
			throw new DesktopStartupRecoveryControllerError("state-unavailable", "Desktop recovery state is unavailable.");
		}
	}
	async previewUninstall(bundleId) {
		this.assertCurrentGeneration();
		if (!BUNDLE_ID_PATTERN.test(bundleId)) throw this.invalidTarget();
		try {
			const packageName = this.bundlePackages.get(bundleId);
			if (packageName === void 0) throw this.invalidTarget();
			const inventory = readDesktopProfileBundleInventory(this.options.pluginState);
			this.assertCurrentGeneration();
			this.assertUninstallable(inventory, packageName);
			this.prunePreviews();
			this.trimPreviews(this.uninstallPreviews);
			const previewId = `uninstall_${randomBytes(32).toString("base64url")}`;
			const expiresAt = this.now() + PREVIEW_TTL_MS;
			this.uninstallPreviews.set(previewId, {
				previewId,
				bundleId,
				packageName,
				profileName: this.profileName,
				generationId: this.generationId,
				expiresAt
			});
			return {
				previewId,
				packageName,
				expiresAt: new Date(expiresAt).toISOString()
			};
		} catch (cause) {
			throw this.safeReadError(cause);
		}
	}
	async executeUninstall(previewId) {
		this.assertCurrentGeneration();
		if (!UNINSTALL_PREVIEW_ID_PATTERN.test(previewId)) throw this.expiredPreview();
		this.assertOperationAvailable();
		const preview = this.uninstallPreviews.get(previewId);
		this.uninstallPreviews.delete(previewId);
		if (preview === void 0 || preview.expiresAt <= this.now() || preview.profileName !== this.profileName || preview.generationId !== this.generationId) throw this.expiredPreview();
		this.operationActive = true;
		try {
			this.authorizeUninstall(preview.packageName);
			await this.options.uninstallPlugin(preview.packageName);
			this.assertCurrentGeneration();
			if (readDesktopProfileBundleInventory(this.options.pluginState).some((bundle) => bundle.packageName === preview.packageName)) throw new DesktopStartupRecoveryControllerError("operation-failed", "The DSH plugin command completed, but the plugin remains in the current Profile.");
			return {
				action: "uninstall",
				packageName: preview.packageName
			};
		} catch (cause) {
			throw this.safeMutationError(cause);
		} finally {
			this.operationActive = false;
		}
	}
	async previewCheckpointRestore(slotId) {
		this.assertCurrentGeneration();
		try {
			const slot = this.requireSlot(slotId);
			this.prunePreviews();
			this.trimPreviews(this.restorePreviews);
			const previewId = `restore_${randomBytes(32).toString("base64url")}`;
			const expiresAt = this.now() + PREVIEW_TTL_MS;
			this.restorePreviews.set(previewId, {
				previewId,
				slotId,
				snapshotId: slot.manifest.snapshotId,
				capturedAt: slot.manifest.capturedAt,
				profileName: this.profileName,
				generationId: this.generationId,
				expiresAt
			});
			return {
				previewId,
				slotId,
				capturedAt: slot.manifest.capturedAt,
				expiresAt: new Date(expiresAt).toISOString()
			};
		} catch (cause) {
			throw this.safeReadError(cause);
		}
	}
	async executeCheckpointRestore(previewId) {
		this.assertCurrentGeneration();
		if (!RESTORE_PREVIEW_ID_PATTERN.test(previewId)) throw this.expiredPreview();
		this.assertOperationAvailable();
		const preview = this.restorePreviews.get(previewId);
		this.restorePreviews.delete(previewId);
		if (preview === void 0 || preview.expiresAt <= this.now() || preview.profileName !== this.profileName || preview.generationId !== this.generationId) throw this.expiredPreview();
		this.operationActive = true;
		let result;
		try {
			const slot = this.requireSlot(preview.slotId);
			if (slot.manifest.snapshotId !== preview.snapshotId || slot.manifest.capturedAt !== preview.capturedAt) throw this.expiredPreview();
			result = this.options.checkpoints.restoreSlot(preview.slotId);
		} catch (cause) {
			this.operationActive = false;
			throw this.safeMutationError(cause, "checkpoint-restore");
		}
		try {
			await this.options.afterCheckpointRestore?.(result);
			this.options.checkpoints.completeDependencyMaterialization(result.slotId);
			return {
				action: "restore-checkpoint",
				slotId: result.slotId,
				changedFiles: [...result.changedFiles]
			};
		} catch (cause) {
			throw this.safeMutationError(cause, result.dependencyMaterializationRequired ? "dependency-materialization" : "checkpoint-restore");
		} finally {
			this.operationActive = false;
		}
	}
	/** Open one available slot for read-only browsing. */
	async openCheckpoint(slotId) {
		this.assertCurrentGeneration();
		try {
			const slot = this.requireSlot(slotId);
			await this.options.openCheckpointDirectory(slot.snapshotDirectory);
			this.assertCurrentGeneration();
		} catch (cause) {
			throw this.safeReadError(cause);
		}
	}
	dispose() {
		this.disposed = true;
		this.packageBundleIds.clear();
		this.bundlePackages.clear();
		this.uninstallPreviews.clear();
		this.restorePreviews.clear();
	}
	requireSlot(slotId) {
		this.assertCurrentGeneration();
		const slot = this.options.checkpoints.listSlots().find((candidate) => candidate.slotId === slotId);
		this.assertCurrentGeneration();
		if (slot === void 0 || !slot.snapshotExists || slot.manifest === void 0) throw this.invalidTarget();
		return slot;
	}
	projectBundles(inventory) {
		const activeNames = new Set(inventory.map((item) => item.packageName));
		for (const [packageName, bundleId] of this.packageBundleIds) {
			if (activeNames.has(packageName)) continue;
			this.packageBundleIds.delete(packageName);
			this.bundlePackages.delete(bundleId);
		}
		return inventory.map((item) => {
			const bundleId = this.bundleId(item.packageName);
			const owner = !item.mutable ? "core" : item.uninstallable ? "profile" : "external";
			return {
				bundleId,
				packageName: item.packageName,
				status: item.status,
				owner,
				action: item.uninstallable ? "uninstall" : null
			};
		});
	}
	bundleId(packageName) {
		let bundleId = this.packageBundleIds.get(packageName);
		if (bundleId === void 0) {
			bundleId = `bundle_${randomBytes(24).toString("base64url")}`;
			this.packageBundleIds.set(packageName, bundleId);
			this.bundlePackages.set(bundleId, packageName);
		}
		return bundleId;
	}
	authorizeUninstall(packageName) {
		this.assertCurrentGeneration();
		const inventory = readDesktopProfileBundleInventory(this.options.pluginState);
		this.assertCurrentGeneration();
		this.assertUninstallable(inventory, packageName);
	}
	assertUninstallable(inventory, packageName) {
		const target = inventory.find((item) => item.packageName === packageName);
		if (target === void 0) throw this.invalidTarget();
		if (!target.uninstallable) throw new DesktopStartupRecoveryControllerError("immutable-target", "This Desktop bundle cannot be uninstalled.");
	}
	assertCurrentGeneration() {
		if (this.disposed) throw this.generationChanged();
		let current;
		try {
			current = this.options.currentGeneration();
			assertDesktopProfileName(current.profileName);
		} catch {
			throw this.generationChanged();
		}
		if (current.profileName !== this.profileName || current.generationId !== this.generationId || !OPAQUE_ID_PATTERN.test(current.generationId)) throw this.generationChanged();
	}
	assertOperationAvailable() {
		if (this.operationActive) throw new DesktopStartupRecoveryControllerError("operation-in-progress", "Another Desktop recovery operation is already running.");
	}
	prunePreviews() {
		const now = this.now();
		for (const [id, preview] of this.uninstallPreviews) if (preview.expiresAt <= now) this.uninstallPreviews.delete(id);
		for (const [id, preview] of this.restorePreviews) if (preview.expiresAt <= now) this.restorePreviews.delete(id);
	}
	trimPreviews(previews) {
		if (previews.size < MAX_PREVIEWS) return;
		const oldest = previews.keys().next().value;
		if (oldest !== void 0) previews.delete(oldest);
	}
	safeReadError(cause) {
		if (cause instanceof DesktopStartupRecoveryControllerError) return cause;
		return new DesktopStartupRecoveryControllerError("state-unavailable", "Desktop recovery state is unavailable.");
	}
	safeMutationError(cause, operationStage = "plugin-change") {
		if (cause instanceof DesktopStartupRecoveryControllerError) {
			if (cause.operationStage !== void 0) return cause;
			return new DesktopStartupRecoveryControllerError(cause.code, cause.message, {
				operationStage,
				...cause.diagnosticDetail === void 0 ? {} : { diagnosticDetail: cause.diagnosticDetail }
			});
		}
		const rendered = maskSecrets(cause instanceof Error ? cause.stack ?? cause.message : String(cause));
		return new DesktopStartupRecoveryControllerError("operation-failed", "Unable to apply the Desktop recovery operation.", {
			operationStage,
			diagnosticDetail: rendered.length <= MAX_DIAGNOSTIC_DETAIL_CHARS ? rendered : `${rendered.slice(0, MAX_DIAGNOSTIC_DETAIL_CHARS)}\n… output truncated`
		});
	}
	invalidTarget() {
		return new DesktopStartupRecoveryControllerError("invalid-target", "The Desktop recovery target is no longer available.");
	}
	expiredPreview() {
		return new DesktopStartupRecoveryControllerError("preview-expired", "The Desktop recovery confirmation expired or was already used.");
	}
	generationChanged() {
		return new DesktopStartupRecoveryControllerError("generation-changed", "This Desktop recovery generation is no longer active.");
	}
};
//#endregion
//#region src/recovery-copy.ts
const COPY$1 = {
	en: {
		title: "DSH Desktop Recovery Assistant",
		fallbackBody: "The recovery information could not be read. Quit and start DSH Desktop again.",
		reason: "Why Recovery Mode opened",
		requestedMode: "Opened from the restart menu",
		requestedBody: "Normal startup is paused before the current Profile and plugin Host load.",
		currentProfile: "Current Profile",
		failureStage: "Failure stage",
		stageLabels: {
			"electron-ready": "Electron initialization",
			"shell-environment": "Shell environment preparation",
			"runtime-bootstrap": "Desktop runtime preparation",
			"profile-selection": "Profile selection",
			"profile-composition": "Plugin configuration composition",
			"host-boot": "Plugin Host startup",
			"renderer-startup": "Desktop interface startup",
			"health-commit": "Startup health confirmation"
		},
		tabs: {
			plugins: "Plugin management",
			rollback: "Rollback",
			profiles: "Switch Profile",
			diagnostics: "Diagnostics"
		},
		checkpoints: "Healthy-start checkpoints",
		checkpointsUnavailable: "Checkpoint information is unavailable for this startup stage.",
		rollbackBody: "Choose one of the three healthy-start slots to restore the current Profile together with shared settings.yaml and the Harness-home patch.",
		plugins: "Plugin management",
		pluginsBody: "Remove a direct plugin dependency from the current Profile with the official DSH plugin command.",
		pluginsUnavailable: "Plugin information is unavailable for this startup stage.",
		pluginsEmpty: "No plugins were found in the current Profile.",
		core: "Built in",
		profileDependency: "Direct Profile dependency",
		external: "Not directly removable",
		disabled: "Disabled",
		uninstall: "Uninstall",
		diagnostics: "Diagnostic archive",
		savingDiagnostics: "Saving a local diagnostic archive…",
		diagnosticsSaved: "The diagnostic archive was saved locally and is never uploaded automatically.",
		diagnosticsFailed: "The diagnostic archive could not be saved. You can try exporting it again.",
		saveDiagnostics: "Export diagnostics",
		showDiagnostics: "Show in folder",
		privacy: "The archive may contain local paths, logs, system information, and crash-memory fragments. Review it before sharing.",
		configurationFiles: "Configuration files",
		configurationFilesBody: "View or edit the current Profile and shared Harness-home configuration. Restart DSH Desktop after making changes.",
		openSettingsDocument: "Open settings.yaml",
		openProfilePatch: "Edit Profile patch",
		openProfileManifest: "Edit plugin manifest",
		openProfileDirectory: "Open Profile folder",
		profiles: "Available Profiles",
		profilesBody: "Select another Desktop-compatible Profile or create a new one before the plugin Host starts.",
		profilesUnavailable: "Profile switching is unavailable for this startup stage.",
		profilesEmpty: "No other Desktop-compatible Profiles are available.",
		switchProfile: "Switch",
		addProfile: "New Profile",
		openTerminal: "Open DSH Terminal",
		emptySlot: "Empty",
		availableSlot: "Available",
		noHealthyStartup: "No healthy startup has been recorded in this slot.",
		openCheckpoint: "Browse files",
		rollbackCheckpoint: "Roll back to this slot",
		desktopVersion: "DSH Desktop version",
		pluginCount: "Plugins",
		configurationFileCount: "Configuration files",
		checkpointSize: "Checkpoint size",
		unknown: "Unknown",
		restart: "Restart DSH Desktop",
		quit: "Quit",
		working: "Applying the recovery action…",
		cancel: "Cancel",
		confirmUninstall: "Uninstall this plugin?",
		confirmUninstallBody: "DSH will remove this dependency from the current Profile and reconcile its plugin layers. This does not depend on which market installed it.",
		confirmRollback: "Roll back this configuration?",
		confirmRollbackBody: (capturedAt) => `This immediately restores the current Profile plus the checkpointed settings.yaml and Harness-home patch captured at ${capturedAt}. After restarting, DSH Desktop will use the rolled-back configuration.`,
		confirmRollbackAction: "Roll Back",
		uninstalledSuccess: "The plugin was removed from the current Profile. Restart DSH Desktop to use the updated plugin configuration.",
		rollbackSuccess: (slotId) => `Rolled back to ${slotId}. Restart DSH Desktop to use this configuration; the first healthy start after rollback will preserve all three existing slots.`,
		profileSelectedSuccess: "This Profile is now selected. Restart DSH Desktop to use it.",
		actionFailed: "The recovery action could not be completed. Review the diagnostic archive and try again.",
		rollbackFailedTitle: "Rollback failed",
		rollbackFailedMessage: "The rollback did not finish. The Recovery Assistant remains open so you can review the details and try again.",
		uninstallFailedTitle: "Plugin uninstall failed",
		uninstallFailedMessage: "The plugin was not removed. The Recovery Assistant remains open so you can review the details and try again.",
		operationStage: "Operation stage",
		operationStageLabels: {
			"checkpoint-restore": "Checkpoint file restore",
			"dependency-materialization": "Profile dependency rebuild",
			"plugin-change": "DSH plugin uninstall"
		},
		errorCode: "Error code",
		technicalDetails: "Technical details",
		close: "Close"
	},
	zh: {
		title: "DSH Desktop 恢复助手",
		fallbackBody: "无法读取恢复信息。请退出并重新启动 DSH Desktop。",
		reason: "进入恢复模式的原因",
		requestedMode: "从重启菜单主动进入",
		requestedBody: "普通启动已暂停，当前 Profile 和插件 Host 尚未加载。",
		currentProfile: "当前 Profile",
		failureStage: "失败阶段",
		stageLabels: {
			"electron-ready": "Electron 初始化",
			"shell-environment": "Shell 环境准备",
			"runtime-bootstrap": "桌面运行时准备",
			"profile-selection": "Profile 选择",
			"profile-composition": "插件配置组合",
			"host-boot": "插件 Host 启动",
			"renderer-startup": "桌面界面启动",
			"health-commit": "启动健康状态确认"
		},
		tabs: {
			plugins: "插件管理",
			rollback: "回滚",
			profiles: "切换 Profile",
			diagnostics: "诊断"
		},
		checkpoints: "健康启动 Checkpoint",
		checkpointsUnavailable: "当前启动阶段无法读取 Checkpoint 信息。",
		rollbackBody: "从三个健康启动槽位中选择一个，同时恢复当前 Profile、共享 settings.yaml 和 DSH home 补丁。",
		plugins: "插件管理",
		pluginsBody: "使用官方 DSH 插件命令，从当前 Profile 中卸载直接依赖的插件。",
		pluginsUnavailable: "当前启动阶段无法读取插件信息。",
		pluginsEmpty: "当前 Profile 中没有插件。",
		core: "内置组件",
		profileDependency: "Profile 直接依赖",
		external: "不可直接卸载",
		disabled: "已禁用",
		uninstall: "卸载",
		diagnostics: "诊断包",
		savingDiagnostics: "正在保存本地诊断包…",
		diagnosticsSaved: "诊断包已保存在本地，不会自动上传。",
		diagnosticsFailed: "无法保存诊断包，可以重新尝试导出。",
		saveDiagnostics: "导出诊断",
		showDiagnostics: "在文件夹中显示",
		privacy: "诊断包可能包含本地路径、日志、系统信息和崩溃内存片段，分享前请先检查。",
		configurationFiles: "配置文件",
		configurationFilesBody: "查看或编辑当前 Profile 与 DSH home 的共享配置。修改后需要重新启动 DSH Desktop。",
		openSettingsDocument: "打开 settings.yaml",
		openProfilePatch: "编辑 Profile 补丁",
		openProfileManifest: "编辑插件清单",
		openProfileDirectory: "打开 Profile 目录",
		profiles: "可用 Profile",
		profilesBody: "在插件 Host 启动前切换到其他支持桌面端的 Profile，或新建一个 Profile。",
		profilesUnavailable: "当前启动阶段无法切换 Profile。",
		profilesEmpty: "没有其他支持桌面端的 Profile。",
		switchProfile: "切换",
		addProfile: "新建 Profile",
		openTerminal: "打开 DSH 终端",
		emptySlot: "空槽位",
		availableSlot: "可回滚",
		noHealthyStartup: "此槽位尚未记录健康启动。",
		openCheckpoint: "浏览文件",
		rollbackCheckpoint: "回滚到此槽位",
		desktopVersion: "DSH Desktop 版本",
		pluginCount: "插件",
		configurationFileCount: "配置文件",
		checkpointSize: "Checkpoint 大小",
		unknown: "未知",
		restart: "重启 DSH Desktop",
		quit: "退出",
		working: "正在执行恢复操作…",
		cancel: "取消",
		confirmUninstall: "卸载这个插件？",
		confirmUninstallBody: "DSH 将从当前 Profile 中移除此依赖，并重新整理插件层。无论插件由哪个市场安装，都会使用相同的卸载流程。",
		confirmRollback: "回滚这套配置？",
		confirmRollbackBody: (capturedAt) => `将立即恢复 ${capturedAt} 创建的 Checkpoint 中的当前 Profile、settings.yaml 与 DSH home 补丁；重启后，DSH Desktop 将使用回滚后的配置。`,
		confirmRollbackAction: "回滚",
		uninstalledSuccess: "插件已从当前 Profile 中卸载。请重启 DSH Desktop 以使用更新后的插件配置。",
		rollbackSuccess: (slotId) => `已回滚到${slotId}。请重启 DSH Desktop 以使用该配置；回滚后的第一次健康启动会保留现有三个槽位。`,
		profileSelectedSuccess: "已设为当前 Profile。请重启 DSH Desktop 以使用该 Profile。",
		actionFailed: "无法完成恢复操作。请检查诊断包后重试。",
		rollbackFailedTitle: "回滚失败",
		rollbackFailedMessage: "回滚未能完成。恢复助手会保持打开，你可以查看详细错误后重试。",
		uninstallFailedTitle: "插件卸载失败",
		uninstallFailedMessage: "插件未能卸载。恢复助手会保持打开，你可以查看详细错误后重试。",
		operationStage: "操作阶段",
		operationStageLabels: {
			"checkpoint-restore": "Checkpoint 文件恢复",
			"dependency-materialization": "Profile 依赖重建",
			"plugin-change": "DSH 插件卸载"
		},
		errorCode: "错误代码",
		technicalDetails: "技术详情",
		close: "关闭"
	}
};
function desktopRecoveryCopy(locale) {
	return COPY$1[locale];
}
//#endregion
//#region src/startup-recovery-window.ts
/** Host-independent Electron recovery window for profile startup failures. */
const RECOVERY_SCHEME = "dsh-recovery:";
const RECOVERY_DOCUMENT = fileURLToPath(new URL("./native-ui/recovery.html", import.meta.url));
const DEFAULT_RECOVERY_WIDTH = 800;
const DEFAULT_RECOVERY_HEIGHT = 760;
const DEFAULT_RECOVERY_MIN_WIDTH = 680;
const DEFAULT_RECOVERY_MIN_HEIGHT = 560;
const RECOVERY_WORK_AREA_INSET = 48;
function validWorkAreaSize(value) {
	if (value === void 0 || !Number.isFinite(value.width) || !Number.isFinite(value.height) || value.width < 1 || value.height < 1) return void 0;
	return {
		width: Math.floor(value.width),
		height: Math.floor(value.height)
	};
}
function currentWorkAreaSize(screenApi) {
	try {
		const current = validWorkAreaSize(screenApi.getDisplayNearestPoint(screenApi.getCursorScreenPoint()).workAreaSize);
		if (current !== void 0) return current;
	} catch {}
	try {
		return validWorkAreaSize(screenApi.getPrimaryDisplay().workAreaSize);
	} catch {
		return;
	}
}
/** Clamp recovery dimensions to the current display, with the primary display as fallback. */
function desktopStartupRecoveryWindowBounds(screenApi = screen) {
	const workArea = currentWorkAreaSize(screenApi);
	const width = workArea === void 0 ? DEFAULT_RECOVERY_WIDTH : Math.min(DEFAULT_RECOVERY_WIDTH, Math.max(1, workArea.width - RECOVERY_WORK_AREA_INSET));
	const height = workArea === void 0 ? DEFAULT_RECOVERY_HEIGHT : Math.min(DEFAULT_RECOVERY_HEIGHT, Math.max(1, workArea.height - RECOVERY_WORK_AREA_INSET));
	return {
		width,
		height,
		minWidth: Math.min(DEFAULT_RECOVERY_MIN_WIDTH, width),
		minHeight: Math.min(DEFAULT_RECOVERY_MIN_HEIGHT, height)
	};
}
/** Parse only the fixed action origin used by the local shadcn recovery document. */
function parseDesktopStartupRecoveryAction(href) {
	let url;
	try {
		url = new URL(href);
	} catch {
		return;
	}
	if (url.protocol !== RECOVERY_SCHEME || url.username.length > 0 || url.password.length > 0 || url.port.length > 0 || url.pathname !== "" || url.hash.length > 0) return void 0;
	const action = url.hostname;
	if (!(/* @__PURE__ */ new Set([
		"preview-uninstall",
		"preview-checkpoint",
		"open-checkpoint",
		"export-diagnostics",
		"show-diagnostics",
		"open-settings-document",
		"open-profile-patch",
		"open-profile-manifest",
		"open-profile-directory",
		"open-terminal",
		"open-profile-creator",
		"switch-profile",
		"restart",
		"quit"
	])).has(action)) return void 0;
	if ([...url.searchParams.keys()].some((key) => key !== "id" && key !== "name") || url.searchParams.getAll("id").length > 1 || url.searchParams.getAll("name").length > 1) return void 0;
	const id = url.searchParams.get("id") ?? void 0;
	if ((action.startsWith("preview-") || action === "switch-profile" || action === "open-checkpoint") !== (id !== void 0)) return void 0;
	if (id !== void 0 && (action === "preview-checkpoint" || action === "open-checkpoint")) {
		if (!/^slot-[123]$/u.test(id)) return void 0;
	} else if (id !== void 0 && (id.length < 8 || id.length > 160)) return void 0;
	const name = url.searchParams.get("name") ?? void 0;
	if (action === "switch-profile") {
		if (name === void 0 || name.length === 0 || Buffer.byteLength(name, "utf8") > 255 || name.includes("/") || name.includes("\\") || /[\0\r\n]/u.test(name)) return void 0;
	} else if (name !== void 0) return void 0;
	return {
		action,
		...id === void 0 ? {} : { id },
		...name === void 0 ? {} : { name }
	};
}
/** One native recovery window whose renderer has no Node, IPC, or network capability. */
var DesktopStartupRecoveryWindow = class {
	options;
	window;
	snapshot;
	snapshotError;
	diagnostics = { status: "saving" };
	diagnosticPath;
	diagnosticTask;
	diagnosticAbort = new AbortController();
	notice;
	busy = false;
	restartReady = false;
	activeTab = "plugins";
	profiles;
	resolveResult;
	settled = false;
	constructor(options) {
		this.options = options;
	}
	/** Open the local recovery document and settle only on explicit restart, quit, or close. */
	async run() {
		const copy = desktopRecoveryCopy(this.options.locale);
		const result = new Promise((resolve) => {
			this.resolveResult = resolve;
		});
		try {
			this.snapshot = await this.options.controller?.snapshot();
		} catch (cause) {
			this.snapshotError = cause instanceof Error ? cause.message : String(cause);
		}
		this.refreshProfiles();
		const window = new BrowserWindow({
			title: copy.title,
			...auxiliaryWindowChromeOptions(),
			...desktopStartupRecoveryWindowBounds(),
			show: false,
			autoHideMenuBar: true,
			backgroundColor: "#202124",
			webPreferences: {
				contextIsolation: true,
				nodeIntegration: false,
				nodeIntegrationInSubFrames: false,
				sandbox: true,
				webSecurity: true,
				webviewTag: false,
				spellcheck: false,
				partition: "dsh-recovery"
			}
		});
		this.window = window;
		window.accessibleTitle = copy.title;
		window.removeMenu();
		window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
		window.webContents.on("will-attach-webview", (event) => {
			event.preventDefault();
		});
		const navigate = (event, href) => {
			const action = parseDesktopStartupRecoveryAction(href);
			event.preventDefault();
			if (action !== void 0) this.handleAction(action);
		};
		window.webContents.on("will-navigate", navigate);
		window.webContents.on("will-redirect", navigate);
		const show = () => {
			revealApplication(window);
		};
		const activate = () => {
			if (applicationNeedsReveal(window)) show();
		};
		app.on("activate", activate);
		if (process.platform === "darwin") app.on("did-become-active", activate);
		window.once("ready-to-show", show);
		window.on("closed", () => {
			app.off("activate", activate);
			if (process.platform === "darwin") app.off("did-become-active", activate);
			this.window = void 0;
			this.finish("quit");
		});
		await this.render();
		this.startDiagnosticExport().catch(() => {});
		return await result;
	}
	/** Bring an already open recovery window to the foreground. */
	show() {
		if (this.window === void 0 || this.window.isDestroyed()) return;
		revealApplication(this.window);
	}
	async handleAction(action) {
		if (this.busy || this.settled) return;
		const copy = desktopRecoveryCopy(this.options.locale);
		try {
			if (action.action === "preview-uninstall" && action.id !== void 0) {
				this.activeTab = "plugins";
				const preview = await this.requireController().previewUninstall(action.id);
				if (await this.confirmRecoveryAction("uninstall", preview)) await this.runBusy(async () => {
					const result = await this.requireController().executeUninstall(preview.previewId);
					this.notice = {
						tone: "success",
						title: result.packageName,
						body: copy.uninstalledSuccess
					};
					this.restartReady = true;
					await this.refreshSnapshot();
				});
			} else if (action.action === "preview-checkpoint" && action.id !== void 0) {
				this.activeTab = "rollback";
				const preview = await this.requireController().previewCheckpointRestore(action.id);
				if (await this.confirmRecoveryAction("checkpoint", preview)) await this.runBusy(async () => {
					const slotNumber = (await this.requireController().executeCheckpointRestore(preview.previewId)).slotId.slice(-1);
					const slotLabel = this.options.locale === "zh" ? `槽位 ${slotNumber}` : `Slot ${slotNumber}`;
					this.notice = {
						tone: "success",
						title: slotLabel,
						body: copy.rollbackSuccess(slotLabel)
					};
					this.restartReady = true;
					await this.refreshSnapshot();
				});
			} else if (action.action === "open-checkpoint" && action.id !== void 0) {
				this.activeTab = "rollback";
				await this.requireController().openCheckpoint(action.id);
			} else if (action.action === "export-diagnostics") {
				this.activeTab = "diagnostics";
				await this.startDiagnosticExport().catch(() => {});
			} else if (action.action === "show-diagnostics" && this.diagnosticPath !== void 0) {
				this.activeTab = "diagnostics";
				shell.showItemInFolder(this.diagnosticPath);
			} else if (action.action === "open-terminal") {
				if (this.options.openTerminal === void 0) throw new Error("DSH Terminal is unavailable for this startup stage.");
				await this.options.openTerminal();
			} else if (action.action === "open-profile-creator") {
				this.activeTab = "profiles";
				if (this.options.profileActions === void 0) throw new Error("Profile creation is unavailable for this startup stage.");
				await this.options.profileActions.openCreator();
			} else if (action.action === "switch-profile" && action.id !== void 0 && action.name !== void 0) {
				this.activeTab = "profiles";
				const actions = this.options.profileActions;
				if (actions === void 0) throw new Error("Profile switching is unavailable for this startup stage.");
				const profileName = action.name;
				const actionToken = action.id;
				await this.runBusy(async () => {
					await actions.switchProfile(profileName, actionToken);
					this.notice = {
						tone: "success",
						title: profileName,
						body: copy.profileSelectedSuccess
					};
					this.restartReady = true;
					this.refreshProfiles();
				});
			} else if (action.action === "open-settings-document") {
				this.activeTab = "diagnostics";
				await this.openConfigurationPath("settingsDocument");
			} else if (action.action === "open-profile-patch") {
				this.activeTab = "diagnostics";
				await this.openConfigurationPath("profilePatch");
			} else if (action.action === "open-profile-manifest") {
				this.activeTab = "diagnostics";
				await this.openConfigurationPath("profileManifest");
			} else if (action.action === "open-profile-directory") {
				this.activeTab = "diagnostics";
				await this.openConfigurationPath("profileDirectory");
			} else if (action.action === "restart") {
				const copy = desktopRestartConfirmationCopy(this.options.locale);
				const window = this.window;
				if (window === void 0 || window.isDestroyed()) return;
				if ((await showDesktopMessageBox({
					type: "question",
					title: copy.title,
					message: copy.message,
					detail: copy.detail,
					buttons: [copy.confirm, copy.cancel],
					defaultId: 1,
					cancelId: 1,
					noLink: true
				}, window)).response === 0) this.finish("restart");
				return;
			} else if (action.action === "quit") {
				await this.ensureDiagnostics();
				this.finish("quit");
				return;
			}
		} catch (cause) {
			this.notice = {
				tone: "error",
				title: copy.title,
				body: copy.actionFailed
			};
			if (action.action === "preview-checkpoint" || action.action === "preview-uninstall") await this.showOperationFailure(cause, action.action).catch(() => {});
		}
		await this.render();
	}
	async showOperationFailure(cause, action) {
		const window = this.window;
		if (window === void 0 || window.isDestroyed()) return;
		const copy = desktopRecoveryCopy(this.options.locale);
		const error = cause instanceof DesktopStartupRecoveryControllerError ? cause : void 0;
		const stage = error?.operationStage ?? "checkpoint-restore";
		const message = error?.message ?? (cause instanceof Error ? cause.message : String(cause));
		const detail = [
			`${copy.operationStage}: ${copy.operationStageLabels[stage]}`,
			`${copy.errorCode}: ${error?.code ?? "operation-failed"}`,
			"",
			message,
			...error?.diagnosticDetail === void 0 ? [] : [
				"",
				copy.technicalDetails,
				error.diagnosticDetail
			]
		].join("\n");
		await showDesktopDialog({
			type: "error",
			title: action === "preview-checkpoint" ? copy.rollbackFailedTitle : copy.uninstallFailedTitle,
			message: action === "preview-checkpoint" ? copy.rollbackFailedMessage : copy.uninstallFailedMessage,
			detail,
			buttons: [copy.close],
			defaultId: 0,
			cancelId: 0,
			presentation: "diagnostic"
		}, window);
	}
	async confirmRecoveryAction(kind, preview) {
		const window = this.window;
		if (window === void 0 || window.isDestroyed()) return false;
		const copy = desktopRecoveryCopy(this.options.locale);
		const slotNumber = "slotId" in preview ? preview.slotId.slice(-1) : void 0;
		const message = "packageName" in preview ? preview.packageName : this.options.locale === "zh" ? `槽位 ${slotNumber}` : `Slot ${slotNumber}`;
		const checkpointTime = "capturedAt" in preview && !Number.isNaN(Date.parse(preview.capturedAt)) ? new Date(preview.capturedAt).toLocaleString(this.options.locale === "zh" ? "zh-CN" : "en-US") : copy.unknown;
		return (await showDesktopMessageBox({
			type: kind === "uninstall" ? "warning" : "question",
			title: kind === "uninstall" ? copy.confirmUninstall : copy.confirmRollback,
			message,
			detail: kind === "uninstall" ? copy.confirmUninstallBody : copy.confirmRollbackBody(checkpointTime),
			buttons: [kind === "uninstall" ? copy.uninstall : copy.confirmRollbackAction, copy.cancel],
			defaultId: 1,
			cancelId: 1,
			noLink: true
		}, window)).response === 0;
	}
	async runBusy(operation) {
		this.busy = true;
		await this.render();
		try {
			await operation();
		} finally {
			this.busy = false;
		}
	}
	async refreshSnapshot() {
		try {
			this.snapshot = await this.requireController().snapshot();
			this.snapshotError = void 0;
		} catch (cause) {
			this.snapshotError = cause instanceof Error ? cause.message : String(cause);
		}
	}
	refreshProfiles() {
		try {
			this.profiles = this.options.profileActions?.list();
		} catch {
			this.profiles = void 0;
		}
	}
	async ensureDiagnostics() {
		try {
			await this.startDiagnosticExport();
			return true;
		} catch {
			return false;
		}
	}
	startDiagnosticExport() {
		if (this.diagnostics.status === "saved" && this.diagnosticPath !== void 0) return Promise.resolve(this.diagnosticPath);
		if (this.diagnosticTask !== void 0) return this.diagnosticTask;
		const task = this.saveDiagnostics();
		this.diagnosticTask = task;
		task.catch(() => {
			if (this.diagnosticTask === task) this.diagnosticTask = void 0;
		});
		return task;
	}
	async saveDiagnostics() {
		this.diagnostics = { status: "saving" };
		await this.render();
		try {
			const path = await this.options.exportDiagnostics(this.diagnosticAbort.signal);
			this.diagnosticPath = path;
			this.diagnostics = {
				status: "saved",
				filename: basename(path)
			};
			await this.render();
			return path;
		} catch (cause) {
			this.diagnostics = { status: "failed" };
			this.notice = {
				tone: "error",
				title: desktopRecoveryCopy(this.options.locale).diagnostics,
				body: desktopRecoveryCopy(this.options.locale).diagnosticsFailed
			};
			await this.render();
			throw cause;
		}
	}
	async render() {
		const window = this.window;
		if (window === void 0 || window.isDestroyed()) return;
		const notice = this.notice;
		const model = {
			locale: this.options.locale,
			failureStage: this.options.failureStage,
			failureDetail: this.options.failureDetail,
			...this.options.requested === true ? { requested: true } : {},
			...this.snapshot === void 0 ? {} : { snapshot: this.snapshot },
			...this.snapshotError === void 0 ? {} : { snapshotError: this.snapshotError },
			diagnostics: this.diagnostics,
			...notice === void 0 ? {} : { notice },
			busy: this.busy,
			restartReady: this.restartReady,
			activeTab: this.activeTab,
			configurationAvailable: this.options.configurationPaths !== void 0,
			...this.profiles === void 0 ? {} : { profiles: this.profiles },
			...this.options.profileActions === void 0 ? {} : { profileActionToken: this.options.profileActions.token },
			...this.options.openTerminal === void 0 ? {} : { terminalAvailable: true },
			...this.options.profileActions === void 0 ? {} : { profileCreatorAvailable: true }
		};
		const state = Buffer.from(JSON.stringify(model), "utf8").toString("base64url");
		await window.loadFile(RECOVERY_DOCUMENT, { query: {
			state,
			locale: this.options.locale,
			platform: process.platform,
			frame: String(auxiliaryWindowHasCustomFrame())
		} });
		if (this.notice === notice) this.notice = void 0;
	}
	finish(result) {
		if (this.settled) return;
		this.settled = true;
		this.diagnosticAbort.abort(new DOMException("Recovery window closed.", "AbortError"));
		const window = this.window;
		this.window = void 0;
		if (window !== void 0 && !window.isDestroyed()) window.destroy();
		this.resolveResult?.(result);
		this.resolveResult = void 0;
	}
	requireController() {
		if (this.options.controller === void 0) throw new Error("Desktop plugin recovery actions are unavailable for this startup stage.");
		return this.options.controller;
	}
	async openConfigurationPath(kind) {
		const path = this.options.configurationPaths?.[kind];
		if (path === void 0) throw new Error("Desktop profile configuration is unavailable for this startup stage.");
		if (kind === "settingsDocument") {
			await mkdir(dirname(path), {
				recursive: true,
				mode: 448
			});
			try {
				await writeFile(path, "", {
					flag: "wx",
					mode: 384
				});
			} catch (cause) {
				if (cause.code !== "EEXIST") throw cause;
			}
		}
		if (kind === "settingsDocument" && process.platform === "darwin") {
			await new Promise((resolve, reject) => {
				execFile("/usr/bin/open", ["-t", path], { windowsHide: true }, (cause) => {
					if (cause === null) resolve();
					else reject(cause);
				});
			});
			return;
		}
		const error = await shell.openPath(path);
		if (error.length > 0) throw new Error(error);
	}
};
//#endregion
//#region src/startup-failure-routing.ts
/**
* Route one startup exception without inspecting its message. Error strings are
* diagnostics, never authority for deciding whether Desktop may mutate state.
*/
function routeDesktopStartupFailure(context) {
	if (!context.appReady) return "stderr-only";
	return "startup-recovery";
}
//#endregion
//#region src/startup-generation.ts
/** Resource ownership for one immutable Desktop startup generation. */
const BIN_NAME$5 = "dsh-plugin-desktop";
const DEFAULT_QUIESCE_TIMEOUT_MS = 5e3;
/**
* Own the Host and process-local resources created by one Desktop startup.
* Host effects receive the same idempotent release callbacks as final shutdown,
* so every path converges on one resource lifetime.
*/
var DesktopStartupGeneration = class {
	options;
	id = randomUUID();
	quiesceTimeoutMs;
	releases = [];
	host;
	hostDisposeTask;
	releaseTask;
	released = false;
	constructor(options) {
		this.options = options;
		this.quiesceTimeoutMs = options.quiesceTimeoutMs ?? DEFAULT_QUIESCE_TIMEOUT_MS;
		if (!Number.isSafeInteger(this.quiesceTimeoutMs) || this.quiesceTimeoutMs < 1) throw new Error(`${BIN_NAME$5}: startup generation quiesce timeout must be a positive integer`);
	}
	/** Bind the only Cordis Host that may own this generation's effects. */
	bindHost(host) {
		this.assertActive();
		if (this.host !== void 0 && this.host !== host) throw new Error(`${BIN_NAME$5}: startup generation already owns another Host`);
		this.host = host;
	}
	/** Register one process-local resource and return its idempotent Host effect. */
	own(release) {
		this.assertActive();
		let active = true;
		const releaseOnce = () => {
			if (!active) return;
			active = false;
			release();
		};
		this.releases.push(releaseOnce);
		return releaseOnce;
	}
	/** Stop the Host and its effects before a recovery mutation. */
	async quiesceForRecovery() {
		if (this.released) return false;
		if (this.host === void 0) return true;
		this.hostDisposeTask ??= this.disposeHostForRecovery();
		let timeout;
		const timedOut = new Promise((resolve) => {
			timeout = setTimeout(() => {
				this.options.logger.error(`${BIN_NAME$5}: plugin Host did not stop in time; mutating recovery actions are unavailable`);
				resolve(false);
			}, this.quiesceTimeoutMs);
		});
		const result = await Promise.race([this.hostDisposeTask, timedOut]);
		if (timeout !== void 0) clearTimeout(timeout);
		return result;
	}
	/** Release the Host and every owned resource exactly once. */
	release() {
		this.releaseTask ??= this.releaseOwned();
		return this.releaseTask;
	}
	async releaseOwned() {
		this.released = true;
		let failure;
		try {
			if (this.hostDisposeTask === void 0 || !await this.hostDisposeTask) await this.disposeBoundHost();
		} catch (cause) {
			failure = cause;
		}
		for (const release of this.releases.reverse()) try {
			release();
		} catch (cause) {
			failure ??= cause;
		}
		if (failure !== void 0) throw failure;
	}
	async disposeHostForRecovery() {
		try {
			await this.disposeBoundHost();
			return true;
		} catch (cause) {
			this.options.logger.error(`${BIN_NAME$5}: failed to stop the plugin Host before recovery: ${cause instanceof Error ? cause.message : String(cause)}`);
			return false;
		}
	}
	async disposeBoundHost() {
		const host = this.host;
		if (host === void 0) return;
		await host.fiber.dispose();
		if (this.host === host) this.host = void 0;
	}
	assertActive() {
		if (this.released) throw new Error(`${BIN_NAME$5}: startup generation is already released`);
	}
};
//#endregion
//#region src/profile-checkpoint.ts
/**
* Healthy-start configuration checkpoints for Desktop recovery.
*
* Exactly three rotating slots are retained. Restoring a slot never launches
* pnpm and never copies node_modules; it only restores the fixed declarative
* Profile and Harness-home files listed below. The first healthy startup after
* a restore intentionally consumes a skip marker instead of replacing a
* checkpoint.
*/
const BIN_NAME$4 = "dsh-plugin-desktop";
const MANIFEST_VERSION = 3;
const LEGACY_MANIFEST_VERSION = 2;
const SKIP_MARKER_VERSION = 1;
const SNAPSHOT_ROOT = "health-snapshots";
const MANIFEST_FILENAME = "manifest.json";
const SKIP_MARKER_FILENAME = "skip-next-healthy.json";
const FILE_MODE = 384;
const DIRECTORY_MODE = 448;
const CHECK_POSIX_MODE$1 = process.platform !== "win32";
const HASH_PATTERN$1 = /^[0-9a-f]{64}$/u;
const ID_PATTERN = /^[A-Za-z0-9._:@/-]{1,256}$/u;
const DESKTOP_PROFILE_CHECKPOINT_SLOT_IDS = [
	"slot-1",
	"slot-2",
	"slot-3"
];
const LEGACY_PROFILE_CHECKPOINT_FILES = [
	"package.json",
	"pnpm-lock.yaml",
	"pnpm-workspace.yaml",
	"cordis.patch.yml",
	".dsh-market/state.json"
];
/** Files covered by unified startup recovery. Optional files retain absence. */
const DESKTOP_PROFILE_CHECKPOINT_FILES = [
	...LEGACY_PROFILE_CHECKPOINT_FILES,
	"home/settings.yaml",
	"home/cordis.patch.yml"
];
const FILE_LIMITS = {
	"package.json": 1 * 1024 * 1024,
	"pnpm-lock.yaml": 32 * 1024 * 1024,
	"pnpm-workspace.yaml": 1 * 1024 * 1024,
	"cordis.patch.yml": 1 * 1024 * 1024,
	".dsh-market/state.json": 1 * 1024 * 1024,
	"home/settings.yaml": 4 * 1024 * 1024,
	"home/cordis.patch.yml": 1 * 1024 * 1024
};
function fail(message) {
	throw new Error(`${BIN_NAME$4}: ${message}`);
}
function assertAbsolute(label, value) {
	if (typeof value !== "string" || value.length === 0 || !isAbsolute(value) || value.includes("\0")) fail(`${label} must be an absolute path without NUL`);
	return resolve(value);
}
function assertIdentifier(label, value) {
	if (typeof value !== "string" || !ID_PATTERN.test(value) || value.includes("\\")) fail(`invalid ${label}`);
	return value;
}
function assertProfileName(value) {
	if (typeof value !== "string" || value.length === 0 || value.length > 255 || value.includes("/") || value.includes("\\") || /[\0\r\n]/u.test(value)) fail("invalid profile name");
	return value;
}
function assertAppVersion(value) {
	if (typeof value !== "string" || value.length === 0 || value.length > 128 || /[\0\r\n]/u.test(value)) fail("invalid Desktop version");
	return value;
}
function assertSlotId(value) {
	if (!DESKTOP_PROFILE_CHECKPOINT_SLOT_IDS.includes(value)) fail("invalid checkpoint slot");
	return value;
}
function hash(bytes) {
	return createHash("sha256").update(bytes).digest("hex");
}
function isENOENT(cause) {
	return cause?.code === "ENOENT";
}
function realDirectory(label, path) {
	const absolute = assertAbsolute(label, path);
	let item;
	try {
		item = lstatSync(absolute);
	} catch (cause) {
		fail(`${label} is unavailable: ${cause instanceof Error ? cause.message : String(cause)}`);
	}
	if (!item.isDirectory() || item.isSymbolicLink()) fail(`${label} must be a real directory`);
	realpathSync(absolute);
	return absolute;
}
function ensureDirectory(path) {
	mkdirSync(path, {
		recursive: true,
		mode: DIRECTORY_MODE
	});
	const item = lstatSync(path);
	if (!item.isDirectory() || item.isSymbolicLink()) fail(`checkpoint directory is not a real directory: ${path}`);
	if (CHECK_POSIX_MODE$1 && (item.mode & 511) !== DIRECTORY_MODE) chmodSync(path, DIRECTORY_MODE);
}
function writeDurable(path, bytes, mode = FILE_MODE) {
	ensureDirectory(dirname(path));
	const temporary = `${path}.${process.pid}.${randomUUID()}.tmp`;
	let fd;
	try {
		fd = openSync(temporary, "wx", mode);
		writeSync(fd, bytes);
		fsyncSync(fd);
		closeSync(fd);
		fd = void 0;
		renameSync(temporary, path);
		try {
			const directoryFd = openSync(dirname(path), "r");
			try {
				fsyncSync(directoryFd);
			} finally {
				closeSync(directoryFd);
			}
		} catch {}
	} finally {
		if (fd !== void 0) closeSync(fd);
		try {
			unlinkSync(temporary);
		} catch {}
	}
}
function readJson(path) {
	const item = lstatSync(path);
	if (!item.isFile() || item.isSymbolicLink() || CHECK_POSIX_MODE$1 && (item.mode & 511) !== FILE_MODE) fail(`checkpoint file has unsafe type or mode: ${path}`);
	return JSON.parse(readFileSync(path, "utf8"));
}
function checkpointPluginCount(directory) {
	try {
		const value = readJson(filePath(directory, "package.json"));
		if (value === null || typeof value !== "object" || Array.isArray(value)) return void 0;
		const dsh = value.dsh;
		if (dsh === null || typeof dsh !== "object" || Array.isArray(dsh)) return void 0;
		const profile = dsh.profile;
		if (profile === null || typeof profile !== "object" || Array.isArray(profile)) return void 0;
		const bundles = profile.bundles;
		if (!Array.isArray(bundles) || bundles.some((bundle) => typeof bundle !== "string")) return void 0;
		return bundles.length;
	} catch {
		return;
	}
}
function fileEqual(left, right) {
	return left.present === right.present && (!left.present || left.sha256 === right.sha256 && left.size === right.size && left.mode === right.mode);
}
function filePath(root, name) {
	const path = join(root, ...name.split("/"));
	if (path !== resolve(root, ...name.split("/")) || relative(root, path).startsWith("..")) fail("checkpoint filename escaped its root");
	return path;
}
function checkpointFiles(version) {
	if (version === LEGACY_MANIFEST_VERSION) return LEGACY_PROFILE_CHECKPOINT_FILES;
	if (version === MANIFEST_VERSION) return DESKTOP_PROFILE_CHECKPOINT_FILES;
	fail("checkpoint manifest is invalid");
}
function targetPath(profileDir, homeDir, name) {
	if (name === "home/settings.yaml") return join(homeDir, "settings.yaml");
	if (name === "home/cordis.patch.yml") return join(homeDir, "cordis.patch.yml");
	return filePath(profileDir, name);
}
function assertTargetParent(profileDir, homeDir, name) {
	const parent = dirname(targetPath(profileDir, homeDir, name));
	try {
		const item = lstatSync(parent);
		if (item.isSymbolicLink() || !item.isDirectory()) fail(`checkpoint target parent must be a real directory: ${name}`);
		realpathSync(parent);
	} catch (cause) {
		if (!isENOENT(cause)) throw cause;
	}
}
/** Three-slot Profile checkpoint manager. */
var DesktopProfileCheckpoint = class {
	userDataDir;
	profileDir;
	homeDir;
	profileIdentity;
	profileName;
	provider;
	appVersion;
	profileRoot;
	limits;
	now;
	constructor(options) {
		const userData = options.userDataDir ?? options.userData;
		const profile = options.profileDir ?? options.profilePath;
		if (userData === void 0 || profile === void 0) fail("userDataDir and profileDir are required");
		this.userDataDir = realDirectory("userDataDir", userData);
		this.profileDir = realDirectory("profileDir", profile);
		this.homeDir = realDirectory("homeDir", options.homeDir ?? resolve(this.profileDir, "..", ".."));
		this.profileIdentity = assertIdentifier("profile identity", options.profileIdentity ?? hash(this.profileDir));
		this.profileName = assertProfileName(options.profileName ?? "desktop");
		this.provider = assertIdentifier("provider", options.provider ?? "unknown");
		this.appVersion = assertAppVersion(options.appVersion ?? "unknown");
		this.now = options.now ?? Date.now;
		this.limits = {
			...FILE_LIMITS,
			...options.maxFileBytes ?? {}
		};
		for (const name of DESKTOP_PROFILE_CHECKPOINT_FILES) if (!Number.isSafeInteger(this.limits[name]) || this.limits[name] < 0) fail(`invalid size limit for ${name}`);
		const root = join(this.userDataDir, SNAPSHOT_ROOT);
		ensureDirectory(root);
		this.profileRoot = join(root, hash(this.profileIdentity));
		ensureDirectory(this.profileRoot);
	}
	/** Return all three stable slots, including empty slots. */
	listSlots() {
		this.recoverOrphanedSlots();
		return DESKTOP_PROFILE_CHECKPOINT_SLOT_IDS.map((slotId) => {
			const directory = this.slotDirectory(slotId);
			const snapshot = this.readSnapshot(directory, false);
			return snapshot === void 0 ? {
				slotId,
				snapshotExists: false,
				snapshotDirectory: directory
			} : (() => {
				const pluginCount = checkpointPluginCount(snapshot.directory);
				return {
					slotId,
					snapshotExists: true,
					snapshotDirectory: directory,
					manifest: snapshot.manifest,
					...pluginCount === void 0 ? {} : { pluginCount },
					totalBytes: snapshot.manifest.files.reduce((total, file) => total + (file.present ? file.size ?? 0 : 0), 0)
				};
			})();
		});
	}
	/** Capture every healthy startup, rotating the oldest of the three slots. */
	captureHealthy() {
		this.recoverOrphanedSlots();
		const current = this.readCurrentImages(DESKTOP_PROFILE_CHECKPOINT_FILES, true);
		const skip = this.readSkipMarker();
		if (skip !== void 0) {
			unlinkSync(join(this.profileRoot, SKIP_MARKER_FILENAME));
			return {
				status: "skipped-after-restore",
				restoredSlotId: skip.restoredSlotId
			};
		}
		const slots = this.listSlots();
		const target = slots.find((slot) => !slot.snapshotExists) ?? [...slots].sort((left, right) => {
			return Date.parse(left.manifest.capturedAt) - Date.parse(right.manifest.capturedAt) || left.slotId.localeCompare(right.slotId);
		})[0];
		const snapshotId = randomUUID();
		const targetDirectory = target.snapshotDirectory;
		const staging = join(this.profileRoot, `.staging-${target.slotId}-${process.pid}-${snapshotId}`);
		ensureDirectory(staging);
		try {
			const records = [];
			for (let index = 0; index < DESKTOP_PROFILE_CHECKPOINT_FILES.length; index += 1) {
				const name = DESKTOP_PROFILE_CHECKPOINT_FILES[index];
				const image = current[index];
				records.push({
					name,
					...image
				});
				if (image.present) {
					const destination = filePath(staging, name);
					ensureDirectory(dirname(destination));
					writeDurable(destination, readFileSync(targetPath(this.profileDir, this.homeDir, name)));
				}
			}
			const manifest = {
				version: MANIFEST_VERSION,
				snapshotId,
				capturedAt: new Date(this.now()).toISOString(),
				profileIdentity: this.profileIdentity,
				profileName: this.profileName,
				provider: this.provider,
				slotId: target.slotId,
				reason: "healthy-startup",
				appVersion: this.appVersion,
				files: records
			};
			writeDurable(join(staging, MANIFEST_FILENAME), Buffer.from(`${JSON.stringify(manifest)}\n`, "utf8"));
			this.replaceSlot(targetDirectory, staging);
			return {
				status: "captured",
				slotId: target.slotId,
				snapshotDirectory: targetDirectory,
				manifest
			};
		} catch (cause) {
			rmSync(staging, {
				recursive: true,
				force: true
			});
			throw cause;
		}
	}
	inspectSlot(slotId) {
		const resolvedSlot = assertSlotId(slotId);
		this.recoverOrphanedSlot(resolvedSlot);
		const snapshot = this.readSnapshot(this.slotDirectory(resolvedSlot), false);
		if (snapshot === void 0) return {
			slotId: resolvedSlot,
			snapshotExists: false,
			currentDiffers: false,
			changedFiles: []
		};
		const names = checkpointFiles(snapshot.manifest.version);
		const current = this.readCurrentImages(names, false);
		const changedFiles = names.filter((_, index) => !fileEqual(snapshot.manifest.files[index], current[index]));
		return {
			slotId: resolvedSlot,
			snapshotExists: true,
			currentDiffers: changedFiles.length > 0,
			changedFiles,
			manifest: snapshot.manifest
		};
	}
	/** Restore one user-selected slot and preserve it across the next healthy boot. */
	restoreSlot(slotId) {
		const resolvedSlot = assertSlotId(slotId);
		this.recoverOrphanedSlot(resolvedSlot);
		const snapshot = this.readSnapshot(this.slotDirectory(resolvedSlot), true);
		if (snapshot === void 0) fail(`checkpoint ${resolvedSlot} is empty`);
		const names = checkpointFiles(snapshot.manifest.version);
		const current = this.readCurrentImages(names, false);
		const changedFiles = names.filter((_, index) => !fileEqual(snapshot.manifest.files[index], current[index]));
		const dependencyMaterializationRequired = this.readSkipMarker()?.dependencyMaterializationPending === true || changedFiles.some((name) => name === "package.json" || name === "pnpm-lock.yaml" || name === "pnpm-workspace.yaml");
		writeDurable(join(this.profileRoot, SKIP_MARKER_FILENAME), Buffer.from(`${JSON.stringify({
			version: SKIP_MARKER_VERSION,
			restoredSlotId: resolvedSlot,
			restoredAt: new Date(this.now()).toISOString(),
			dependencyMaterializationPending: dependencyMaterializationRequired
		})}\n`, "utf8"));
		for (const name of names) assertTargetParent(this.profileDir, this.homeDir, name);
		for (let index = 0; index < names.length; index += 1) {
			const name = names[index];
			const record = snapshot.manifest.files[index];
			const target = targetPath(this.profileDir, this.homeDir, name);
			if (record.present) {
				const bytes = readFileSync(filePath(snapshot.directory, name));
				if (hash(bytes) !== record.sha256 || bytes.byteLength !== record.size) fail(`checkpoint changed during restore: ${name}`);
				writeDurable(target, bytes, record.mode);
			} else try {
				const item = lstatSync(target);
				if (item.isSymbolicLink() || !item.isFile()) fail(`cannot remove unsafe profile entry: ${name}`);
				unlinkSync(target);
			} catch (cause) {
				if (!isENOENT(cause)) throw cause;
			}
		}
		return {
			status: "restored",
			slotId: resolvedSlot,
			changedFiles,
			dependencyMaterializationRequired,
			snapshotDirectory: snapshot.directory
		};
	}
	/** Keep the checkpoint-preservation marker but clear its derived dependency work. */
	completeDependencyMaterialization(slotId) {
		const resolvedSlot = assertSlotId(slotId);
		const marker = this.readSkipMarker();
		if (marker === void 0 || marker.restoredSlotId !== resolvedSlot) fail("checkpoint materialization completion does not match the active restore");
		if (!marker.dependencyMaterializationPending) return;
		writeDurable(join(this.profileRoot, SKIP_MARKER_FILENAME), Buffer.from(`${JSON.stringify({
			...marker,
			dependencyMaterializationPending: false
		})}\n`, "utf8"));
	}
	slotDirectory(slotId) {
		return join(this.profileRoot, slotId);
	}
	readCurrentImages(names, requirePackage) {
		return names.map((name) => {
			assertTargetParent(this.profileDir, this.homeDir, name);
			const path = targetPath(this.profileDir, this.homeDir, name);
			let item;
			try {
				item = lstatSync(path);
			} catch (cause) {
				if (isENOENT(cause)) {
					if (requirePackage && name === "package.json") fail("healthy profile package.json is unavailable");
					return { present: false };
				}
				throw cause;
			}
			if (item.isSymbolicLink() || !item.isFile()) fail(`checkpoint entry must be a regular file: ${name}`);
			if (item.size > this.limits[name]) fail(`profile checkpoint file is too large: ${name}`);
			const bytes = readFileSync(path);
			return {
				present: true,
				sha256: hash(bytes),
				size: bytes.byteLength,
				mode: item.mode & 511
			};
		});
	}
	replaceSlot(target, staging) {
		if (!existsSync(target)) {
			renameSync(staging, target);
			return;
		}
		const old = `${target}.old-${randomUUID()}`;
		renameSync(target, old);
		try {
			renameSync(staging, target);
		} catch (cause) {
			renameSync(old, target);
			throw cause;
		}
		rmSync(old, {
			recursive: true,
			force: true
		});
	}
	recoverOrphanedSlots() {
		for (const slotId of DESKTOP_PROFILE_CHECKPOINT_SLOT_IDS) this.recoverOrphanedSlot(slotId);
	}
	recoverOrphanedSlot(slotId) {
		const target = this.slotDirectory(slotId);
		if (existsSync(target)) return;
		let candidates;
		try {
			candidates = readdirSync(this.profileRoot).filter((name) => name.startsWith(`${slotId}.old-`)).sort().reverse();
		} catch (cause) {
			if (isENOENT(cause)) return;
			throw cause;
		}
		for (const name of candidates) {
			const candidate = join(this.profileRoot, name);
			try {
				const item = lstatSync(candidate);
				if (!item.isDirectory() || item.isSymbolicLink() || CHECK_POSIX_MODE$1 && (item.mode & 511) !== DIRECTORY_MODE) continue;
				renameSync(candidate, target);
				return;
			} catch (cause) {
				if (!isENOENT(cause)) throw cause;
			}
		}
	}
	readSkipMarker() {
		const path = join(this.profileRoot, SKIP_MARKER_FILENAME);
		try {
			const value = readJson(path);
			if (value === null || typeof value !== "object" || Array.isArray(value)) fail("skip healthy marker is invalid");
			const marker = value;
			if (marker.version !== SKIP_MARKER_VERSION || typeof marker.restoredSlotId !== "string" || typeof marker.restoredAt !== "string" || !Number.isFinite(Date.parse(marker.restoredAt)) || marker.dependencyMaterializationPending !== void 0 && typeof marker.dependencyMaterializationPending !== "boolean") fail("skip healthy marker is invalid");
			return {
				version: SKIP_MARKER_VERSION,
				restoredSlotId: assertSlotId(marker.restoredSlotId),
				restoredAt: marker.restoredAt,
				dependencyMaterializationPending: marker.dependencyMaterializationPending === true
			};
		} catch (cause) {
			if (isENOENT(cause)) return void 0;
			throw cause;
		}
	}
	readSnapshot(directory, requireComplete) {
		try {
			const expectedSlotId = assertSlotId(basename(directory));
			const directoryItem = lstatSync(directory);
			if (!directoryItem.isDirectory() || directoryItem.isSymbolicLink() || CHECK_POSIX_MODE$1 && (directoryItem.mode & 511) !== DIRECTORY_MODE) fail("checkpoint directory has unsafe type or mode");
			const value = readJson(join(directory, MANIFEST_FILENAME));
			if (value === null || typeof value !== "object" || Array.isArray(value)) fail("checkpoint manifest is invalid");
			const object = value;
			const files = object.files;
			const expectedFiles = checkpointFiles(object.version);
			if (typeof object.snapshotId !== "string" || !ID_PATTERN.test(object.snapshotId) || typeof object.capturedAt !== "string" || !Number.isFinite(Date.parse(object.capturedAt)) || object.profileIdentity !== this.profileIdentity || object.profileName !== this.profileName || typeof object.provider !== "string" || assertIdentifier("checkpoint provider", object.provider) !== object.provider || !Array.isArray(files) || files.length !== expectedFiles.length) fail("checkpoint manifest is invalid");
			if (object.slotId !== expectedSlotId || object.reason !== "healthy-startup" || typeof object.appVersion !== "string" || assertAppVersion(object.appVersion) !== object.appVersion) fail("checkpoint metadata is invalid");
			for (let index = 0; index < expectedFiles.length; index += 1) {
				const record = files[index];
				const expected = expectedFiles[index];
				if (record === null || typeof record !== "object" || Array.isArray(record)) fail("checkpoint manifest is invalid");
				const item = record;
				if (item.name !== expected || typeof item.present !== "boolean") fail("checkpoint manifest is invalid");
				if (item.present && (typeof item.sha256 !== "string" || !HASH_PATTERN$1.test(item.sha256) || !Number.isSafeInteger(item.size) || item.size < 0 || item.size > this.limits[expected] || !Number.isSafeInteger(item.mode) || item.mode < 0 || item.mode > 511)) fail("checkpoint manifest is invalid");
				const backup = filePath(directory, expected);
				if (item.present) {
					const backupItem = lstatSync(backup);
					if (!backupItem.isFile() || backupItem.isSymbolicLink() || CHECK_POSIX_MODE$1 && (backupItem.mode & 511) !== FILE_MODE) fail(`checkpoint backup is unsafe: ${expected}`);
					const bytes = readFileSync(backup);
					if (bytes.byteLength !== item.size || hash(bytes) !== item.sha256) fail(`checkpoint backup is incomplete: ${expected}`);
				} else if (existsSync(backup)) fail(`checkpoint contains an unexpected backup: ${expected}`);
			}
			if (requireComplete && !files.some((record) => record.present === true)) fail("checkpoint contains no restorable files");
			return {
				directory,
				manifest: value
			};
		} catch (cause) {
			if (isENOENT(cause)) try {
				lstatSync(directory);
			} catch (directoryCause) {
				if (isENOENT(directoryCause)) return void 0;
			}
			throw cause;
		}
	}
};
/** Remove all three slots and the skip marker for one deleted Profile. */
function clearDesktopProfileCheckpoint(userDataDir, profileDir) {
	const userData = realDirectory("userDataDir", userDataDir);
	const profile = assertAbsolute("profileDir", profileDir);
	const profileRoot = join(userData, SNAPSHOT_ROOT, hash(hash(profile)));
	let item;
	try {
		item = lstatSync(profileRoot);
	} catch (cause) {
		if (isENOENT(cause)) return;
		throw cause;
	}
	if (item.isSymbolicLink() || !item.isDirectory()) fail("profile checkpoint directory has unsafe type");
	rmSync(profileRoot, {
		recursive: true,
		force: false
	});
}
//#endregion
//#region src/setup-wizard-state.ts
/** Per-Profile completion state for the launcher-owned Desktop Setup Wizard. */
const BIN_NAME$3 = "dsh-plugin-desktop";
const STATE_VERSION = 1;
const STATE_ROOT_DIRECTORY = "profile-setup";
const STATE_FILENAME = "state.json";
const STATE_DIRECTORY_MODE = 448;
const STATE_FILE_MODE = 384;
const MAX_STATE_BYTES = 4 * 1024;
const HASH_PATTERN = /^[0-9a-f]{64}$/u;
const CHECK_POSIX_MODE = process.platform !== "win32";
function invalid$1(message) {
	return /* @__PURE__ */ new Error(`${BIN_NAME$3}: invalid Desktop Setup Wizard state: ${message}`);
}
function assertAbsolutePath$2(label, value) {
	if (typeof value !== "string" || value.length === 0 || value.includes("\0") || !isAbsolute(value)) throw new TypeError(`${BIN_NAME$3}: ${label} must be an absolute path without NUL`);
	return resolve(value);
}
/** Stable Profile identity used only as a private user-data path component. */
function desktopSetupWizardProfileHash(profileDir) {
	const normalized = assertAbsolutePath$2("Setup Wizard Profile directory", profileDir);
	return createHash("sha256").update(normalized).digest("hex");
}
/** Fixed marker path for one Profile under one Electron user-data directory. */
function desktopSetupWizardStatePath(userDataDir, profileDir) {
	const userData = assertAbsolutePath$2("Setup Wizard user-data directory", userDataDir);
	const profileHash = desktopSetupWizardProfileHash(profileDir);
	return join(userData, STATE_ROOT_DIRECTORY, profileHash, STATE_FILENAME);
}
function assertPrivateDirectory(path) {
	const info = lstatSync(path);
	if (!info.isDirectory() || info.isSymbolicLink()) throw invalid$1(`state directory must be a real directory: ${path}`);
	if (CHECK_POSIX_MODE && (info.mode & 511) !== STATE_DIRECTORY_MODE) throw invalid$1(`state directory permissions must be ${STATE_DIRECTORY_MODE.toString(8)}`);
}
function ensurePrivateDirectory(path) {
	mkdirSync(path, {
		recursive: true,
		mode: STATE_DIRECTORY_MODE
	});
	const info = lstatSync(path);
	if (!info.isDirectory() || info.isSymbolicLink()) throw invalid$1(`state directory must be a real directory: ${path}`);
	if (CHECK_POSIX_MODE && (info.mode & 511) !== STATE_DIRECTORY_MODE) chmodSync(path, STATE_DIRECTORY_MODE);
}
function existingPathInfo(path) {
	try {
		return lstatSync(path);
	} catch (cause) {
		if (cause.code === "ENOENT") return void 0;
		throw cause;
	}
}
function assertSafeStateTarget(path) {
	const info = existingPathInfo(path);
	if (info === void 0) return;
	if (!info.isFile() || info.isSymbolicLink()) throw invalid$1("marker must be a regular file");
	if (info.size > MAX_STATE_BYTES) throw invalid$1(`marker exceeds ${String(MAX_STATE_BYTES)} bytes`);
	if (CHECK_POSIX_MODE && (info.mode & 511) !== STATE_FILE_MODE) throw invalid$1(`marker permissions must be ${STATE_FILE_MODE.toString(8)}`);
}
function readStateBytes(path) {
	const pathInfo = existingPathInfo(path);
	if (pathInfo === void 0) return void 0;
	if (!pathInfo.isFile() || pathInfo.isSymbolicLink()) throw invalid$1("marker must be a regular file");
	if (pathInfo.size > MAX_STATE_BYTES) throw invalid$1(`marker exceeds ${String(MAX_STATE_BYTES)} bytes`);
	if (CHECK_POSIX_MODE && (pathInfo.mode & 511) !== STATE_FILE_MODE) throw invalid$1(`marker permissions must be ${STATE_FILE_MODE.toString(8)}`);
	const descriptor = openSync(path, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0));
	try {
		const descriptorInfo = fstatSync(descriptor);
		if (!descriptorInfo.isFile() || descriptorInfo.size > MAX_STATE_BYTES) throw invalid$1(`marker must be a regular file within ${String(MAX_STATE_BYTES)} bytes`);
		if (descriptorInfo.dev !== pathInfo.dev || descriptorInfo.ino !== pathInfo.ino) throw invalid$1("marker changed while it was being opened");
		if (CHECK_POSIX_MODE && (descriptorInfo.mode & 511) !== STATE_FILE_MODE) throw invalid$1(`marker permissions must be ${STATE_FILE_MODE.toString(8)}`);
		const buffer = Buffer.alloc(4097);
		let bytesRead = 0;
		while (bytesRead < buffer.byteLength) {
			const count = readSync(descriptor, buffer, bytesRead, buffer.byteLength - bytesRead, null);
			if (count === 0) break;
			bytesRead += count;
		}
		if (bytesRead > MAX_STATE_BYTES) throw invalid$1(`marker exceeds ${String(MAX_STATE_BYTES)} bytes`);
		try {
			return new TextDecoder("utf-8", { fatal: true }).decode(buffer.subarray(0, bytesRead));
		} catch {
			throw invalid$1("marker must contain valid UTF-8");
		}
	} finally {
		closeSync(descriptor);
	}
}
function parseState(text, expectedProfileHash) {
	let value;
	try {
		value = JSON.parse(text);
	} catch {
		throw invalid$1("marker must contain valid JSON");
	}
	if (value === null || typeof value !== "object" || Array.isArray(value)) throw invalid$1("marker root must be an object");
	const object = value;
	const keys = Object.keys(object).sort();
	if (keys.length !== 3 || keys[0] !== "outcome" || keys[1] !== "profileHash" || keys[2] !== "version") throw invalid$1("marker contains unexpected fields");
	if (object.version !== STATE_VERSION) throw invalid$1("marker has an unsupported version");
	if (typeof object.profileHash !== "string" || !HASH_PATTERN.test(object.profileHash) || object.profileHash !== expectedProfileHash) throw invalid$1("marker Profile identity does not match its path");
	if (object.outcome !== "completed" && object.outcome !== "skipped") throw invalid$1("marker outcome must be completed or skipped");
	return Object.freeze({
		version: STATE_VERSION,
		profileHash: object.profileHash,
		outcome: object.outcome
	});
}
/** Read one Profile marker; absence means the Wizard still needs a decision. */
function readDesktopSetupWizardState(userDataDir, profileDir) {
	const path = desktopSetupWizardStatePath(userDataDir, profileDir);
	const root = dirname(dirname(path));
	const profileRoot = dirname(path);
	if (existingPathInfo(root) === void 0) return void 0;
	assertPrivateDirectory(root);
	if (existingPathInfo(profileRoot) === void 0) return void 0;
	assertPrivateDirectory(profileRoot);
	const text = readStateBytes(path);
	if (text === void 0) return void 0;
	return parseState(text, desktopSetupWizardProfileHash(profileDir));
}
/** Atomically record explicit completion or an explicit skip for one Profile. */
async function completeOrSkipDesktopSetupWizard(userDataDir, profileDir, outcome) {
	if (outcome !== "completed" && outcome !== "skipped") throw new TypeError(`${BIN_NAME$3}: invalid Desktop Setup Wizard outcome`);
	const path = desktopSetupWizardStatePath(userDataDir, profileDir);
	const profileHash = desktopSetupWizardProfileHash(profileDir);
	ensurePrivateDirectory(dirname(dirname(path)));
	ensurePrivateDirectory(dirname(path));
	const state = Object.freeze({
		version: STATE_VERSION,
		profileHash,
		outcome
	});
	assertSafeStateTarget(path);
	const current = readStateBytes(path);
	if (current !== void 0) parseState(current, profileHash);
	await writeFileAtomic(path, `${JSON.stringify(state, void 0, 2)}\n`, {
		mode: STATE_FILE_MODE,
		dirMode: STATE_DIRECTORY_MODE
	});
	if (CHECK_POSIX_MODE) chmodSync(path, STATE_FILE_MODE);
	return state;
}
/** Clear one Profile marker without touching any other Profile's decision. */
async function clearDesktopSetupWizardState(userDataDir, profileDir) {
	const path = desktopSetupWizardStatePath(userDataDir, profileDir);
	if (existingPathInfo(dirname(dirname(path))) === void 0) return;
	assertPrivateDirectory(dirname(dirname(path)));
	if (existingPathInfo(dirname(path)) === void 0) return;
	assertPrivateDirectory(dirname(path));
	if (existingPathInfo(path) === void 0) return;
	assertSafeStateTarget(path);
	unlinkSync(path);
}
Object.freeze({
	version: STATE_VERSION,
	rootDirectory: STATE_ROOT_DIRECTORY,
	filename: STATE_FILENAME,
	maxBytes: MAX_STATE_BYTES,
	directoryMode: STATE_DIRECTORY_MODE,
	fileMode: STATE_FILE_MODE
});
//#endregion
//#region src/setup-wizard-settings.ts
/** Pre-Host reader and atomic writer for Desktop Setup Wizard preferences. */
const BIN_NAME$2 = "dsh-plugin-desktop";
const DESKTOP_NAMESPACE = "dsh-desktop";
const NOTIFICATIONS_NAMESPACE = "dsh-desktop-notifications";
const MAX_DOCUMENT_BYTES = 4 * 1024 * 1024;
const DOCUMENT_FILE_MODE = 384;
const DOCUMENT_DIRECTORY_MODE = 448;
function invalid(message) {
	return /* @__PURE__ */ new Error(`${BIN_NAME$2}: invalid Setup Wizard settings document: ${message}`);
}
function settingsPath(value) {
	if (typeof value !== "string" || value.length === 0 || value.includes("\0") || !isAbsolute(value)) throw new TypeError(`${BIN_NAME$2}: Setup Wizard settings document must be an absolute path without NUL`);
	const path = resolve(value);
	const extension = extname(path).toLowerCase();
	if (extension !== ".yaml" && extension !== ".yml" && extension !== ".json") throw new TypeError(`${BIN_NAME$2}: Setup Wizard settings document must use .yaml, .yml, or .json`);
	return path;
}
function formatOf(path) {
	return extname(path).toLowerCase() === ".json" ? "json" : "yaml";
}
function isRecord(value) {
	return value !== null && typeof value === "object" && !Array.isArray(value);
}
function readDocumentText(path) {
	let pathInfo;
	try {
		pathInfo = lstatSync(path);
	} catch (cause) {
		if (cause.code === "ENOENT") return void 0;
		throw cause;
	}
	if (!pathInfo.isFile() || pathInfo.isSymbolicLink()) throw invalid("document must be a regular file");
	if (pathInfo.size > MAX_DOCUMENT_BYTES) throw invalid(`document exceeds ${String(MAX_DOCUMENT_BYTES)} bytes`);
	const descriptor = openSync(path, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0));
	try {
		const info = fstatSync(descriptor);
		if (!info.isFile() || info.size > MAX_DOCUMENT_BYTES) throw invalid(`document must be a regular file within ${String(MAX_DOCUMENT_BYTES)} bytes`);
		if (info.dev !== pathInfo.dev || info.ino !== pathInfo.ino) throw invalid("document changed while it was being opened");
		const buffer = Buffer.alloc(4194305);
		let bytesRead = 0;
		while (bytesRead < buffer.byteLength) {
			const count = readSync(descriptor, buffer, bytesRead, buffer.byteLength - bytesRead, null);
			if (count === 0) break;
			bytesRead += count;
		}
		if (bytesRead > MAX_DOCUMENT_BYTES) throw invalid(`document exceeds ${String(MAX_DOCUMENT_BYTES)} bytes`);
		try {
			return new TextDecoder("utf-8", { fatal: true }).decode(buffer.subarray(0, bytesRead));
		} catch {
			throw invalid("document must contain valid UTF-8");
		}
	} finally {
		closeSync(descriptor);
	}
}
function loadSettingsDocument(path) {
	const format = formatOf(path);
	const text = readDocumentText(path);
	if (format === "json") {
		let value = {};
		if (text !== void 0) try {
			value = JSON.parse(text);
		} catch {
			throw invalid("JSON could not be parsed");
		}
		if (!isRecord(value)) throw invalid("root must be a map of namespace sections");
		return {
			format,
			root: value
		};
	}
	const yaml = parseDocument(text ?? "", { prettyErrors: true });
	if (yaml.errors.length > 0) throw invalid(`YAML could not be parsed: ${yaml.errors.map((error) => error.message).join("; ")}`);
	const value = yaml.toJS() ?? {};
	if (!isRecord(value)) throw invalid("root must be a map of namespace sections");
	return {
		format,
		root: value,
		yaml
	};
}
function section(root, namespace) {
	const value = root[namespace];
	if (value === void 0) return {};
	if (!isRecord(value)) throw invalid(`${namespace} must be a map`);
	return value;
}
function optionalBoolean(values, key, fallback) {
	const value = values[key];
	if (value === void 0) return fallback;
	if (typeof value !== "boolean") throw invalid(`${key} must be a boolean`);
	return value;
}
function parseMode(value) {
	if (value === void 0) return "compatibility";
	if (value === "compatibility" || value === "extended" || value === "advanced") return value;
	throw invalid("dsh-desktop.mode must be compatibility, extended, or advanced");
}
function parseExposure(value) {
	if (value === void 0) return "loopback";
	if (value === "loopback" || value === "lan") return value;
	throw invalid("dsh-desktop.networkExposure must be loopback or lan");
}
function notificationSettings(values) {
	return Object.freeze({
		enabled: optionalBoolean(values, "enabled", true),
		notifyOnTurnCompletion: optionalBoolean(values, "notifyOnTurnCompletion", true),
		notifyOnTurnFailure: optionalBoolean(values, "notifyOnTurnFailure", true),
		notifyOnJobCompletion: optionalBoolean(values, "notifyOnJobCompletion", true),
		notifyOnJobFailure: optionalBoolean(values, "notifyOnJobFailure", true)
	});
}
function projectSettings(root) {
	const desktop = section(root, DESKTOP_NAMESPACE);
	const notifications = section(root, NOTIFICATIONS_NAMESPACE);
	const mode = parseMode(desktop.mode);
	const networkExposure = parseExposure(desktop.networkExposure);
	const openBrowser = desktopBrowserAccessEnabled(mode, optionalBoolean(desktop, "openBrowser", false), networkExposure);
	return Object.freeze({
		mode,
		macosMaterial: parseMacosWindowMaterial(desktop.macosMaterial),
		windowsMaterial: parseWindowsWindowMaterial(desktop.windowsMaterial),
		openBrowser,
		networkExposure: desktopNetworkExposureForBrowserAccess(openBrowser, networkExposure),
		notifications: notificationSettings(notifications)
	});
}
function normalizedUpdate(value) {
	if (!isRecord(value)) throw new TypeError(`${BIN_NAME$2}: invalid Setup Wizard settings update`);
	const requestedMode = parseMode(value.mode);
	if (value.macosMaterial !== "off" && value.macosMaterial !== "transparent") throw new TypeError(`${BIN_NAME$2}: macOS Setup Wizard material must be off or transparent`);
	if (value.windowsMaterial !== "off" && value.windowsMaterial !== "acrylic" && value.windowsMaterial !== "mica") throw new TypeError(`${BIN_NAME$2}: Windows Setup Wizard material must be off, acrylic, or mica`);
	if (typeof value.openBrowser !== "boolean") throw new TypeError(`${BIN_NAME$2}: Setup Wizard openBrowser must be a boolean`);
	const openBrowser = desktopBrowserAccessAvailable(requestedMode) && value.openBrowser;
	const networkExposure = desktopNetworkExposureForBrowserAccess(openBrowser, parseExposure(value.networkExposure));
	if (!isRecord(value.notifications)) throw new TypeError(`${BIN_NAME$2}: Setup Wizard notifications must be a map`);
	const notificationKeys = [
		"enabled",
		"notifyOnTurnCompletion",
		"notifyOnTurnFailure",
		"notifyOnJobCompletion",
		"notifyOnJobFailure"
	];
	if (Object.keys(value.notifications).length !== notificationKeys.length || notificationKeys.some((key) => typeof value.notifications[key] !== "boolean")) throw new TypeError(`${BIN_NAME$2}: Setup Wizard update must contain all five notification booleans`);
	return Object.freeze({
		mode: requestedMode,
		macosMaterial: value.macosMaterial,
		windowsMaterial: value.windowsMaterial,
		openBrowser,
		networkExposure,
		notifications: Object.freeze({
			enabled: value.notifications.enabled,
			notifyOnTurnCompletion: value.notifications.notifyOnTurnCompletion,
			notifyOnTurnFailure: value.notifications.notifyOnTurnFailure,
			notifyOnJobCompletion: value.notifications.notifyOnJobCompletion,
			notifyOnJobFailure: value.notifications.notifyOnJobFailure
		})
	});
}
function sameSettings(current, next) {
	return current.mode === next.mode && current.macosMaterial === next.macosMaterial && current.windowsMaterial === next.windowsMaterial && current.openBrowser === next.openBrowser && current.networkExposure === next.networkExposure && current.notifications.enabled === next.notifications.enabled && current.notifications.notifyOnTurnCompletion === next.notifications.notifyOnTurnCompletion && current.notifications.notifyOnTurnFailure === next.notifications.notifyOnTurnFailure && current.notifications.notifyOnJobCompletion === next.notifications.notifyOnJobCompletion && current.notifications.notifyOnJobFailure === next.notifications.notifyOnJobFailure;
}
function applyYamlUpdate(document, next) {
	document.setIn([DESKTOP_NAMESPACE, "mode"], next.mode);
	document.setIn([DESKTOP_NAMESPACE, "macosMaterial"], next.macosMaterial);
	document.setIn([DESKTOP_NAMESPACE, "windowsMaterial"], next.windowsMaterial);
	document.setIn([DESKTOP_NAMESPACE, "openBrowser"], next.openBrowser);
	document.setIn([DESKTOP_NAMESPACE, "networkExposure"], next.networkExposure);
	for (const [key, value] of Object.entries(next.notifications)) document.setIn([NOTIFICATIONS_NAMESPACE, key], value);
	return document.toString();
}
function applyJsonUpdate(root, next) {
	const output = structuredClone(root);
	const desktop = { ...section(output, DESKTOP_NAMESPACE) };
	desktop.mode = next.mode;
	desktop.macosMaterial = next.macosMaterial;
	desktop.windowsMaterial = next.windowsMaterial;
	desktop.openBrowser = next.openBrowser;
	desktop.networkExposure = next.networkExposure;
	output[DESKTOP_NAMESPACE] = desktop;
	output[NOTIFICATIONS_NAMESPACE] = {
		...section(output, NOTIFICATIONS_NAMESPACE),
		...next.notifications
	};
	return `${JSON.stringify(output, void 0, 2)}\n`;
}
function ensureDocumentDirectory(path) {
	const directory = dirname(path);
	mkdirSync(directory, {
		recursive: true,
		mode: DOCUMENT_DIRECTORY_MODE
	});
	const info = lstatSync(directory);
	if (!info.isDirectory() || info.isSymbolicLink()) throw invalid("document parent must be a real directory");
}
/** Read defaults or validated current values from the exact prepared settings file. */
function readDesktopSetupWizardSettings(documentPath) {
	return projectSettings(loadSettingsDocument(settingsPath(documentPath)).root);
}
/**
* Atomically update only Wizard-owned leaves, preserving every other setting.
* Setup runs before the Host and never creates or waits for a settings writer
* lock; the same-directory rename still keeps readers from seeing torn bytes.
*/
async function updateDesktopSetupWizardSettings(documentPath, value) {
	const path = settingsPath(documentPath);
	const next = normalizedUpdate(value);
	if (sameSettings(projectSettings(loadSettingsDocument(path).root), next)) return next;
	ensureDocumentDirectory(path);
	const loaded = loadSettingsDocument(path);
	projectSettings(loaded.root);
	await writeFileAtomic(path, loaded.format === "yaml" ? applyYamlUpdate(loaded.yaml, next) : applyJsonUpdate(loaded.root, next), {
		mode: DOCUMENT_FILE_MODE,
		dirMode: DOCUMENT_DIRECTORY_MODE
	});
	return next;
}
/**
* Atomically migrate settings written with the former browser-handoff
* semantics before the Host reads them. Existing LAN exposure becomes an
* explicit browser-access grant only for an already-selected compatibility
* mode. Incompatible modes retain their selection and withdraw browser/LAN
* access. Returns whether the durable document changed.
*/
async function migrateDesktopBrowserAccessSettings(documentPath) {
	const path = settingsPath(documentPath);
	const migrationValues = (loaded) => {
		projectSettings(loaded.root);
		const desktop = section(loaded.root, DESKTOP_NAMESPACE);
		const storedMode = parseMode(desktop.mode);
		const storedOpenBrowser = optionalBoolean(desktop, "openBrowser", false);
		const storedExposure = parseExposure(desktop.networkExposure);
		const browserAccess = desktopBrowserAccessEnabled(storedMode, storedOpenBrowser, storedExposure);
		const networkExposure = desktopNetworkExposureForBrowserAccess(browserAccess, storedExposure);
		return {
			browserAccess,
			needed: storedOpenBrowser !== browserAccess || storedExposure !== networkExposure,
			networkExposure
		};
	};
	if (!migrationValues(loadSettingsDocument(path)).needed) return false;
	ensureDocumentDirectory(path);
	const loaded = loadSettingsDocument(path);
	const migration = migrationValues(loaded);
	if (!migration.needed) return false;
	let output;
	if (loaded.format === "yaml") {
		loaded.yaml.setIn([DESKTOP_NAMESPACE, "openBrowser"], migration.browserAccess);
		loaded.yaml.setIn([DESKTOP_NAMESPACE, "networkExposure"], migration.networkExposure);
		output = loaded.yaml.toString();
	} else {
		const root = structuredClone(loaded.root);
		const nextDesktop = { ...section(root, DESKTOP_NAMESPACE) };
		nextDesktop.openBrowser = migration.browserAccess;
		nextDesktop.networkExposure = migration.networkExposure;
		root[DESKTOP_NAMESPACE] = nextDesktop;
		output = `${JSON.stringify(root, void 0, 2)}\n`;
	}
	await writeFileAtomic(path, output, {
		mode: DOCUMENT_FILE_MODE,
		dirMode: DOCUMENT_DIRECTORY_MODE
	});
	return true;
}
Object.freeze({
	desktopNamespace: DESKTOP_NAMESPACE,
	notificationsNamespace: NOTIFICATIONS_NAMESPACE,
	maxDocumentBytes: MAX_DOCUMENT_BYTES,
	fileMode: DOCUMENT_FILE_MODE
});
//#endregion
//#region src/setup-wizard-contract.ts
const SELECTION_KEYS = Object.freeze([
	"mode",
	"macosMaterial",
	"windowsMaterial",
	"openBrowser",
	"networkExposure",
	"market",
	"notifications"
]);
const INPUT_KEYS = Object.freeze([
	...SELECTION_KEYS,
	"profileName",
	"platform",
	"micaSupported"
]);
const NOTIFICATION_KEYS = Object.freeze([
	"enabled",
	"notifyOnTurnCompletion",
	"notifyOnTurnFailure",
	"notifyOnJobCompletion",
	"notifyOnJobFailure"
]);
function isObject(value) {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}
function hasExactKeys(value, expected) {
	const actual = Object.keys(value);
	return actual.length === expected.length && actual.every((key) => expected.includes(key));
}
function isMode(value) {
	return value === "compatibility" || value === "extended" || value === "advanced";
}
function isMacosMaterial(value) {
	return value === "off" || value === "transparent";
}
function isWindowsMaterial(value) {
	return value === "off" || value === "acrylic" || value === "mica";
}
function isNetworkExposure(value) {
	return value === "loopback" || value === "lan";
}
function isMarket(value) {
	return value === "disabled" || value === "community-market" || value === "dsh-market";
}
function isPlatform(value) {
	return value === "darwin" || value === "win32" || value === "linux";
}
function isDesktopSetupWizardNotifications(value) {
	return isObject(value) && hasExactKeys(value, NOTIFICATION_KEYS) && NOTIFICATION_KEYS.every((key) => typeof value[key] === "boolean");
}
function hasSelectionValues(value) {
	return isMode(value.mode) && isMacosMaterial(value.macosMaterial) && isWindowsMaterial(value.windowsMaterial) && typeof value.openBrowser === "boolean" && isNetworkExposure(value.networkExposure) && isMarket(value.market) && isDesktopSetupWizardNotifications(value.notifications);
}
/** Strictly validate the bounded JSON state loaded by the local document. */
function isDesktopSetupWizardInput(value) {
	if (!isObject(value) || !hasExactKeys(value, INPUT_KEYS) || !hasSelectionValues(value)) return false;
	return typeof value.profileName === "string" && value.profileName.length > 0 && new TextEncoder().encode(value.profileName).byteLength <= 255 && !value.profileName.includes("/") && !value.profileName.includes("\\") && value.profileName !== "." && value.profileName !== ".." && value.profileName !== "node_modules" && !/[\0-\x1f\x7f-\x9f]/u.test(value.profileName) && !/[<>:"|?*]/u.test(value.profileName) && !/[. ]$/u.test(value.profileName) && !/^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$/iu.test(value.profileName) && isPlatform(value.platform) && typeof value.micaSupported === "boolean";
}
/** Reject selections the current platform cannot actually present. */
function desktopSetupWizardSelectionIsAvailable(selection, capabilities) {
	if (selection.openBrowser && selection.mode !== "compatibility") return false;
	if (!selection.openBrowser && selection.networkExposure === "lan") return false;
	if (capabilities.platform === "linux" && selection.mode !== "compatibility") return false;
	return capabilities.platform !== "win32" || selection.windowsMaterial !== "mica" || capabilities.micaSupported;
}
/** Freeze a complete result before it crosses back into launcher orchestration. */
function freezeDesktopSetupWizardSelection(selection) {
	const notifications = Object.freeze({ ...selection.notifications });
	return Object.freeze({
		...selection,
		notifications
	});
}
//#endregion
//#region src/setup-wizard-copy.ts
const COPY = {
	en: {
		beta: "Beta",
		title: "Set up DSH Desktop",
		profile: "Profile",
		welcomeTitle: "Welcome to DSH Desktop",
		welcomeBody: "This wizard configures the Desktop experience for the Profile shown below.",
		firstProfileSetup: "This is the first time you are setting up Desktop mode for this Profile.",
		startSetup: "Start setup",
		presentationTitle: "Choose a window mode",
		presentationBody: "Choose how DSH Desktop presents the official client.",
		compatibilityMode: "Compatibility mode",
		compatibilityModeBody: "Keep the official client layout for the broadest compatibility.",
		extendedMode: "Extended window",
		extendedModeBody: "Add Desktop controls around the official content area.",
		advancedMode: "Enhanced mode",
		advancedModeBody: "Use the layout and window interactions optimized for Desktop.",
		unavailableOnLinux: "This mode is currently available on macOS and Windows.",
		windowMaterial: "Choose a window material",
		windowMaterialBody: "Choose the transparency or glass effect used by the Desktop window.",
		materialOff: "No window material",
		materialOffBody: "Use a solid, opaque window background.",
		materialTransparent: "Transparent",
		materialTransparentBody: "Let content behind the window show through the Desktop surface.",
		materialAcrylic: "Acrylic",
		materialAcrylicBody: "Use the Windows acrylic blur material.",
		materialMica: "Mica",
		materialMicaBody: "Use the native Windows Mica material when it is supported.",
		browserTitle: "Set up browser access",
		browserBody: "Choose whether this Profile may be opened in a browser and who may reach it.",
		openBrowser: "Allow opening this Profile in a browser",
		browserCompatibilityNotice: "Browser access is only available in compatibility mode.",
		browserCompatibilityDialogTitle: "Switch to compatibility mode?",
		browserCompatibilityDialogBody: "Opening this Profile in a browser requires compatibility mode. Continue to switch the window mode and enable browser access.",
		confirmBrowserCompatibility: "Switch and enable",
		cancelBrowserCompatibility: "Cancel",
		networkExposure: "Network access",
		networkExposureBody: "Loopback keeps access on this computer. LAN makes the client reachable from your local network.",
		loopback: "This computer only",
		loopbackBody: "Listen on loopback addresses only.",
		lan: "Local network",
		lanBody: "Allow other devices on the same LAN to open and operate the client.",
		lanWarningTitle: "Allow control from your local network?",
		lanWarningBody: "This is dangerous: everyone on your local network may be able to operate your computer directly. Enable it only with great care. Browser security restrictions may prevent some security modules from working when DSH Desktop is accessed over HTTP from the local network, which may cause it not to work correctly.",
		confirmLan: "Enable LAN access",
		cancelLan: "Keep this computer only",
		marketTitle: "Choose a plugin market",
		marketBody: "Choose one plugin market for this Desktop installation.",
		marketDisabled: "Do not enable a plugin market",
		marketDisabledBody: "Keep plugin market features turned off.",
		communityMarket: "dsh-community-market",
		communityMarketBody: "The open market built into DSH Desktop, including custom data sources.",
		dshMarket: "dsh-market",
		dshMarketBody: "The popular community market powered by awesome-dsh-plugin data.",
		notificationsTitle: "Set up Desktop notifications",
		notificationsBody: "Choose which completion and failure events send a system notification. Notification text never includes conversation content.",
		notificationsEnabled: "Enable Desktop notifications",
		turnCompletion: "User turn completed",
		turnFailure: "User turn failed",
		jobCompletion: "Background job completed",
		jobFailure: "Background job failed",
		back: "Previous",
		next: "Next",
		skip: "Skip setup",
		skipDialogTitle: "Skip setup?",
		skipDialogBody: "You can still configure all of these options later under Settings > Desktop settings.",
		cancelSkip: "Continue setup",
		confirmSkip: "Skip setup",
		successTitle: "Setup complete",
		successBody: "DSH Desktop is ready for this Profile.",
		startUsing: "Start using DSH Desktop",
		invalidState: "Setup information could not be loaded. Close this window and try again."
	},
	zh: {
		beta: "Beta",
		title: "设置 DSH Desktop",
		profile: "Profile",
		welcomeTitle: "欢迎设置 DSH Desktop",
		welcomeBody: "此向导将为下方 Profile 配置桌面体验。",
		firstProfileSetup: "这是您第一次为这个 Profile 设置桌面模式。",
		startSetup: "开始设置",
		presentationTitle: "选择窗口模式",
		presentationBody: "选择 DSH Desktop 如何呈现官方客户端。",
		compatibilityMode: "兼容模式",
		compatibilityModeBody: "保留官方客户端布局，兼容性最好。",
		extendedMode: "扩展窗口",
		extendedModeBody: "在官方内容区域周围增加桌面控制。",
		advancedMode: "增强模式",
		advancedModeBody: "使用针对桌面端优化的布局和窗口交互。",
		unavailableOnLinux: "此模式目前支持 macOS 和 Windows。",
		windowMaterial: "选择窗口材质",
		windowMaterialBody: "选择桌面窗口使用的透明或玻璃效果。",
		materialOff: "不使用窗口材质",
		materialOffBody: "使用不透明的纯色窗口背景。",
		materialTransparent: "透明材质",
		materialTransparentBody: "让桌面窗口呈现可透出背后内容的透明效果。",
		materialAcrylic: "亚克力",
		materialAcrylicBody: "使用 Windows 亚克力模糊材质。",
		materialMica: "Mica",
		materialMicaBody: "在系统支持时使用 Windows 原生 Mica 材质。",
		browserTitle: "设置浏览器访问",
		browserBody: "选择是否允许在浏览器中打开这个 Profile，以及谁可以访问。",
		openBrowser: "允许在浏览器中打开",
		browserCompatibilityNotice: "浏览器访问仅在兼容模式下可用。",
		browserCompatibilityDialogTitle: "切换到兼容模式？",
		browserCompatibilityDialogBody: "在浏览器中打开只能使用兼容模式。继续将把这个 Profile 的窗口模式切换为兼容模式，并开启浏览器访问。",
		confirmBrowserCompatibility: "切换并开启",
		cancelBrowserCompatibility: "取消",
		networkExposure: "网络访问范围",
		networkExposureBody: "仅本机访问只监听回环地址；局域网访问会让同一网络中的设备能够打开客户端。",
		loopback: "仅这台电脑",
		loopbackBody: "只监听本机回环地址。",
		lan: "局域网",
		lanBody: "允许同一局域网中的其他设备打开并操作客户端。",
		lanWarningTitle: "允许局域网中的设备控制吗？",
		lanWarningBody: "这样很危险，所有在你局域网内的人都能直接操作你的电脑，请谨慎开启。由于浏览器安全限制，从局域网内使用 HTTP 访问时，部分安全模块可能不可用，可能导致 DSH Desktop 无法正常使用。",
		confirmLan: "确认开启局域网访问",
		cancelLan: "保持仅本机访问",
		marketTitle: "选择插件市场",
		marketBody: "为这套桌面安装选择一个插件市场。",
		marketDisabled: "不启用插件市场",
		marketDisabledBody: "保持插件市场功能关闭。",
		communityMarket: "dsh-community-market",
		communityMarketBody: "DSH Desktop 内置的开放市场，并支持自定义数据源。",
		dshMarket: "dsh-market",
		dshMarketBody: "使用 awesome-dsh-plugin 数据的热门社区市场。",
		notificationsTitle: "设置桌面通知",
		notificationsBody: "选择哪些完成或失败事件发送系统通知。通知文本不会包含会话内容。",
		notificationsEnabled: "启用桌面通知",
		turnCompletion: "用户回合完成",
		turnFailure: "用户回合失败",
		jobCompletion: "后台任务完成",
		jobFailure: "后台任务失败",
		back: "上一步",
		next: "下一步",
		skip: "跳过设置",
		skipDialogTitle: "跳过设置？",
		skipDialogBody: "之后仍可在“设置” > “桌面设置”中配置这里的所有内容。",
		cancelSkip: "继续设置",
		confirmSkip: "确认跳过",
		successTitle: "设置成功",
		successBody: "这个 Profile 的 DSH Desktop 已准备就绪。",
		startUsing: "开始使用",
		invalidState: "无法加载设置信息。请关闭此窗口后重试。"
	}
};
function desktopSetupWizardCopy(locale) {
	return COPY[locale];
}
//#endregion
//#region src/setup-wizard-window.ts
/** Isolated pre-Host Setup Wizard window with a strict navigation result channel. */
const SETUP_WIZARD_SCHEME = "dsh-setup-wizard:";
const SETUP_WIZARD_DOCUMENT = fileURLToPath(new URL("./native-ui/setup-wizard.html", import.meta.url));
const MAX_ACTION_BYTES = 8192;
const COMPLETE_KEYS = Object.freeze([
	"mode",
	"macosMaterial",
	"windowsMaterial",
	"openBrowser",
	"networkExposure",
	"market",
	"notificationsEnabled",
	"notifyOnTurnCompletion",
	"notifyOnTurnFailure",
	"notifyOnJobCompletion",
	"notifyOnJobFailure"
]);
function exactBoolean(value) {
	if (value === "true") return true;
	if (value === "false") return false;
}
function exactMode(value) {
	return value === "compatibility" || value === "extended" || value === "advanced" ? value : void 0;
}
function exactMacosMaterial(value) {
	return value === "off" || value === "transparent" ? value : void 0;
}
function exactWindowsMaterial(value) {
	return value === "off" || value === "acrylic" || value === "mica" ? value : void 0;
}
function exactNetworkExposure(value) {
	return value === "loopback" || value === "lan" ? value : void 0;
}
function exactMarket(value) {
	return value === "disabled" || value === "community-market" || value === "dsh-market" ? value : void 0;
}
/** Parse only a bounded, complete result generated by the local Setup document. */
function parseDesktopSetupWizardAction(href) {
	if (new TextEncoder().encode(href).byteLength > MAX_ACTION_BYTES) return void 0;
	let url;
	try {
		url = new URL(href);
	} catch {
		return;
	}
	if (url.protocol !== SETUP_WIZARD_SCHEME || url.username !== "" || url.password !== "" || url.port !== "" || url.pathname !== "" || url.hash !== "") return void 0;
	const keys = [...url.searchParams.keys()];
	if (url.hostname === "skip") return keys.length === 0 ? Object.freeze({ action: "skip" }) : void 0;
	if (url.hostname !== "complete" || keys.length !== COMPLETE_KEYS.length || keys.some((key) => !COMPLETE_KEYS.includes(key)) || COMPLETE_KEYS.some((key) => url.searchParams.getAll(key).length !== 1)) return void 0;
	const mode = exactMode(url.searchParams.get("mode"));
	const macosMaterial = exactMacosMaterial(url.searchParams.get("macosMaterial"));
	const windowsMaterial = exactWindowsMaterial(url.searchParams.get("windowsMaterial"));
	const openBrowser = exactBoolean(url.searchParams.get("openBrowser"));
	const networkExposure = exactNetworkExposure(url.searchParams.get("networkExposure"));
	const market = exactMarket(url.searchParams.get("market"));
	const enabled = exactBoolean(url.searchParams.get("notificationsEnabled"));
	const notifyOnTurnCompletion = exactBoolean(url.searchParams.get("notifyOnTurnCompletion"));
	const notifyOnTurnFailure = exactBoolean(url.searchParams.get("notifyOnTurnFailure"));
	const notifyOnJobCompletion = exactBoolean(url.searchParams.get("notifyOnJobCompletion"));
	const notifyOnJobFailure = exactBoolean(url.searchParams.get("notifyOnJobFailure"));
	if (mode === void 0 || macosMaterial === void 0 || windowsMaterial === void 0 || openBrowser === void 0 || networkExposure === void 0 || market === void 0 || enabled === void 0 || notifyOnTurnCompletion === void 0 || notifyOnTurnFailure === void 0 || notifyOnJobCompletion === void 0 || notifyOnJobFailure === void 0) return void 0;
	const selection = freezeDesktopSetupWizardSelection({
		mode,
		macosMaterial,
		windowsMaterial,
		openBrowser,
		networkExposure,
		market,
		notifications: {
			enabled,
			notifyOnTurnCompletion,
			notifyOnTurnFailure,
			notifyOnJobCompletion,
			notifyOnJobFailure
		}
	});
	return Object.freeze({
		action: "complete",
		selection
	});
}
/** One-shot native Setup Wizard; close is distinct from the explicit Skip action. */
var DesktopSetupWizardWindow = class {
	options;
	started = false;
	window;
	constructor(options) {
		this.options = options;
	}
	/** Bring the running Wizard forward for app activation and second-instance events. */
	show() {
		const window = this.window;
		if (window === void 0 || window.isDestroyed()) return;
		revealApplication(window, this.options.input.platform);
	}
	async run() {
		if (this.started) throw new Error("dsh-plugin-desktop: Setup Wizard can only run once");
		this.started = true;
		if (!isDesktopSetupWizardInput(this.options.input)) throw new TypeError("dsh-plugin-desktop: invalid Setup Wizard input");
		const { input } = this.options;
		const copy = desktopSetupWizardCopy(this.options.locale);
		const state = Buffer.from(JSON.stringify(input), "utf8").toString("base64url");
		const customFrame = auxiliaryWindowHasCustomFrame(input.platform);
		const window = new BrowserWindow({
			title: copy.title,
			...auxiliaryWindowChromeOptions(input.platform),
			width: 880,
			height: 720,
			minWidth: 680,
			minHeight: 560,
			useContentSize: true,
			resizable: true,
			maximizable: false,
			fullscreenable: false,
			show: input.platform === "win32",
			autoHideMenuBar: true,
			backgroundColor: "#202124",
			webPreferences: {
				contextIsolation: true,
				nodeIntegration: false,
				nodeIntegrationInSubFrames: false,
				sandbox: true,
				webSecurity: true,
				webviewTag: false,
				spellcheck: false,
				partition: "dsh-setup-wizard"
			}
		});
		this.window = window;
		window.accessibleTitle = copy.title;
		window.removeMenu();
		window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
		window.webContents.on("will-attach-webview", (event) => {
			event.preventDefault();
		});
		return await new Promise((resolve, reject) => {
			let settled = false;
			const finish = (result) => {
				if (settled) return;
				settled = true;
				if (this.window === window) this.window = void 0;
				if (!window.isDestroyed()) window.destroy();
				resolve(result);
			};
			const navigate = (event, href) => {
				event.preventDefault();
				const action = parseDesktopSetupWizardAction(href);
				if (action === void 0) return;
				if (action.action === "complete" && !desktopSetupWizardSelectionIsAvailable(action.selection, input)) return;
				finish(action);
			};
			window.webContents.on("will-navigate", navigate);
			window.webContents.on("will-redirect", navigate);
			window.once("ready-to-show", () => {
				if (!settled && this.window === window && !window.isDestroyed()) revealApplication(window, input.platform);
			});
			window.on("closed", () => {
				if (this.window === window) this.window = void 0;
				finish(Object.freeze({ action: "quit" }));
			});
			window.loadFile(SETUP_WIZARD_DOCUMENT, { query: {
				locale: this.options.locale,
				state,
				platform: input.platform,
				frame: String(customFrame)
			} }).catch((cause) => {
				if (settled) return;
				settled = true;
				if (this.window === window) this.window = void 0;
				if (!window.isDestroyed()) window.destroy();
				reject(cause);
			});
		});
	}
};
//#endregion
//#region src/profile-materializer.ts
/** Re-materialize a restored profile before the Cordis Host is created. */
const ELECTRON_HEADERS_URL$1 = "https://electronjs.org/headers";
const DEFAULT_TIMEOUT_MS$1 = 12e4;
const DEFAULT_MAX_OUTPUT_BYTES$1 = 256 * 1024;
const TERMINATION_GRACE_MS = 3e3;
const DIAGNOSTIC_STREAM_CHARS = 8e3;
/** Error raised when profile materialization cannot complete successfully. */
var ProfileMaterializationError = class extends Error {
	result;
	constructor(message, result) {
		super(message);
		this.name = "ProfileMaterializationError";
		if (result !== void 0) this.result = result;
	}
};
function diagnosticStream$1(label, value) {
	const normalized = value.trim();
	if (normalized.length === 0) return void 0;
	return `${label}:\n${normalized.length <= DIAGNOSTIC_STREAM_CHARS ? normalized : `${normalized.slice(0, DIAGNOSTIC_STREAM_CHARS)}\n… ${label} truncated`}`;
}
/** Bounded technical context suitable for a local recovery error window. */
function formatProfileMaterializationFailure(cause) {
	if (!(cause instanceof ProfileMaterializationError)) return cause instanceof Error ? cause.stack ?? cause.message : String(cause);
	const result = cause.result;
	if (result === void 0) return cause.stack ?? cause.message;
	return [
		"Profile dependency materialization failed.",
		`Command: ${`pnpm ${result.argv.slice(4).join(" ")}`}`,
		`Working directory: ${result.cwd}`,
		`Exit status: ${String(result.exitCode)}`,
		`Signal: ${result.signal ?? "none"}`,
		diagnosticStream$1("stderr", result.stderr),
		diagnosticStream$1("stdout", result.stdout)
	].filter((section) => section !== void 0).join("\n\n");
}
function inheritedPath$1() {
	const exact = process.env.PATH;
	if (exact !== void 0 || process.platform !== "win32") return exact ?? "";
	return Object.entries(process.env).find(([key]) => key.toUpperCase() === "PATH")?.[1] ?? "";
}
function assertAbsolutePath$1(label, value) {
	if (value.length === 0 || value.includes("\0") || !isAbsolute(value)) throw new ProfileMaterializationError(`profile materializer ${label} must be an absolute path without NUL`);
}
function assertPositiveFinite$1(label, value) {
	if (!Number.isFinite(value) || value <= 0) throw new ProfileMaterializationError(`profile materializer ${label} must be positive`);
}
function killProcessTree(child, force = false) {
	const signal = force ? "SIGKILL" : "SIGTERM";
	try {
		if (process.platform !== "win32" && child.pid !== void 0) process.kill(-child.pid, signal);
		else child.kill(signal);
	} catch {
		try {
			child.kill(signal);
		} catch {}
	}
}
function appendOutput(chunks, chunk, currentLength, maxBytes) {
	const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
	const nextLength = currentLength + buffer.byteLength;
	if (nextLength > maxBytes) throw new ProfileMaterializationError(`profile materializer output exceeded ${String(maxBytes)} bytes`);
	chunks.push(buffer);
	return nextLength;
}
/**
* Restore dependencies for an already-restored profile without creating a
* Host or using a shell. Restores use a frozen lockfile; an explicit Profile
* layout migration may reconcile obsolete pnpm settings in that lockfile.
*/
async function materializeProfile(options) {
	for (const [label, value] of [
		["application executable", options.appExecutable],
		["environment preloader", options.clearEnvironmentPath],
		["pnpm entry", options.pnpmBinPath],
		["Node command directory", options.nodeBinDir],
		["Node command", options.nodeShimPath],
		["Harness home", options.homeDir],
		["profile directory", options.profileDir]
	]) assertAbsolutePath$1(label, value);
	if (options.electronVersion.length === 0 || options.electronVersion.includes("\0")) throw new ProfileMaterializationError("profile materializer Electron version must not be empty or contain NUL");
	const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS$1;
	const maxOutputBytes = options.maxOutputBytes ?? DEFAULT_MAX_OUTPUT_BYTES$1;
	assertPositiveFinite$1("timeout", timeoutMs);
	assertPositiveFinite$1("maximum output", maxOutputBytes);
	options.signal?.throwIfAborted();
	const argv = [
		options.appExecutable,
		"--import",
		pathToFileURL(options.clearEnvironmentPath).href,
		options.pnpmBinPath,
		PNPM_IGNORE_MINIMUM_RELEASE_AGE,
		"install",
		options.updateLockfile === true ? "--no-frozen-lockfile" : "--frozen-lockfile"
	];
	const path = inheritedPath$1();
	const environment = {
		...process.env,
		PATH: path.length === 0 ? options.nodeBinDir : `${options.nodeBinDir}${delimiter}${path}`,
		NODE: options.nodeShimPath,
		ELECTRON_RUN_AS_NODE: "1",
		DSH_HOME: options.homeDir,
		CI: "true",
		npm_config_runtime: "electron",
		npm_config_target: options.electronVersion,
		npm_config_disturl: ELECTRON_HEADERS_URL$1
	};
	const child = (options.spawn ?? spawn)(options.appExecutable, argv.slice(1), {
		cwd: options.profileDir,
		env: environment,
		shell: false,
		detached: process.platform !== "win32",
		stdio: [
			"ignore",
			"pipe",
			"pipe"
		],
		windowsHide: true
	});
	if (child.stdout === null || child.stderr === null) {
		killProcessTree(child);
		throw new ProfileMaterializationError("profile materializer subprocess did not expose piped output");
	}
	const stdout = child.stdout;
	const stderr = child.stderr;
	const stdoutChunks = [];
	const stderrChunks = [];
	let stdoutLength = 0;
	let stderrLength = 0;
	let failure;
	let terminationTimer;
	let timeoutTimer;
	let settled = false;
	return await new Promise((resolve, reject) => {
		const terminate = (cause) => {
			if (failure !== void 0) return;
			failure = cause;
			killProcessTree(child);
			terminationTimer = setTimeout(() => {
				killProcessTree(child, true);
			}, TERMINATION_GRACE_MS);
			terminationTimer.unref();
		};
		const acceptStdout = (chunk) => {
			try {
				stdoutLength = appendOutput(stdoutChunks, chunk, stdoutLength, maxOutputBytes);
			} catch (cause) {
				terminate(cause instanceof Error ? cause : new Error(String(cause)));
			}
		};
		const acceptStderr = (chunk) => {
			try {
				stderrLength = appendOutput(stderrChunks, chunk, stderrLength, maxOutputBytes);
			} catch (cause) {
				terminate(cause instanceof Error ? cause : new Error(String(cause)));
			}
		};
		const onAbort = () => {
			terminate(new ProfileMaterializationError("profile materializer was aborted"));
		};
		stdout.on("data", acceptStdout);
		stderr.on("data", acceptStderr);
		child.once("error", (cause) => {
			terminate(cause instanceof Error ? cause : new Error(String(cause)));
		});
		options.signal?.addEventListener("abort", onAbort, { once: true });
		timeoutTimer = setTimeout(() => {
			terminate(new ProfileMaterializationError(`profile materializer timed out after ${String(timeoutMs)}ms`));
		}, timeoutMs);
		timeoutTimer.unref();
		child.once("close", (exitCode, signal) => {
			if (settled) return;
			settled = true;
			if (timeoutTimer !== void 0) clearTimeout(timeoutTimer);
			if (terminationTimer !== void 0) clearTimeout(terminationTimer);
			options.signal?.removeEventListener("abort", onAbort);
			const result = {
				argv,
				cwd: options.profileDir,
				exitCode,
				signal,
				stdout: Buffer.concat(stdoutChunks).toString("utf8"),
				stderr: Buffer.concat(stderrChunks).toString("utf8")
			};
			if (failure !== void 0) reject(new ProfileMaterializationError(failure.message, result));
			else if (exitCode !== 0 || signal !== null) reject(new ProfileMaterializationError(`profile materializer exited unsuccessfully (code=${String(exitCode)}, signal=${String(signal)})`, result));
			else resolve(result);
		});
	});
}
//#endregion
//#region src/recovery-plugin-uninstall.ts
/** Run the official DSH plugin-removal flow before the Cordis Host starts. */
const DEFAULT_TIMEOUT_MS = 12e4;
const DEFAULT_MAX_OUTPUT_BYTES = 256 * 1024;
const ELECTRON_HEADERS_URL = "https://electronjs.org/headers";
const PACKAGE_NAME_PATTERN = /^(?:@[a-z0-9][a-z0-9._-]*\/)?[a-z0-9][a-z0-9._-]*$/u;
var RecoveryPluginUninstallError = class extends Error {
	result;
	constructor(message, result) {
		super(message);
		this.result = result;
		this.name = "RecoveryPluginUninstallError";
	}
};
function assertAbsolutePath(label, value) {
	if (value.length === 0 || value.includes("\0") || !isAbsolute(value)) throw new RecoveryPluginUninstallError(`recovery plugin uninstall ${label} must be an absolute path without NUL`);
}
function inheritedPath(environment, platform) {
	const exact = environment.PATH;
	if (exact !== void 0 || platform !== "win32") return exact ?? "";
	return Object.entries(environment).find(([key]) => key.toUpperCase() === "PATH")?.[1] ?? "";
}
/** Build the fixed Desktop command environment used after Host quiescence. */
function recoveryPluginEnvironment(options, platform = process.platform) {
	const environment = { ...options.environment ?? process.env };
	if (platform === "win32") {
		for (const key of Object.keys(environment)) if (key.toUpperCase() === "PATH") delete environment[key];
	}
	const path = inheritedPath(options.environment ?? process.env, platform);
	environment.PATH = [
		options.nodeBinDir,
		options.pnpmBinDir,
		path
	].filter((value) => value.length > 0).join(platform === "win32" ? ";" : ":");
	environment.NODE = options.nodeShimPath;
	environment.ELECTRON_RUN_AS_NODE = "1";
	environment.DSH_HOME = options.homeDir;
	environment.CI = "true";
	environment.npm_config_runtime = "electron";
	environment.npm_config_target = options.electronVersion;
	environment.npm_config_disturl = ELECTRON_HEADERS_URL;
	return environment;
}
function diagnosticStream(label, value) {
	const normalized = value.trim();
	return normalized.length === 0 ? void 0 : `${label}:\n${normalized}`;
}
/** Bounded technical context suitable for a local Desktop error window. */
function formatRecoveryPluginRemoveFailure(cause) {
	if (!(cause instanceof RecoveryPluginUninstallError) || cause.result === void 0) return cause instanceof Error ? cause.stack ?? cause.message : String(cause);
	return [
		"DSH plugin uninstall failed.",
		`Command: dsh plugin --profile ${cause.result.profileName} remove ${cause.result.packageName}`,
		`Package-manager policy: ${PNPM_IGNORE_MINIMUM_RELEASE_AGE}`,
		`Exit status: ${String(cause.result.exitCode)}`,
		`Signal: ${cause.result.signal ?? "none"}`,
		diagnosticStream("stderr", cause.result.stderr),
		diagnosticStream("stdout", cause.result.stdout)
	].filter((section) => section !== void 0).join("\n\n");
}
/**
* Remove one direct Profile dependency through the packaged `dsh plugin`
* entry. That command owns both pnpm mutation and bundle reconciliation.
*/
async function removeRecoveryPlugin(options) {
	assertDesktopProfileName(options.profileName);
	if (!PACKAGE_NAME_PATTERN.test(options.packageName)) throw new RecoveryPluginUninstallError("recovery plugin uninstall package name is invalid");
	for (const [label, value] of [
		["application executable", options.appExecutable],
		["DSH bootstrap", options.dshBootstrapPath],
		["Profile directory", options.profileDir],
		["Harness home", options.homeDir],
		["Node command directory", options.nodeBinDir],
		["Node command", options.nodeShimPath],
		["pnpm command directory", options.pnpmBinDir]
	]) assertAbsolutePath(label, value);
	if (options.electronVersion.length === 0 || options.electronVersion.includes("\0")) throw new RecoveryPluginUninstallError("recovery plugin uninstall Electron version is invalid");
	const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
	const maxBuffer = options.maxOutputBytes ?? DEFAULT_MAX_OUTPUT_BYTES;
	if (!Number.isFinite(timeoutMs) || timeoutMs <= 0 || !Number.isFinite(maxBuffer) || maxBuffer <= 0) throw new RecoveryPluginUninstallError("recovery plugin uninstall process limits are invalid");
	options.signal?.throwIfAborted();
	const args = [
		"--expose-internals",
		options.dshBootstrapPath,
		"plugin",
		"--profile",
		options.profileName,
		"remove",
		options.packageName
	];
	return await new Promise((resolve, reject) => {
		execFile(options.appExecutable, args, {
			cwd: options.profileDir,
			encoding: "utf8",
			env: recoveryPluginEnvironment(options),
			maxBuffer,
			timeout: timeoutMs,
			windowsHide: true,
			...options.signal === void 0 ? {} : { signal: options.signal }
		}, (cause, stdout, stderr) => {
			if (cause === null) {
				resolve({
					packageName: options.packageName,
					profileName: options.profileName,
					exitCode: 0,
					stdout,
					stderr
				});
				return;
			}
			reject(new RecoveryPluginUninstallError(`dsh plugin remove exited unsuccessfully (code=${String(cause.code)}, signal=${String(cause.signal)})`, {
				packageName: options.packageName,
				profileName: options.profileName,
				exitCode: cause.code ?? null,
				signal: cause.signal ?? null,
				stdout,
				stderr
			}));
		});
	});
}
//#endregion
//#region src/shutdown.ts
/** Application-level quit sources that must remain active before any window mounts. */
/** Maximum grace allowed for the Cordis tree to dispose before native exit. */
const DESKTOP_SHUTDOWN_TIMEOUT_MS = 5e3;
/**
* Coordinate the final Electron action without relaunching failed generations.
* @param native - native application and runtime exit operations.
* @param beforeExit - listener cleanup that must precede app.exit.
* @returns a final-exit controller consumed by the shutdown path.
*/
function createDesktopExitCoordinator(native, beforeExit) {
	let relaunchArguments = false;
	return {
		requestRelaunch(args) {
			relaunchArguments = args ?? [];
		},
		finish(code) {
			beforeExit();
			native.prepareToQuit();
			if (relaunchArguments !== false && code === 0) native.relaunch(relaunchArguments.length === 0 ? void 0 : relaunchArguments);
			native.exit(code);
		}
	};
}
/**
* Create one bounded shutdown around the Host Cordis disposer.
* @param dispose - whole Host tree teardown.
* @param exit - final native process exit.
* @param timeoutMs - grace before forced exit.
* @returns a controller whose second request escalates immediately.
*/
function createDesktopShutdown(dispose, exit, timeoutMs = DESKTOP_SHUTDOWN_TIMEOUT_MS) {
	let pending;
	let timeout;
	let exited = false;
	const exitOnce = (code) => {
		if (exited) return;
		exited = true;
		if (timeout !== void 0) clearTimeout(timeout);
		exit(code);
	};
	return { request(code) {
		if (pending !== void 0) {
			exitOnce(code);
			return pending;
		}
		const failureCode = code === 0 ? 1 : code;
		timeout = setTimeout(() => {
			exitOnce(failureCode);
		}, timeoutMs);
		pending = Promise.resolve().then(dispose).then(() => {
			exitOnce(code);
		}, () => {
			exitOnce(failureCode);
		});
		return pending;
	} };
}
/**
* Route every application-level quit source through Cordis teardown.
* @param signals - process signal owner.
* @param nativeApp - Electron application event owner.
* @param requestQuit - idempotent launcher shutdown request.
* @returns a disposer removing every listener.
*/
function installShutdownRequests(signals, nativeApp, requestQuit) {
	const interrupt = () => {
		requestQuit(130);
	};
	const terminate = () => {
		requestQuit(0);
	};
	const beforeQuit = (event) => {
		event.preventDefault();
		requestQuit(0);
	};
	const windowAllClosed = () => {};
	signals.on("SIGINT", interrupt);
	signals.on("SIGTERM", terminate);
	nativeApp.on("before-quit", beforeQuit);
	nativeApp.on("window-all-closed", windowAllClosed);
	return () => {
		signals.off("SIGINT", interrupt);
		signals.off("SIGTERM", terminate);
		nativeApp.off("before-quit", beforeQuit);
		nativeApp.off("window-all-closed", windowAllClosed);
	};
}
//#endregion
//#region src/relaunch-arguments.ts
/** One-process launch marker used to enter recovery before Profile Host boot. */
const DESKTOP_RECOVERY_MODE_ARGUMENT = "--dsh-desktop-recovery";
/** Rebuild the current Electron command line without retaining recovery mode. */
function desktopDefaultRelaunchArguments(argv = process.argv) {
	return argv.slice(1).filter((argument) => argument !== DESKTOP_RECOVERY_MODE_ARGUMENT);
}
/** Build a one-shot recovery-mode command line. */
function desktopRecoveryRelaunchArguments(argv = process.argv) {
	return [...desktopDefaultRelaunchArguments(argv), DESKTOP_RECOVERY_MODE_ARGUMENT];
}
/** Detect an explicit recovery-mode launch without accepting prefix variants. */
function desktopRecoveryModeRequested(argv = process.argv) {
	return argv.slice(1).includes(DESKTOP_RECOVERY_MODE_ARGUMENT);
}
//#endregion
//#region src/session-projcache-recovery.ts
const BIN_NAME$1 = "dsh-plugin-desktop";
const SESSION_PROJCACHE_RELATIVE_PATH = ["storages", "session_projcache.json"];
function assertAbsoluteHome(homeDir) {
	if (!isAbsolute(homeDir) || homeDir.includes("\0")) throw new Error(`${BIN_NAME$1}: session projection cache recovery requires an absolute DSH home path`);
}
function assertPositiveFinite(label, value) {
	if (!Number.isFinite(value) || value <= 0) throw new Error(`${BIN_NAME$1}: session projection cache recovery ${label} must be positive`);
}
function compactTimestamp(date) {
	return `${String(date.getUTCFullYear())}${String(date.getUTCMonth() + 1).padStart(2, "0")}${String(date.getUTCDate()).padStart(2, "0")}T${String(date.getUTCHours()).padStart(2, "0")}${String(date.getUTCMinutes()).padStart(2, "0")}${String(date.getUTCSeconds()).padStart(2, "0")}${String(date.getUTCMilliseconds()).padStart(3, "0")}Z`;
}
function uniqueBackupPath(cachePath, stamp) {
	const dir = dirname(cachePath);
	const extension = extname(cachePath);
	const prefix = join(dir, `${basename(cachePath, extension)}.oversized-${stamp}`);
	const first = `${prefix}${extension}`;
	if (!existsSync(first)) return first;
	for (let attempt = 1; attempt < Number.MAX_SAFE_INTEGER; attempt += 1) {
		const candidate = `${prefix}.${String(attempt)}${extension}`;
		if (!existsSync(candidate)) return candidate;
	}
	throw new Error(`${BIN_NAME$1}: could not allocate a unique oversized session projection cache backup path`);
}
function recoverOversizedSessionProjectionCache(homeDir, options = {}) {
	assertAbsoluteHome(homeDir);
	const maxBytes = options.maxBytes ?? 134217728;
	assertPositiveFinite("size limit", maxBytes);
	const cachePath = join(homeDir, ...SESSION_PROJCACHE_RELATIVE_PATH);
	let stat;
	try {
		stat = lstatSync(cachePath);
	} catch (cause) {
		if (cause.code === "ENOENT") return {
			status: "missing",
			cachePath
		};
		throw cause;
	}
	if (!stat.isFile() || stat.isSymbolicLink()) return {
		status: "non-file",
		cachePath
	};
	if (stat.size <= maxBytes) return {
		status: "within-limit",
		cachePath
	};
	const backupPath = uniqueBackupPath(cachePath, compactTimestamp((options.now ?? (() => /* @__PURE__ */ new Date()))()));
	renameSync(cachePath, backupPath);
	return {
		status: "quarantined",
		cachePath,
		backupPath,
		sizeBytes: stat.size
	};
}
//#endregion
//#region src/main.ts
/** DSH Desktop executable: minimal Electron bootstrap around the Host Cordis root. */
const BIN_NAME = "dsh-plugin-desktop";
const PRODUCT_NAME = "DSH Desktop";
var RendererStartupFailure = class extends Error {
	reason;
	constructor(reason, report) {
		super(report.error ?? `Renderer boot failed for ${String(report.plugins.length)} plugin(s)`);
		this.reason = reason;
		this.name = "RendererStartupFailure";
	}
};
function lifecycleRendererFailureReason(reason) {
	return reason === "renderer-timeout" ? "renderer-timeout" : "renderer-failed";
}
function lifecycleStartupFailureReason(cause, runtime) {
	if (cause instanceof RendererStartupFailure) return cause.reason;
	return runtime.rendererBootFailureReason ?? "startup-failed";
}
/** Report optional user UI plugins skipped to keep startup recoverable. */
function notifySkippedOptionalEntries(runtime, logger, entries) {
	if (entries.length === 0) return;
	const copy = desktopNativeCopy(runtime.locale);
	const names = entries.map((entry) => entry.name);
	try {
		runtime.updates.notify({
			title: copy.skippedPluginTitle,
			body: copy.skippedPluginBody(names[0], names.length - 1)
		});
	} catch (cause) {
		logger.error(`${BIN_NAME}: failed to show skipped plugin notification: ${cause instanceof Error ? cause.message : String(cause)}`);
	}
}
/** Surface path/volume risks that otherwise become obscure sandbox or pnpm failures later. */
function warnWindowsVolumeConcerns(logger, concerns) {
	for (const concern of concerns) logger.error(`${BIN_NAME}: Windows volume warning: ${formatWindowsVolumeConcern(concern)}`);
}
/** Notify once after the UI is ready; stderr carries the exact paths. */
function notifyWindowsVolumeConcerns(runtime, logger, concerns) {
	if (concerns.length === 0) return;
	const copy = desktopNativeCopy(runtime.locale);
	const concernLabel = concerns[0]?.label;
	const label = runtime.locale === "zh" ? concernLabel === "application install" ? "应用安装目录" : concernLabel === "desktop user data" ? "桌面用户数据" : concernLabel === "DSH home" ? "DSH 主目录" : "某个配置路径" : concernLabel ?? "A configured path";
	try {
		runtime.updates.notify({
			title: copy.unsupportedStorageTitle,
			body: copy.unsupportedStorageBody(label)
		});
	} catch (cause) {
		logger.error(`${BIN_NAME}: failed to show Windows volume warning: ${cause instanceof Error ? cause.message : String(cause)}`);
	}
}
function notifySessionProjectionCacheRecovery(runtime, logger, _recovery) {
	try {
		runtime.updates.notify({
			title: "Recovered Session Cache",
			body: "An oversized session projection cache was moved aside and will be rebuilt from session history."
		});
	} catch (cause) {
		logger.error(`${BIN_NAME}: failed to show session projection cache recovery notification: ${cause instanceof Error ? cause.message : String(cause)}`);
	}
}
/** Start one Electron process and leave lifetime to the mounted desktop plugin. */
async function start() {
	if (!app.requestSingleInstanceLock()) {
		app.quit();
		return;
	}
	if (isDesktopInstallerQuitRequest(process.argv, process.platform)) {
		app.quit();
		return;
	}
	let shutdown;
	let removeShutdownRequests;
	let removeUncaughtExceptionLogging;
	let removeChildProcessLogging;
	let fileExporter;
	let runtime;
	let logSink;
	let startupRecoveryController;
	let startupRecoveryWindow;
	let setupWizardWindow;
	let startupRecoveryConfigurationPaths;
	let profileCheckpoint;
	let startupRecoveryProfileActions;
	let sessionProjectionCacheRecovery;
	let profileRecoveryActionUsed = false;
	let recoveryTerminalAvailable = false;
	let startupStage = "electron-ready";
	const appVersion = desktopProductVersion();
	const recoveryModeRequested = desktopRecoveryModeRequested();
	try {
		logSink = new LogFileSink(join(app.getPath("userData"), "logs"), {
			maxFileBytes: 10 * 1024 * 1024,
			maxDirectoryBytes: 200 * 1024 * 1024
		});
		logSink.enforceDirectoryCap();
		logSink.purgeOlderThan(7);
		logSink.writeHeader(`--- ${BIN_NAME} ${PRODUCT_NAME} ${appVersion} ${process.platform} node ${process.version} run ${Date.now()} ---`);
	} catch (cause) {
		const detail = cause instanceof Error ? cause.message : String(cause);
		process.stderr.write(`${BIN_NAME}: file logging unavailable: ${maskSecrets(detail)}\n`);
		logSink = void 0;
	}
	const electronLogger = new ElectronStderrLogger(logSink);
	const generation = new DesktopStartupGeneration({ logger: electronLogger });
	const generationId = generation.id;
	const lifecycleRecorder = createDesktopLifecycleRecorder({
		userDataDir: app.getPath("userData"),
		appVersion,
		platform: process.platform,
		arch: process.arch,
		logger: electronLogger
	});
	lifecycleRecorder.startStartup(startupStage);
	try {
		startDesktopCrashReporting(crashReporter, {
			productName: PRODUCT_NAME,
			version: appVersion,
			platform: process.platform,
			arch: process.arch
		});
	} catch (cause) {
		electronLogger.error(`${BIN_NAME}: local crash reporting unavailable: ${cause instanceof Error ? cause.message : String(cause)}`);
	}
	let desktopRun;
	try {
		desktopRun = beginDesktopRun(join(app.getPath("userData"), "crash-evidence", "active-run.json"), {
			startedAt: (/* @__PURE__ */ new Date()).toISOString(),
			pid: process.pid,
			version: appVersion
		});
		const previousRun = desktopRun.previousRun;
		if (previousRun !== void 0) electronLogger.error("unreadable" in previousRun ? `${BIN_NAME}: previous desktop run did not shut down cleanly (active run marker unreadable)` : `${BIN_NAME}: previous desktop run did not shut down cleanly (startedAt: ${previousRun.startedAt}, pid: ${String(previousRun.pid)}, version: ${previousRun.version})`);
	} catch (cause) {
		electronLogger.error(`${BIN_NAME}: active run tracking unavailable: ${cause instanceof Error ? cause.message : String(cause)}`);
	}
	removeChildProcessLogging = installDesktopChildProcessLogging(app, electronLogger);
	const nativeExit = createDesktopExitCoordinator({
		prepareToQuit: () => {
			runtime.prepareToQuit();
		},
		relaunch: (args) => {
			app.relaunch({ args: [...args ?? desktopDefaultRelaunchArguments()] });
		},
		exit: (code) => {
			app.exit(code);
		}
	}, () => {
		removeShutdownRequests?.();
		removeUncaughtExceptionLogging?.();
		removeChildProcessLogging?.();
		try {
			desktopRun?.markClean();
		} catch (cause) {
			electronLogger.error(`${BIN_NAME}: failed to clear active run marker: ${cause instanceof Error ? cause.message : String(cause)}`);
		}
	});
	let restartRequested = false;
	runtime = new ElectronDesktopRuntime(async (target) => {
		if (shutdown === void 0) throw new Error("dsh-plugin-desktop: shutdown coordinator is not ready");
		if (restartRequested) return;
		restartRequested = true;
		nativeExit.requestRelaunch(target === "recovery" ? desktopRecoveryRelaunchArguments() : desktopDefaultRelaunchArguments());
		await shutdown.request(0);
	}, (report) => {
		if (report.status === "failed") lifecycleRecorder.finishRendererBoot(report, lifecycleRendererFailureReason(runtime.rendererBootFailureReason));
		return report.status === "failed";
	}, electronLogger, void 0, void 0, await getOrCreateDesktopInstallationId(app.getPath("userData")));
	const finalExit = (code) => {
		nativeExit.finish(code);
	};
	shutdown = createDesktopShutdown(async () => {
		await generation.release();
	}, finalExit);
	const requestQuit = (code) => {
		shutdown.request(code);
	};
	removeUncaughtExceptionLogging = installDesktopUncaughtExceptionLogging(process, electronLogger, requestQuit);
	removeShutdownRequests = installShutdownRequests(process, app, requestQuit);
	const openStartupRecoveryWindow = async (failureDetail, controller, requested = false) => {
		if (!app.isReady()) return "unavailable";
		try {
			startupRecoveryWindow = new DesktopStartupRecoveryWindow({
				...controller === void 0 ? {} : { controller },
				...startupRecoveryConfigurationPaths === void 0 ? {} : { configurationPaths: startupRecoveryConfigurationPaths },
				locale: desktopLocaleFromLanguageTag(app.getLocale()),
				failureStage: startupStage,
				failureDetail: maskSecrets(failureDetail),
				...requested ? { requested: true } : {},
				exportDiagnostics: async (signal) => await exportDesktopDiagnostics(app.getPath("userData"), {
					appVersion,
					crashDumpsDir: app.getPath("crashDumps"),
					signal
				}),
				...recoveryTerminalAvailable ? { openTerminal: () => {
					runtime.openTerminal();
				} } : {},
				...startupRecoveryProfileActions === void 0 ? {} : { profileActions: startupRecoveryProfileActions }
			});
			return await startupRecoveryWindow.run();
		} catch (cause) {
			electronLogger.error(`${BIN_NAME}: failed to open startup recovery window: ${cause instanceof Error ? cause.message : String(cause)}`);
			return "unavailable";
		} finally {
			startupRecoveryWindow = void 0;
		}
	};
	const showPreHostSurface = () => {
		if (setupWizardWindow !== void 0) {
			setupWizardWindow.show();
			return true;
		}
		if (startupRecoveryWindow !== void 0) {
			startupRecoveryWindow.show();
			return true;
		}
		return false;
	};
	app.on("activate", () => {
		showPreHostSurface();
	});
	if (process.platform === "darwin") app.on("did-become-active", () => {
		showPreHostSurface();
	});
	app.on("second-instance", (_event, argv) => {
		if (isDesktopInstallerQuitRequest(argv, process.platform)) {
			requestQuit(0);
			return;
		}
		if (!showPreHostSurface()) runtime.show();
	});
	try {
		await app.whenReady();
		startupStage = "shell-environment";
		lifecycleRecorder.transitionStartupStage(startupStage);
		if (process.platform === "win32") app.setAppUserModelId("ai.deepseek.dsh.desktop");
		if (app.isPackaged && process.cwd() === "/") process.chdir(app.getPath("home"));
		const shellEnvironmentResolution = await resolveDesktopShellEnvironment({
			environment: process.env,
			home: app.getPath("home"),
			isPackaged: app.isPackaged,
			platform: process.platform
		});
		for (const [name, value] of Object.entries(shellEnvironmentResolution.updates)) process.env[name] = value;
		const homeDir = resolveDshHome();
		const projectionCacheRecovery = recoverOversizedSessionProjectionCache(homeDir);
		if (projectionCacheRecovery.status === "quarantined") {
			sessionProjectionCacheRecovery = projectionCacheRecovery;
			electronLogger.error(`${BIN_NAME}: quarantined oversized session projection cache (${String(projectionCacheRecovery.sizeBytes)} bytes) at ${projectionCacheRecovery.cachePath}; backup saved to ${projectionCacheRecovery.backupPath}`);
		}
		const windowsVolumeConcerns = diagnoseWindowsVolumes(process.platform, [
			{
				label: "application install",
				path: process.execPath
			},
			{
				label: "desktop user data",
				path: app.getPath("userData")
			},
			{
				label: "DSH home",
				path: homeDir
			}
		]);
		warnWindowsVolumeConcerns(electronLogger, windowsVolumeConcerns);
		installFailLoud(BIN_NAME, {
			on: (event, handler) => process.on(event, handler),
			off: (event, handler) => process.off(event, handler),
			stderr: electronLogger,
			exit: finalExit
		}, async () => {
			await generation.release();
		});
		startupStage = "runtime-bootstrap";
		lifecycleRecorder.transitionStartupStage(startupStage);
		const environment = loadLayeredEnv(BIN_NAME, process.cwd());
		const electronVersion = process.versions.electron;
		if (electronVersion === void 0) throw new Error(`${BIN_NAME}: plugin runtime requires the Electron runtime version`);
		const pnpmBinPath = packagedDependencyPath(import.meta.url, "pnpm/bin/pnpm.mjs");
		const pnpmRuntime = installDesktopPnpmRuntime({
			platform: process.platform,
			appExecutable: process.execPath,
			pnpmBinPath,
			electronVersion,
			stateDir: join(app.getPath("userData"), "runtime-commands"),
			environment: process.env
		});
		const dshBootstrapPath = fileURLToPath(new URL("./desktop-cli.js", import.meta.url));
		const releasePnpmRuntime = generation.own(() => {
			pnpmRuntime.dispose();
		});
		const selectionStatePath = join(app.getPath("userData"), "profile-selection", "state.json");
		const pluginManagementStatePath = join(app.getPath("userData"), "plugin-management", "state.json");
		startupStage = "profile-selection";
		lifecycleRecorder.transitionStartupStage(startupStage);
		const activeProfileName = beginDesktopProfileStartup(selectionStatePath, homeDir).profileName;
		const activeProfileDir = resolveProfileDir(activeProfileName, homeDir);
		runtime.configureTerminal({
			profileName: activeProfileName,
			profileDir: activeProfileDir,
			homeDir
		});
		recoveryTerminalAvailable = true;
		const recoveryProfileToken = randomUUID();
		startupRecoveryProfileActions = {
			token: recoveryProfileToken,
			list: () => listDesktopProfiles(homeDir).map((profile) => ({
				name: profile.name,
				current: profile.name === activeProfileName,
				selectable: profile.webCapable && profile.problem === void 0
			})),
			switchProfile: (name, token) => {
				if (token !== recoveryProfileToken || profileRecoveryActionUsed) throw new Error(`${BIN_NAME}: the Profile recovery action is no longer valid`);
				profileRecoveryActionUsed = true;
				assertDesktopProfileName(name);
				if (readDesktopProfileState(selectionStatePath).active !== activeProfileName) throw new Error(`${BIN_NAME}: active Profile changed before recovery`);
				const target = listDesktopProfiles(homeDir).find((profile) => profile.name === name);
				if (target === void 0 || !target.webCapable || target.problem !== void 0) throw new Error(`${BIN_NAME}: Profile ${JSON.stringify(name)} is unavailable`);
				selectDesktopProfile(selectionStatePath, homeDir, name);
			},
			openCreator: () => {
				runtime.openProfileCreateWindow({ onSubmit: async (name) => {
					assertDesktopProfileName(name);
					if (readDesktopProfileState(selectionStatePath).active !== activeProfileName) throw new Error(`${BIN_NAME}: active Profile changed before recovery`);
					createDesktopWebProfile(homeDir, name);
					selectDesktopProfile(selectionStatePath, homeDir, name);
				} });
			}
		};
		try {
			profileCheckpoint = new DesktopProfileCheckpoint({
				userDataDir: app.getPath("userData"),
				profileDir: activeProfileDir,
				homeDir,
				profileName: activeProfileName,
				provider: "desktop-profile",
				appVersion
			});
		} catch (cause) {
			electronLogger.error(`${BIN_NAME}: healthy profile checkpoints are unavailable: ${cause instanceof Error ? cause.message : String(cause)}`);
		}
		startupRecoveryConfigurationPaths = {
			settingsDocument: join(homeDir, "settings.yaml"),
			profilePatch: join(activeProfileDir, PROFILE_PATCH_FILENAME),
			profileManifest: join(activeProfileDir, "package.json"),
			profileDirectory: activeProfileDir
		};
		if (profileCheckpoint !== void 0) startupRecoveryController = new DesktopStartupRecoveryController({
			pluginState: {
				profileName: activeProfileName,
				homeDir,
				statePath: pluginManagementStatePath
			},
			generationId,
			currentGeneration: () => ({
				profileName: readDesktopProfileState(selectionStatePath).active,
				generationId
			}),
			uninstallPlugin: async (packageName) => {
				try {
					await removeRecoveryPlugin({
						appExecutable: process.execPath,
						dshBootstrapPath,
						profileName: activeProfileName,
						profileDir: activeProfileDir,
						homeDir,
						nodeBinDir: pnpmRuntime.nodeBinDir,
						nodeShimPath: pnpmRuntime.nodeShimPath,
						pnpmBinDir: pnpmRuntime.pathDir,
						electronVersion,
						packageName
					});
				} catch (cause) {
					const detail = maskSecrets(formatRecoveryPluginRemoveFailure(cause));
					electronLogger.error(`${BIN_NAME}: recovery plugin uninstall failed:\n${detail}`);
					throw new DesktopStartupRecoveryControllerError("operation-failed", "The plugin could not be removed from the current Profile.", {
						operationStage: "plugin-change",
						diagnosticDetail: detail
					});
				}
			},
			checkpoints: profileCheckpoint,
			openCheckpointDirectory: async (path) => {
				const error = await shell.openPath(path);
				if (error.length > 0) throw new Error(error);
			},
			afterCheckpointRestore: async (result) => {
				if (!result.dependencyMaterializationRequired) return;
				try {
					await materializeProfile({
						appExecutable: process.execPath,
						clearEnvironmentPath: pnpmRuntime.clearEnvironmentPath,
						pnpmBinPath,
						nodeBinDir: pnpmRuntime.nodeBinDir,
						nodeShimPath: pnpmRuntime.nodeShimPath,
						homeDir,
						profileDir: activeProfileDir,
						electronVersion
					});
				} catch (cause) {
					const detail = maskSecrets(formatProfileMaterializationFailure(cause));
					electronLogger.error(`${BIN_NAME}: checkpoint dependency materialization failed:\n${detail}`);
					throw new DesktopStartupRecoveryControllerError("operation-failed", "The checkpoint files were restored, but Profile dependencies could not be rebuilt.", {
						operationStage: "dependency-materialization",
						diagnosticDetail: detail
					});
				}
			}
		});
		if (recoveryModeRequested) {
			const recoveryResult = await openStartupRecoveryWindow("Recovery mode was requested from the Desktop restart menu.", startupRecoveryController, true);
			startupRecoveryController?.dispose();
			startupRecoveryController = void 0;
			if (recoveryResult === "restart") nativeExit.requestRelaunch();
			await shutdown.request(recoveryResult === "restart" ? 0 : 1);
			return;
		}
		startupStage = "profile-composition";
		lifecycleRecorder.transitionStartupStage(startupStage);
		const marketUserDataDir = app.getPath("userData");
		let marketSelection = readDesktopMarketStateForUserData(marketUserDataDir);
		const preparationHooks = { onSettingsDocumentResolved: (settingsDocument) => {
			if (startupRecoveryConfigurationPaths === void 0) return;
			startupRecoveryConfigurationPaths = {
				...startupRecoveryConfigurationPaths,
				settingsDocument
			};
		} };
		let prepared = prepareDesktopProfile(process.env.DSH_TELEMETRY_DISABLED, homeDir, process.platform, activeProfileName, pluginManagementStatePath, marketSelection, preparationHooks);
		if (await migrateDesktopBrowserAccessSettings(prepared.settingsDocument)) prepared = prepareDesktopProfile(process.env.DSH_TELEMETRY_DISABLED, homeDir, process.platform, activeProfileName, pluginManagementStatePath, marketSelection, preparationHooks);
		if (readDesktopSetupWizardState(marketUserDataDir, prepared.profile.dir) === void 0) {
			const setupSettings = readDesktopSetupWizardSettings(prepared.settingsDocument);
			setupWizardWindow = new DesktopSetupWizardWindow({
				locale: desktopLocaleFromLanguageTag(app.getLocale()),
				input: {
					profileName: activeProfileName,
					platform: runtime.platform,
					micaSupported: process.platform === "win32" && windowsSupportsMica(runtime.windowsBuild),
					...setupSettings,
					market: marketSelection.requested
				}
			});
			let setupResult;
			try {
				setupResult = await setupWizardWindow.run();
			} finally {
				setupWizardWindow = void 0;
			}
			if (setupResult.action === "quit") {
				startupRecoveryController?.dispose();
				startupRecoveryController = void 0;
				await shutdown.request(0);
				return;
			}
			if (setupResult.action === "skip") await completeOrSkipDesktopSetupWizard(marketUserDataDir, prepared.profile.dir, "skipped");
			else {
				await updateDesktopSetupWizardSettings(prepared.settingsDocument, {
					mode: setupResult.selection.mode,
					macosMaterial: setupResult.selection.macosMaterial,
					windowsMaterial: setupResult.selection.windowsMaterial,
					openBrowser: setupResult.selection.openBrowser,
					networkExposure: setupResult.selection.networkExposure,
					notifications: setupResult.selection.notifications
				});
				await selectDesktopMarketProvider(marketUserDataDir, setupResult.selection.market);
				marketSelection = readDesktopMarketStateForUserData(marketUserDataDir);
				prepared = prepareDesktopProfile(process.env.DSH_TELEMETRY_DISABLED, homeDir, process.platform, activeProfileName, pluginManagementStatePath, marketSelection, preparationHooks);
				await completeOrSkipDesktopSetupWizard(marketUserDataDir, prepared.profile.dir, "completed");
			}
		}
		if (profileCheckpoint === void 0) try {
			profileCheckpoint = new DesktopProfileCheckpoint({
				userDataDir: app.getPath("userData"),
				profileDir: prepared.profile.dir,
				homeDir,
				profileName: activeProfileName,
				provider: "desktop-profile",
				appVersion
			});
		} catch (cause) {
			electronLogger.error(`${BIN_NAME}: healthy profile checkpoints remain unavailable: ${cause instanceof Error ? cause.message : String(cause)}`);
		}
		startupStage = "runtime-bootstrap";
		lifecycleRecorder.transitionStartupStage(startupStage);
		const dshRuntime = process.platform === "win32" ? installDesktopDshRuntime({
			platform: process.platform,
			appExecutable: process.execPath,
			dshBootstrapPath,
			profileName: activeProfileName,
			homeDir,
			stateDir: join(app.getPath("userData"), "host-commands", activeProfileName),
			environment: process.env
		}) : void 0;
		const releaseDshRuntime = generation.own(() => {
			dshRuntime?.dispose();
		});
		if (prepared.requiresDependencyMigration) {
			electronLogger.error(`${BIN_NAME}: migrating legacy Profile dependency layout with packaged pnpm`);
			try {
				await materializeProfile({
					appExecutable: process.execPath,
					clearEnvironmentPath: pnpmRuntime.clearEnvironmentPath,
					pnpmBinPath,
					nodeBinDir: pnpmRuntime.nodeBinDir,
					nodeShimPath: pnpmRuntime.nodeShimPath,
					homeDir,
					profileDir: prepared.profile.dir,
					electronVersion,
					updateLockfile: true
				});
				prepared = prepareDesktopProfile(process.env.DSH_TELEMETRY_DISABLED, homeDir, process.platform, activeProfileName, pluginManagementStatePath, marketSelection, preparationHooks);
				if (prepared.requiresDependencyMigration) throw new Error(`${BIN_NAME}: packaged pnpm did not produce compatible Profile dependency metadata`);
			} catch (migrationCause) {
				const detail = migrationCause instanceof ProfileMaterializationError ? migrationCause.result?.stderr || migrationCause.message : migrationCause instanceof Error ? migrationCause.message : String(migrationCause);
				throw new Error(`${BIN_NAME}: Profile dependency migration failed: ${maskSecrets(detail)}`);
			}
		}
		if (prepared.marketFailure !== void 0) electronLogger.error(`${BIN_NAME}: requested Market provider ${prepared.market.requested} was disabled for this generation: ${prepared.marketFailure}`);
		const browserAccess = createDesktopBrowserAccess(prepared.mode === "compatibility" && prepared.openBrowser);
		const desktopPnpmBootstrap = {
			activeProfileName,
			activeProfileDir: prepared.profile.dir,
			homeDir,
			appExecutable: process.execPath,
			pnpmBinPath,
			electronVersion,
			nodeBinDir: pnpmRuntime.nodeBinDir,
			nodeShimPath: pnpmRuntime.nodeShimPath,
			clearEnvironmentPath: pnpmRuntime.clearEnvironmentPath,
			dshBootstrapPath
		};
		startupStage = "host-boot";
		lifecycleRecorder.transitionStartupStage(startupStage);
		const releasePackageResolver = installProfilePackageResolver(prepared.bareModuleBaseUrl);
		const ctx = await boot(BIN_NAME, prepared.rootConfig, prepared.patches, async (hostCtx) => {
			generation.bindHost(hostCtx);
			hostCtx.effect(() => releasePnpmRuntime, "dsh-plugin-desktop: packaged pnpm runtime PATH");
			if (dshRuntime !== void 0) hostCtx.effect(() => releaseDshRuntime, "dsh-plugin-desktop: packaged dsh runtime PATH");
			hostCtx.effect(() => releasePackageResolver, "dsh-plugin-desktop: profile package resolution");
			hostCtx.provide(DSH_LAUNCH_ENVIRONMENT_KEY, environment);
			hostCtx.provide("desktopBrowserAccess", browserAccess);
			hostCtx.provide("desktopRuntime", runtime);
			hostCtx.provide("desktopPnpmBootstrap", desktopPnpmBootstrap);
			await hostCtx.plugin(DesktopActionsService, {
				openTerminal: () => {
					runtime.openTerminal();
				},
				requestRestart: () => runtime.requestRestart()
			});
			if (prepared.market.effective === "community-market") await hostCtx.plugin(DesktopPluginsService, {
				profileName: activeProfileName,
				homeDir,
				statePath: pluginManagementStatePath,
				installAnchor: desktopInstallAnchor()
			});
			if (logSink !== void 0) {
				fileExporter = new FileExporter(logSink);
				hostCtx.logger.exporter(fileExporter);
			}
			await hostCtx.plugin(DesktopProfileService, {
				current: {
					name: activeProfileName,
					dir: prepared.profile.dir
				},
				create: (name) => createDesktopWebProfile(homeDir, name),
				list: () => listDesktopProfiles(homeDir),
				canDelete: (name) => canDeleteDesktopProfile({
					home: homeDir,
					selectionStatePath,
					currentProfileName: activeProfileName
				}, name),
				delete: (name) => deleteDesktopProfile({
					home: homeDir,
					selectionStatePath,
					currentProfileName: activeProfileName,
					clearDisabledState: () => clearDesktopProfilePluginState(pluginManagementStatePath, name),
					clearCheckpoint: async () => {
						const profileDir = resolveProfileDir(name, homeDir);
						clearDesktopProfileCheckpoint(app.getPath("userData"), profileDir);
						await clearDesktopSetupWizardState(app.getPath("userData"), profileDir);
					}
				}, name),
				persistSelection: (name) => {
					selectDesktopProfile(selectionStatePath, homeDir, name);
				},
				requestRestart: () => runtime.requestRestart()
			});
			let pendingSettingsRestart;
			const scheduleSettingsRestart = () => {
				pendingSettingsRestart ??= setImmediate(() => {
					pendingSettingsRestart = void 0;
					runtime.requestRestart().catch((cause) => {
						hostCtx.logger.error(`${BIN_NAME}: failed to restart after Desktop setting change: ${cause instanceof Error ? cause.message : String(cause)}`);
					});
				});
			};
			hostCtx.effect(() => () => {
				if (pendingSettingsRestart !== void 0) clearImmediate(pendingSettingsRestart);
				pendingSettingsRestart = void 0;
			}, "dsh-plugin-desktop: pending Desktop settings restart");
			const readMarket = () => desktopMarketSnapshotWithEffective(readDesktopMarketStateForUserData(marketUserDataDir), prepared.market.effective);
			hostCtx.provide("desktopSettingsController", new DesktopSettingsController({
				profiles: hostCtx.desktopProfiles,
				persistProfileSelection: (name) => {
					selectDesktopProfile(selectionStatePath, homeDir, name);
				},
				readMarket,
				readWeb: () => {
					const webRuntime = hostCtx.get("webRuntime");
					if (webRuntime === void 0) throw new Error(`${BIN_NAME}: Web runtime is unavailable`);
					return {
						localUrl: desktopLoopbackBrowserUrl(hostCtx.webServer.port),
						lanUrls: desktopLanBrowserUrls(hostCtx.webServer.port, webRuntime.lanAddresses)
					};
				},
				selectMarket: async (provider) => desktopMarketSnapshotWithEffective(await selectDesktopMarketProvider(marketUserDataDir, provider), prepared.market.effective),
				scheduleRestart: scheduleSettingsRestart,
				scheduleRecoveryRestart: () => {
					runtime.requestRecoveryRestart().catch((cause) => {
						hostCtx.logger.error(`${BIN_NAME}: failed to restart in recovery mode: ${cause instanceof Error ? cause.message : String(cause)}`);
					});
				},
				openTerminal: () => {
					runtime.openTerminal();
				},
				reloadRenderer: () => {
					runtime.reloadRenderer();
				},
				toggleDeveloperTools: () => {
					runtime.toggleDeveloperTools();
				},
				exportDiagnostics: () => runtime.exportDiagnostics(),
				openProfileCreator: () => {
					runtime.openProfileCreateWindow({ onSubmit: async (name) => {
						hostCtx.desktopProfiles.create(name);
						await hostCtx.desktopProfiles.select(name);
					} });
				}
			}));
			provideCmdline(hostCtx, {
				args: ["--port", String(prepared.port)],
				exit: requestQuit
			});
		}, prepared.bareModuleBaseUrl).catch((cause) => {
			releasePackageResolver();
			throw cause;
		});
		generation.bindHost(ctx);
		fileExporter?.setThreshold(ctx.settings.get(DESKTOP_SETTINGS_NAMESPACE)?.logLevel ?? "info");
		ctx.on("settings/updated", (namespace, next) => {
			if (namespace !== DESKTOP_SETTINGS_NAMESPACE) return;
			fileExporter?.setThreshold(next.logLevel);
		});
		startupStage = "renderer-startup";
		lifecycleRecorder.transitionStartupStage(startupStage);
		lifecycleRecorder.startRendererBoot();
		const rendererBoot = runtime.beginRendererBootMonitoring({ commitHealthy: async () => {
			lifecycleRecorder.finishRendererBoot({ status: "healthy" }, "renderer-failed");
			startupStage = "health-commit";
			lifecycleRecorder.transitionStartupStage(startupStage);
			try {
				profileCheckpoint?.captureHealthy();
			} catch (cause) {
				electronLogger.error(`${BIN_NAME}: failed to checkpoint the healthy profile configuration: ${cause instanceof Error ? cause.message : String(cause)}`);
			}
		} });
		const [, rendererVerdict] = await Promise.all([runtime.mountScheduled(), rendererBoot]);
		const rendererReport = rendererVerdict.report;
		if ("failureReason" in rendererVerdict) throw new RendererStartupFailure(rendererVerdict.failureReason, rendererVerdict.report);
		lifecycleRecorder.completeStartup(startupStage, rendererReport);
		notifySkippedOptionalEntries(runtime, electronLogger, prepared.skippedOptionalEntries);
		notifyWindowsVolumeConcerns(runtime, electronLogger, windowsVolumeConcerns);
		if (sessionProjectionCacheRecovery !== void 0) notifySessionProjectionCacheRecovery(runtime, electronLogger, sessionProjectionCacheRecovery);
	} catch (cause) {
		runtime.stopRendererBootMonitoring();
		lifecycleRecorder.failRendererBootIfPending(lifecycleRendererFailureReason(runtime.rendererBootFailureReason));
		lifecycleRecorder.failStartup(startupStage, lifecycleStartupFailureReason(cause, runtime));
		electronLogger.errorCause(cause);
		let exitCode = 1;
		const failureRoute = routeDesktopStartupFailure({
			appReady: app.isReady(),
			stage: startupStage
		});
		const recoveryActionsSafe = await generation.quiesceForRecovery();
		if (failureRoute === "startup-recovery") {
			if (await openStartupRecoveryWindow(cause instanceof Error ? cause.message : String(cause), recoveryActionsSafe ? startupRecoveryController : void 0) === "restart") {
				nativeExit.requestRelaunch();
				exitCode = 0;
			}
		}
		startupRecoveryController?.dispose();
		await shutdown.request(exitCode);
	}
}
async function run() {
	app.setName(PRODUCT_NAME);
	if (process.argv.includes("--export-diagnostics")) {
		try {
			await app.whenReady();
			const path = await exportDesktopDiagnostics(app.getPath("userData"), {
				appVersion: desktopProductVersion(),
				crashDumpsDir: app.getPath("crashDumps")
			});
			await new Promise((resolve, reject) => {
				process.stdout.write(`${path}\n`, (error) => {
					if (error === void 0 || error === null) resolve();
					else reject(error);
				});
			});
			app.exit(0);
		} catch (cause) {
			const message = `dsh-plugin-desktop: failed to export diagnostics: ${cause instanceof Error ? cause.stack ?? cause.message : String(cause)}\n`;
			await new Promise((resolve) => {
				process.stderr.write(message, () => {
					resolve();
				});
			});
			app.exit(1);
		}
		return;
	}
	await start();
}
/** Last-resort branch for launcher failures that happen before start's owned coordinator exists. */
async function handleFatalLauncherFailure(cause) {
	const detail = maskSecrets(cause instanceof Error ? cause.stack ?? cause.message : String(cause));
	process.stderr.write(`${BIN_NAME}: fatal launcher failure: ${detail}\n`);
	if (!app.isReady()) {
		app.exit(1);
		return;
	}
	try {
		if (await new DesktopStartupRecoveryWindow({
			locale: desktopLocaleFromLanguageTag(app.getLocale()),
			failureStage: "electron-ready",
			failureDetail: detail,
			exportDiagnostics: async (signal) => await exportDesktopDiagnostics(app.getPath("userData"), {
				appVersion: desktopProductVersion(),
				crashDumpsDir: app.getPath("crashDumps"),
				signal
			})
		}).run() === "restart") {
			app.relaunch();
			app.exit(0);
		} else app.exit(1);
	} catch (windowCause) {
		process.stderr.write(`${BIN_NAME}: fatal recovery window failure: ${maskSecrets(windowCause instanceof Error ? windowCause.stack ?? windowCause.message : String(windowCause))}\n`);
		app.exit(1);
	}
}
run().catch(async (cause) => {
	await handleFatalLauncherFailure(cause);
});
//#endregion
export {};

//# sourceMappingURL=main.js.ma