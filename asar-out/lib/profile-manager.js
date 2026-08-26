pimport { randomUUID } from "node:crypto";
import { chmodSync, closeSync, existsSync, fstatSync, lstatSync, mkdirSync, openSync, readFileSync, readdirSync, renameSync, rmSync, unlinkSync, writeFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { PROFILE_TEMPLATES, initProfile, readProfileManifest, resolveProfileDir, writeProfileManifest } from "@deepseek-ai/dsh-app-boot";
//#region src/profile-manager.ts
/** Desktop-owned profile discovery and restart-safe selection state. */
const BIN_NAME = "dsh-plugin-desktop";
const DEFAULT_PROFILE_NAME = "desktop";
const BASE_BUNDLE_NAME = "@deepseek-ai/dsh-base";
const WEB_BUNDLE_NAME = "@deepseek-ai/dsh-web-app";
const DESKTOP_BUNDLE_NAME = "dsh-plugin-desktop";
const PROFILE_MANIFEST_FILENAME = "package.json";
const STATE_VERSION = 2;
const MAX_STATE_BYTES = 4 * 1024;
const STATE_DIRECTORY_MODE = 448;
const STATE_FILE_MODE = 384;
const MAX_PROFILE_NAME_BYTES = 255;
const INTERNAL_PROFILE_STAGING_PATTERN = /^\..+\.(?:creating|deleting|incomplete)-\d+-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
/** Internal marker separating invalid contents from filesystem access failures. */
var InvalidDesktopProfileStateError = class extends Error {};
/** Return a fresh default so callers cannot mutate shared state. */
function defaultState() {
	return {
		version: STATE_VERSION,
		active: DEFAULT_PROFILE_NAME
	};
}
/** Reject profile names that cannot safely cross the persisted state boundary. */
function assertDesktopProfileName(name) {
	if (typeof name !== "string" || name.length === 0 || name.includes("/") || name.includes("\\") || name === "." || name === ".." || name === "node_modules" || Buffer.byteLength(name, "utf8") > MAX_PROFILE_NAME_BYTES || INTERNAL_PROFILE_STAGING_PATTERN.test(name) || /[\0-\x1f\x7f-\x9f]/.test(name) || /[<>:"|?*]/.test(name) || /[. ]$/.test(name) || /^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$/i.test(name)) throw new Error(`${BIN_NAME}: invalid desktop profile name ${JSON.stringify(name)}`);
	resolveProfileDir(name, "/");
}
/** Validate a manifest bundle list without trusting arbitrary JSON values. */
function manifestBundles(manifest) {
	const value = (manifest.dsh?.profile)?.bundles;
	if (value === void 0) return [];
	if (!Array.isArray(value) || value.some((bundle) => typeof bundle !== "string")) throw new Error("dsh.profile.bundles must be an array of package names");
	return [...value];
}
/** Describe an existing manifest while retaining its failure as list metadata. */
function existingProfile(name, home) {
	const dir = resolveProfileDir(name, home);
	try {
		const bundles = manifestBundles(readProfileManifest(BIN_NAME, dir));
		const desktopBundleIndex = bundles.indexOf(DESKTOP_BUNDLE_NAME);
		const problem = name !== DEFAULT_PROFILE_NAME && desktopBundleIndex !== -1 ? `${DESKTOP_BUNDLE_NAME} is launcher-owned and must not appear in dsh.profile.bundles` : void 0;
		const baseBundleIndex = bundles.indexOf(BASE_BUNDLE_NAME);
		const webBundleIndex = bundles.indexOf(WEB_BUNDLE_NAME);
		return {
			name,
			dir,
			exists: true,
			bundles,
			webCapable: problem === void 0 && (name === DEFAULT_PROFILE_NAME || baseBundleIndex !== -1 && webBundleIndex > baseBundleIndex),
			...problem === void 0 ? {} : { problem }
		};
	} catch (cause) {
		return {
			name,
			dir,
			exists: true,
			bundles: [],
			webCapable: false,
			problem: cause instanceof Error ? cause.message : String(cause)
		};
	}
}
/**
* Create a safe Web profile using only the shipped template.
*
* The profile is initialized in a sibling staging directory and published with
* one rename, so a failed initialization never leaves a partially initialized
* target visible to discovery.
*/
function createDesktopWebProfile(home, name) {
	assertDesktopProfileName(name);
	const template = PROFILE_TEMPLATES.web;
	if (template === void 0) throw new Error(`${BIN_NAME}: installed dsh-app-boot has no web profile template`);
	const target = resolveProfileDir(name, home);
	const profilesDir = dirname(target);
	mkdirSync(profilesDir, { recursive: true });
	try {
		lstatSync(target);
		throw new Error(`${BIN_NAME}: profile ${JSON.stringify(name)} already exists`);
	} catch (cause) {
		if (cause.code !== "ENOENT") throw cause;
	}
	const staging = join(profilesDir, `.${basename(target)}.creating-${process.pid}-${randomUUID()}`);
	try {
		initProfile(staging, [...template]);
		writeProfileManifest(staging, {
			...readProfileManifest(BIN_NAME, staging),
			name: `dsh-profile-${name}`
		});
		try {
			lstatSync(target);
			throw new Error(`${BIN_NAME}: profile ${JSON.stringify(name)} already exists`);
		} catch (cause) {
			if (cause.code !== "ENOENT") throw cause;
		}
		renameSync(staging, target);
	} catch (cause) {
		rmSync(staging, {
			recursive: true,
			force: true
		});
		throw cause;
	}
	return existingProfile(name, home);
}
/**
* Publish the real default Profile while preserving an interrupted, incomplete
* directory under an internal sibling name. Ordinary files and symlinks fail
* closed instead of being replaced.
*/
function materializeDefaultDesktopProfile(home) {
	const target = resolveProfileDir(DEFAULT_PROFILE_NAME, home);
	if (existsSync(join(target, PROFILE_MANIFEST_FILENAME))) return existingProfile(DEFAULT_PROFILE_NAME, home);
	let incomplete;
	try {
		const item = lstatSync(target);
		if (!item.isDirectory() || item.isSymbolicLink()) throw new Error(`${BIN_NAME}: default profile path is not a real directory`);
		incomplete = join(dirname(target), `.${basename(target)}.incomplete-${process.pid}-${randomUUID()}`);
		renameSync(target, incomplete);
	} catch (cause) {
		if (cause.code !== "ENOENT") throw cause;
	}
	try {
		return createDesktopWebProfile(home, DEFAULT_PROFILE_NAME);
	} catch (cause) {
		if (incomplete !== void 0) try {
			lstatSync(target);
		} catch (targetCause) {
			if (targetCause.code === "ENOENT") try {
				renameSync(incomplete, target);
			} catch {}
		}
		throw cause;
	}
}
/** Deterministic profile order with the actual Desktop profile first. */
function compareProfiles(left, right) {
	const priority = (name) => name === DEFAULT_PROFILE_NAME ? 0 : 1;
	const difference = priority(left.name) - priority(right.name);
	if (difference !== 0) return difference;
	return left.name < right.name ? -1 : left.name > right.name ? 1 : 0;
}
/**
* List profile manifests without initializing or modifying any profile.
* @param home - Harness home containing the shared profile directory.
* @returns only profiles whose manifests currently exist on disk.
*/
function listDesktopProfiles(home) {
	const profilesDir = join(home, "profiles");
	const summaries = /* @__PURE__ */ new Map();
	try {
		for (const entry of readdirSync(profilesDir, { withFileTypes: true })) {
			if (INTERNAL_PROFILE_STAGING_PATTERN.test(entry.name)) continue;
			if (entry.name === "node_modules" || !entry.isDirectory() && !entry.isSymbolicLink()) continue;
			try {
				assertDesktopProfileName(entry.name);
			} catch {
				continue;
			}
			if (!existsSync(join(resolveProfileDir(entry.name, home), PROFILE_MANIFEST_FILENAME))) continue;
			summaries.set(entry.name, existingProfile(entry.name, home));
		}
	} catch (cause) {
		if (cause.code !== "ENOENT") throw cause;
	}
	return [...summaries.values()].sort(compareProfiles);
}
/** Validate one selected profile against the exact discovery result. */
function selectableProfile(home, name) {
	assertDesktopProfileName(name);
	const summary = listDesktopProfiles(home).find((profile) => profile.name === name);
	if (summary === void 0) throw new Error(`${BIN_NAME}: profile ${JSON.stringify(name)} does not exist`);
	if (summary.problem !== void 0) throw new Error(`${BIN_NAME}: profile ${JSON.stringify(name)} cannot be selected: ${summary.problem}`);
	if (!summary.webCapable) throw new Error(`${BIN_NAME}: profile ${JSON.stringify(name)} must directly include ${BASE_BUNDLE_NAME} before ${WEB_BUNDLE_NAME}`);
	return summary;
}
function deletionTarget(options, name) {
	assertDesktopProfileName(name);
	if (name === options.currentProfileName) throw new Error(`${BIN_NAME}: current profile ${JSON.stringify(name)} cannot be deleted`);
	const target = resolveProfileDir(name, options.home);
	let item;
	try {
		item = lstatSync(target);
	} catch (cause) {
		if (cause.code === "ENOENT") throw new Error(`${BIN_NAME}: profile ${JSON.stringify(name)} does not exist`);
		throw cause;
	}
	if (!item.isDirectory() || item.isSymbolicLink()) throw new Error(`${BIN_NAME}: profile ${JSON.stringify(name)} is not a real directory`);
	let manifest;
	try {
		manifest = lstatSync(join(target, PROFILE_MANIFEST_FILENAME));
	} catch (cause) {
		if (cause.code === "ENOENT") throw new Error(`${BIN_NAME}: profile ${JSON.stringify(name)} does not exist`);
		throw cause;
	}
	if (!manifest.isFile() || manifest.isSymbolicLink()) throw new Error(`${BIN_NAME}: profile ${JSON.stringify(name)} has an unsafe manifest`);
	return target;
}
/** Return whether a profile is eligible for deletion using current selection state. */
function canDeleteDesktopProfile(options, name) {
	try {
		deletionTarget(options, name);
		return true;
	} catch {
		return false;
	}
}
/**
* Remove one inactive user profile through a same-filesystem staging rename.
* Selection and filesystem checks are repeated immediately before the rename.
*/
async function deleteDesktopProfile(options, name) {
	const target = deletionTarget(options, name);
	if (deletionTarget(options, name) !== target) throw new Error(`${BIN_NAME}: profile deletion target changed during validation`);
	const parent = dirname(target);
	const parentInfo = lstatSync(parent);
	if (!parentInfo.isDirectory() || parentInfo.isSymbolicLink()) throw new Error(`${BIN_NAME}: profile directory parent is not a real directory`);
	const staging = join(parent, `.${basename(target)}.deleting-${process.pid}-${randomUUID()}`);
	renameSync(target, staging);
	try {
		await options.clearDisabledState?.();
		await options.clearCheckpoint?.();
		const stagedInfo = lstatSync(staging);
		if (!stagedInfo.isDirectory() || stagedInfo.isSymbolicLink()) throw new Error(`${BIN_NAME}: profile deletion staging entry is unsafe`);
		rmSync(staging, {
			recursive: true,
			force: false
		});
	} catch (cause) {
		try {
			renameSync(staging, target);
		} catch {}
		throw cause;
	}
}
/** Parse the complete state document and reject unknown format versions. */
function parseState(text) {
	const value = JSON.parse(text);
	if (value === null || typeof value !== "object" || Array.isArray(value)) throw new Error("selection state must be a JSON object");
	const state = value;
	if (state.version !== STATE_VERSION) throw new Error(`selection state version must be ${STATE_VERSION}`);
	if (typeof state.active !== "string") throw new Error("selection state active profile must be a string");
	assertDesktopProfileName(state.active);
	return {
		version: STATE_VERSION,
		active: state.active
	};
}
/** Read at most the private state format's maximum encoded size. */
function readStateText(statePath) {
	const descriptor = openSync(statePath, "r");
	try {
		if (fstatSync(descriptor).size > MAX_STATE_BYTES) throw new InvalidDesktopProfileStateError(`selection state exceeds ${MAX_STATE_BYTES} bytes`);
		return readFileSync(descriptor, "utf8");
	} finally {
		closeSync(descriptor);
	}
}
/** Read state with enough metadata for startup recovery. */
function loadState(statePath) {
	let text;
	try {
		if (lstatSync(statePath).isSymbolicLink()) return {
			state: defaultState(),
			recovered: true
		};
		text = readStateText(statePath);
	} catch (cause) {
		if (cause.code === "ENOENT") return {
			state: defaultState(),
			recovered: false
		};
		if (cause instanceof InvalidDesktopProfileStateError) return {
			state: defaultState(),
			recovered: true
		};
		throw cause;
	}
	try {
		return {
			state: parseState(text),
			recovered: false
		};
	} catch {
		return {
			state: defaultState(),
			recovered: true
		};
	}
}
/** Remove an uncommitted sibling without hiding unexpected filesystem failures. */
function unlinkTemporary(filename) {
	try {
		unlinkSync(filename);
	} catch (cause) {
		if (cause.code !== "ENOENT") throw cause;
	}
}
/** Atomically persist desktop-private state without following a target symlink. */
function writeState(statePath, state) {
	const stateDir = dirname(statePath);
	mkdirSync(stateDir, {
		recursive: true,
		mode: STATE_DIRECTORY_MODE
	});
	const directoryStat = lstatSync(stateDir);
	if (!directoryStat.isDirectory() || directoryStat.isSymbolicLink()) throw new Error(`${BIN_NAME}: profile selection state directory is not private: ${stateDir}`);
	chmodSync(stateDir, STATE_DIRECTORY_MODE);
	const temporary = join(stateDir, `.${basename(statePath)}.${process.pid}.${randomUUID()}.tmp`);
	try {
		writeFileSync(temporary, `${JSON.stringify(state, void 0, 2)}\n`, {
			encoding: "utf8",
			flag: "wx",
			mode: STATE_FILE_MODE
		});
		chmodSync(temporary, STATE_FILE_MODE);
		renameSync(temporary, statePath);
	} finally {
		unlinkTemporary(temporary);
	}
}
/**
* Read the selected profile, recovering malformed desktop-private state to desktop.
* @param statePath - desktop-owned state file outside the Harness profile tree.
* @returns validated selection state.
*/
function readDesktopProfileState(statePath) {
	return loadState(statePath).state;
}
/**
* Request a compatible profile for the next application restart.
* @param statePath - desktop-owned state file outside the Harness profile tree.
* @param home - Harness home used only for read-only profile discovery.
* @param name - profile selected by the user.
* @returns persisted active selection.
*/
function selectDesktopProfile(statePath, home, name) {
	selectableProfile(home, name);
	const next = {
		version: STATE_VERSION,
		active: name
	};
	writeState(statePath, next);
	return next;
}
/**
* Resolve the exact selected Profile. When no Profile manifests exist, create
* one real default Desktop Profile and recover selection to it. A missing
* selection is otherwise left for the Recovery window instead of being
* silently replaced while another Profile remains available.
* @param statePath - desktop-owned state file outside the Harness profile tree.
* @param home - Harness home used for discovery and zero-Profile default materialization.
* @returns profile decision persisted before profile preparation starts.
*/
function beginDesktopProfileStartup(statePath, home) {
	const loaded = loadState(statePath);
	const discovered = listDesktopProfiles(home);
	const noProfilesExist = discovered.length === 0;
	let current = loaded.state;
	let recoveredState = loaded.recovered;
	if ((current.active === DEFAULT_PROFILE_NAME || noProfilesExist) && !discovered.some((profile) => profile.name === DEFAULT_PROFILE_NAME)) materializeDefaultDesktopProfile(home);
	if (noProfilesExist && current.active !== DEFAULT_PROFILE_NAME) {
		current = defaultState();
		recoveredState = true;
	}
	selectableProfile(home, current.active);
	const next = {
		version: STATE_VERSION,
		active: current.active
	};
	writeState(statePath, next);
	return {
		profileName: current.active,
		state: next,
		recoveredState
	};
}
//#endregion
export { assertDesktopProfileName, beginDesktopProfileStartup, canDeleteDesktopProfile, createDesktopWebProfile, deleteDesktopProfile, listDesktopProfiles, readDesktopProfileState, selectDesktopProfile };

//# sourceMappingURL=profile-manager.js.ma