pimport { release } from "node:os";
//#region src/window-material.ts
/** Cross-platform window-material preferences and Windows capability gates. */
const DEFAULT_MACOS_WINDOW_MATERIAL = "transparent";
const DEFAULT_WINDOWS_WINDOW_MATERIAL = "acrylic";
/** Extract the NT build number from a Windows `os.release()` value. */
function windowsBuildNumber(value = release()) {
	const match = /^(?:\d+\.){2}(\d+)(?:\.|$)/.exec(value);
	if (match === null) return void 0;
	const build = Number(match[1]);
	return Number.isSafeInteger(build) ? build : void 0;
}
function windowsSupportsAcrylic(build) {
	return build !== void 0 && build >= 17763;
}
function windowsSupportsRoundedCorners(build) {
	return build !== void 0 && build >= 22e3;
}
function windowsSupportsSystemBackdrop(build) {
	return build !== void 0 && build >= 22621;
}
function windowsSupportsMica(build) {
	return windowsSupportsSystemBackdrop(build);
}
/** Whether Acrylic must use the legacy transparent-window implementation. */
function windowsUsesLegacyAcrylic(build) {
	return windowsSupportsAcrylic(build) && !windowsSupportsRoundedCorners(build);
}
function parseMacosWindowMaterial(value) {
	if (value === void 0) return DEFAULT_MACOS_WINDOW_MATERIAL;
	if (value === "off" || value === "transparent") return value;
	throw new Error("dsh-desktop.macosMaterial must be \"off\" or \"transparent\"");
}
function parseWindowsWindowMaterial(value) {
	if (value === void 0) return DEFAULT_WINDOWS_WINDOW_MATERIAL;
	if (value === "off" || value === "acrylic" || value === "mica") return value;
	throw new Error("dsh-desktop.windowsMaterial must be \"off\", \"acrylic\", or \"mica\"");
}
/** Resolve the actual generation material without making settings non-portable. */
function effectiveDesktopWindowMaterial(mode, platform, macosMaterial, windowsMaterial, windowsBuild) {
	if (platform === "linux") return "off";
	if (platform === "darwin") return macosMaterial;
	if (windowsMaterial === "mica" && !windowsSupportsSystemBackdrop(windowsBuild)) return windowsUsesLegacyAcrylic(windowsBuild) ? "acrylic" : "off";
	if (windowsMaterial === "acrylic") return windowsSupportsSystemBackdrop(windowsBuild) || windowsUsesLegacyAcrylic(windowsBuild) ? "acrylic" : "off";
	return windowsMaterial;
}
//#endregion
export { parseWindowsWindowMaterial as a, windowsSupportsSystemBackdrop as c, parseMacosWindowMaterial as i, windowsUsesLegacyAcrylic as l, DEFAULT_WINDOWS_WINDOW_MATERIAL as n, windowsBuildNumber as o, effectiveDesktopWindowMaterial as r, windowsSupportsMica as s, DEFAULT_MACOS_WINDOW_MATERIAL as t };

//# sourceMappingURL=window-material-0cOktjGz.js.ma