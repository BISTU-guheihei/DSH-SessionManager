pimport { randomBytes, timingSafeEqual } from "node:crypto";
//#region src/desktop-browser-access.ts
/** Generation-scoped capability separating Electron from ordinary browsers. */
/** Header attached only by the Electron renderer's native network session. */
const DESKTOP_RENDERER_ACCESS_HEADER = "x-dsh-desktop-renderer";
const ACCESS_TOKEN_BYTES = 32;
const ACCESS_TOKEN_PATTERN = /^[A-Za-z0-9_-]{43}$/u;
const DESKTOP_MARKER_PREFIX = "dsh-desktop-";
/** Create one unpredictable renderer capability for a Desktop Host generation. */
function createDesktopBrowserAccess(ordinaryBrowserEnabled, token = randomBytes(ACCESS_TOKEN_BYTES).toString("base64url")) {
	if (typeof ordinaryBrowserEnabled !== "boolean") throw new TypeError("dsh-plugin-desktop: ordinary browser access must be a boolean");
	if (!ACCESS_TOKEN_PATTERN.test(token)) throw new TypeError("dsh-plugin-desktop: renderer access token must be 32 base64url bytes");
	return Object.freeze({
		ordinaryBrowserEnabled,
		rendererHeader: Object.freeze({
			name: DESKTOP_RENDERER_ACCESS_HEADER,
			value: token
		})
	});
}
function exactHeaderValue(headers) {
	const value = headers[DESKTOP_RENDERER_ACCESS_HEADER];
	return typeof value === "string" ? value : void 0;
}
function sameToken(actual, expected) {
	if (actual === void 0 || !ACCESS_TOKEN_PATTERN.test(actual) || actual.length !== expected.length) return false;
	return timingSafeEqual(Buffer.from(actual), Buffer.from(expected));
}
/** Whether an uncredentialed URL is attempting to activate Desktop-only client effects. */
function desktopBrowserUrlHasRendererMarkers(rawUrl) {
	let url;
	try {
		url = new URL(rawUrl ?? "/", "http://dsh.invalid");
	} catch {
		return true;
	}
	return [...url.searchParams.keys()].some((key) => key.startsWith(DESKTOP_MARKER_PREFIX));
}
/** Classify one HTTP or upgrade request without exposing the renderer token. */
function decideDesktopBrowserAccess(access, request) {
	if (sameToken(exactHeaderValue(request.headers), access.rendererHeader.value)) return "renderer";
	if (!access.ordinaryBrowserEnabled || desktopBrowserUrlHasRendererMarkers(request.url)) return "denied";
	return "browser";
}
//#endregion
export { decideDesktopBrowserAccess as n, createDesktopBrowserAccess as t };

//# sourceMappingURL=desktop-browser-access-B6cep7Gf.js.ma