pimport { assertDesktopProfileName } from "./profile-manager.js";
import { t as packagedDependencyPath } from "./packaged-runtime-path-BeoaDxsK.js";
import { r as withoutForwardedDesktopPnpmPolicy } from "./pnpm-policy-Dj9BWmx3.js";
import { fileURLToPath, pathToFileURL } from "node:url";
//#region src/desktop-cli.ts
/** Private RunAsNode bootstrap for the packaged DeepSeek Harness CLI. */
const RUN_AS_NODE = "ELECTRON_RUN_AS_NODE";
const DEFAULT_PROFILE = "DSH_DESKTOP_DEFAULT_PROFILE";
const DSH_ENTRY_URL = pathToFileURL(packagedDependencyPath(import.meta.url, "@deepseek-ai/dsh/lib/bin.js")).href;
function clearElectronRunAsNode(environment) {
	for (const key of Object.keys(environment)) if (key.toUpperCase() === RUN_AS_NODE) delete environment[key];
}
function withDefaultDesktopProfile(argv, profileName) {
	assertDesktopProfileName(profileName);
	if (argv.some((argument) => argument === "--profile" || argument.startsWith("--profile="))) return [...argv];
	const first = argv[0];
	if (first === "web" || first === "--help" || first === "-h" || first === "--version" || first === "-V") return [...argv];
	if (first === "plugin") return [
		"plugin",
		"--profile",
		profileName,
		...argv.slice(1)
	];
	return [
		"--profile",
		profileName,
		...argv
	];
}
function takeDefaultProfile(environment) {
	let profileName;
	for (const key of Object.keys(environment)) {
		if (key.toUpperCase() !== DEFAULT_PROFILE) continue;
		const value = environment[key];
		if (value !== void 0 && profileName !== void 0 && value !== profileName) throw new Error("dsh-desktop: conflicting default profile environment values");
		profileName ??= value;
		delete environment[key];
	}
	return profileName;
}
/**
* Enter the packaged DSH CLI without any plugin-install transaction wrapper.
* Manual plugin commands and Market operations rely on unified checkpoints.
*/
async function runDesktopDshCli(environment = process.env, load = (url) => import(url), argv = process.argv) {
	const profileName = takeDefaultProfile(environment);
	clearElectronRunAsNode(environment);
	const selected = profileName === void 0 ? argv.slice(2) : withDefaultDesktopProfile(argv.slice(2), profileName);
	argv.splice(2, argv.length - 2, ...withoutForwardedDesktopPnpmPolicy(selected));
	await load(DSH_ENTRY_URL);
}
function isDirectExecution() {
	const entry = process.argv[1];
	return entry !== void 0 && fileURLToPath(import.meta.url) === entry;
}
if (isDirectExecution()) runDesktopDshCli().catch((cause) => {
	process.stderr.write(`dsh-desktop: failed to start packaged dsh: ${cause instanceof Error ? cause.stack ?? cause.message : String(cause)}\n`);
	process.exitCode = 1;
});
//#endregion
export { clearElectronRunAsNode, runDesktopDshCli, withDefaultDesktopProfile };

//# sourceMappingURL=desktop-cli.js.ma