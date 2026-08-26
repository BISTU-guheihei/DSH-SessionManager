pimport { assertDesktopProfileName } from "./profile-manager.js";
//#region src/desktop-settings-contract.ts
/** Read the current Desktop-owned settings state. */
const DESKTOP_SETTINGS_PATH = "/api/desktop/settings";
/** Create one safe Web profile without selecting it. */
const DESKTOP_PROFILE_CREATE_PATH = "/api/desktop/profiles/create";
/** Select one compatible profile for the next Desktop generation. */
const DESKTOP_PROFILE_SELECT_PATH = "/api/desktop/profiles/select";
/** Delete one inactive, user-created Web Profile. */
const DESKTOP_PROFILE_DELETE_PATH = "/api/desktop/profiles/delete";
/** Persist the Market provider selected for the next Desktop generation. */
const DESKTOP_MARKET_SELECT_PATH = "/api/desktop/market/select";
/** Open the launcher-owned DSH terminal without accepting command text. */
const DESKTOP_TERMINAL_OPEN_PATH = "/api/desktop/terminal/open";
/** Queue an orderly Desktop relaunch after acknowledging the renderer. */
const DESKTOP_RESTART_PATH = "/api/desktop/restart";
/** Queue an orderly relaunch that opens the recovery assistant before Host boot. */
const DESKTOP_RECOVERY_RESTART_PATH = "/api/desktop/restart/recovery";
/** Reload the renderer through the launcher without exposing Electron APIs. */
const DESKTOP_RENDERER_RELOAD_PATH = "/api/desktop/developer/reload";
/** Toggle the mounted window's Developer Tools through the launcher. */
const DESKTOP_DEVELOPER_TOOLS_TOGGLE_PATH = "/api/desktop/developer/devtools";
/** Run the generation-owned manual update check. */
const DESKTOP_UPDATE_CHECK_PATH = "/api/desktop/updates/check";
/** Export one local diagnostic archive through the launcher-owned flow. */
const DESKTOP_DIAGNOSTICS_EXPORT_PATH = "/api/desktop/diagnostics/export";
/** Open the isolated native Profile creator without accepting a path. */
const DESKTOP_PROFILE_CREATE_WINDOW_PATH = "/api/desktop/profiles/create-window";
//#endregion
//#region src/desktop-settings-route.ts
const MAX_SETTINGS_BODY_BYTES = 16 * 1024;
var BodyTooLargeError = class extends Error {};
function finishJson(res, statusCode, value, allow) {
	res.statusCode = statusCode;
	res.setHeader("cache-control", "no-store");
	res.setHeader("content-type", "application/json; charset=utf-8");
	res.setHeader("x-content-type-options", "nosniff");
	if (allow !== void 0) res.setHeader("allow", allow);
	res.end(JSON.stringify(value));
}
function error(message) {
	return { error: message };
}
function isLoopbackHostname(hostname) {
	return hostname === "127.0.0.1" || hostname === "[::1]";
}
function isLoopbackAddress(address) {
	if (address === void 0) return false;
	if (address === "::1" || address === "127.0.0.1") return true;
	if (address.startsWith("::ffff:")) return address.slice(7).startsWith("127.");
	return address.startsWith("127.");
}
function expectedLoopbackOrigin(expectedOrigin) {
	try {
		const url = new URL(expectedOrigin);
		if (url.origin !== expectedOrigin || url.protocol !== "http:" || url.username !== "" || url.password !== "" || !isLoopbackHostname(url.hostname)) return void 0;
		return url;
	} catch {
		return;
	}
}
function exactHeaderOrigin(value) {
	if (value === void 0) return void 0;
	try {
		return new URL(value).origin === value ? value : void 0;
	} catch {
		return;
	}
}
function referrerOrigin(value) {
	if (value === void 0) return void 0;
	try {
		return new URL(value).origin;
	} catch {
		return;
	}
}
/**
* Require the actual socket and Host to stay on the configured loopback origin.
* A mutating request must carry the exact Origin. A read-only browser GET may
* use the standard same-origin fetch metadata plus its same-origin referrer,
* because browsers commonly omit Origin on same-origin GET requests.
*/
function isSameOriginLoopbackRequest(req, expectedOrigin, mutating) {
	const expected = expectedLoopbackOrigin(expectedOrigin);
	if (expected === void 0 || !isLoopbackAddress(req.socket.remoteAddress)) return false;
	if (req.headers.host?.toLowerCase() !== expected.host.toLowerCase()) return false;
	if (exactHeaderOrigin(req.headers.origin) === expected.origin) return req.headers["sec-fetch-site"] === void 0 || req.headers["sec-fetch-site"] === "same-origin";
	if (mutating) return false;
	return req.headers["sec-fetch-site"] === "same-origin" && referrerOrigin(req.headers.referer) === expected.origin;
}
function isJsonRequest(req) {
	return req.headers["content-type"]?.split(";", 1)[0]?.trim().toLowerCase() === "application/json";
}
async function readJson(req) {
	const declaredLength = req.headers["content-length"];
	if (declaredLength !== void 0) {
		if (!/^\d+$/.test(declaredLength)) throw new SyntaxError("invalid content length");
		if (Number(declaredLength) > MAX_SETTINGS_BODY_BYTES) throw new BodyTooLargeError();
	}
	let size = 0;
	const chunks = [];
	for await (const chunk of req) {
		const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
		size += buffer.byteLength;
		if (size > MAX_SETTINGS_BODY_BYTES) throw new BodyTooLargeError();
		chunks.push(buffer);
	}
	return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}
function isExactRecord(value, key) {
	return typeof value === "object" && value !== null && !Array.isArray(value) && Object.keys(value).length === 1 && Object.prototype.hasOwnProperty.call(value, key);
}
function parseProfileRequest(value) {
	if (!isExactRecord(value, "name") || typeof value.name !== "string") return void 0;
	try {
		assertDesktopProfileName(value.name);
		return { name: value.name };
	} catch {
		return;
	}
}
function isMarketProvider(value) {
	return value === "disabled" || value === "community-market" || value === "dsh-market";
}
function parseMarketRequest(value) {
	if (!isExactRecord(value, "provider") || !isMarketProvider(value.provider)) return void 0;
	return { provider: value.provider };
}
function isEmptyRequest(value) {
	return typeof value === "object" && value !== null && !Array.isArray(value) && Object.keys(value).length === 0;
}
async function parsePostBody(req, res) {
	if (!isJsonRequest(req)) {
		finishJson(res, 415, error("content type must be application/json"));
		return INVALID_BODY;
	}
	try {
		return await readJson(req);
	} catch (cause) {
		const tooLarge = cause instanceof BodyTooLargeError;
		finishJson(res, tooLarge ? 413 : 400, error(tooLarge ? "request body is too large" : "invalid JSON request"));
		return INVALID_BODY;
	}
}
const INVALID_BODY = Symbol("invalid body");
function finishPostResponse(res, statusCode, operation, operationName, reportError) {
	finishJson(res, statusCode, operation.response);
	if (operation.afterResponse === void 0) return;
	setImmediate(() => {
		try {
			operation.afterResponse?.();
		} catch (cause) {
			reportError(`${operationName} after response`, cause);
		}
	});
}
/** Serve the renderer-safe Desktop settings snapshot. */
async function handleDesktopSettingsRequest(req, res, expectedOrigin, controller, reportError = () => {}) {
	if (req.method !== "GET") return finishJson(res, 405, error("method not allowed"), "GET");
	if (!isSameOriginLoopbackRequest(req, expectedOrigin, false)) return finishJson(res, 403, error("forbidden"));
	try {
		finishJson(res, 200, controller.read());
	} catch (cause) {
		reportError("read settings", cause);
		finishJson(res, 500, error("desktop settings unavailable"));
	}
}
/** Create one safe Web profile without changing the active generation. */
async function handleDesktopProfileCreateRequest(req, res, expectedOrigin, controller, reportError = () => {}) {
	if (req.method !== "POST") return finishJson(res, 405, error("method not allowed"), "POST");
	if (!isSameOriginLoopbackRequest(req, expectedOrigin, true)) return finishJson(res, 403, error("forbidden"));
	const value = await parsePostBody(req, res);
	if (value === INVALID_BODY) return;
	const request = parseProfileRequest(value);
	if (request === void 0) return finishJson(res, 400, error("invalid profile creation request"));
	try {
		finishJson(res, 201, controller.createProfile(request.name));
	} catch (cause) {
		reportError("create profile", cause);
		finishJson(res, 409, error("profile could not be created"));
	}
}
/** Select one compatible profile through the restart-safe launcher service. */
async function handleDesktopProfileSelectRequest(req, res, expectedOrigin, controller, reportError = () => {}) {
	if (req.method !== "POST") return finishJson(res, 405, error("method not allowed"), "POST");
	if (!isSameOriginLoopbackRequest(req, expectedOrigin, true)) return finishJson(res, 403, error("forbidden"));
	const value = await parsePostBody(req, res);
	if (value === INVALID_BODY) return;
	const request = parseProfileRequest(value);
	if (request === void 0) return finishJson(res, 400, error("invalid profile selection request"));
	try {
		const operation = await controller.selectProfile(request.name);
		finishPostResponse(res, operation.response.restartRequired ? 202 : 200, operation, "select profile", reportError);
	} catch (cause) {
		reportError("select profile", cause);
		finishJson(res, 409, error("profile could not be selected"));
	}
}
/** Delete one inactive user profile and return a fresh settings projection. */
async function handleDesktopProfileDeleteRequest(req, res, expectedOrigin, controller, reportError = () => {}) {
	if (req.method !== "POST") return finishJson(res, 405, error("method not allowed"), "POST");
	if (!isSameOriginLoopbackRequest(req, expectedOrigin, true)) return finishJson(res, 403, error("forbidden"));
	const value = await parsePostBody(req, res);
	if (value === INVALID_BODY) return;
	const request = parseProfileRequest(value);
	if (request === void 0) return finishJson(res, 400, error("invalid profile deletion request"));
	try {
		finishJson(res, 200, await controller.deleteProfile(request.name));
	} catch (cause) {
		reportError("delete profile", cause);
		finishJson(res, 409, error("profile could not be deleted"));
	}
}
/** Persist one Market provider and queue restart only after persistence succeeds. */
async function handleDesktopMarketSelectRequest(req, res, expectedOrigin, controller, reportError = () => {}) {
	if (req.method !== "POST") return finishJson(res, 405, error("method not allowed"), "POST");
	if (!isSameOriginLoopbackRequest(req, expectedOrigin, true)) return finishJson(res, 403, error("forbidden"));
	const value = await parsePostBody(req, res);
	if (value === INVALID_BODY) return;
	const request = parseMarketRequest(value);
	if (request === void 0) return finishJson(res, 400, error("invalid Market selection request"));
	try {
		const operation = await controller.selectMarket(request.provider);
		finishPostResponse(res, operation.response.restartRequired ? 202 : 200, operation, "select Market provider", reportError);
	} catch (cause) {
		reportError("select Market provider", cause);
		finishJson(res, 500, error("Market selection could not be saved"));
	}
}
/** Open the launcher-owned DSH terminal from an exact empty request. */
async function handleDesktopTerminalOpenRequest(req, res, expectedOrigin, controller, reportError = () => {}) {
	if (req.method !== "POST") return finishJson(res, 405, error("method not allowed"), "POST");
	if (!isSameOriginLoopbackRequest(req, expectedOrigin, true)) return finishJson(res, 403, error("forbidden"));
	const value = await parsePostBody(req, res);
	if (value === INVALID_BODY) return;
	if (!isEmptyRequest(value)) return finishJson(res, 400, error("invalid terminal request"));
	try {
		finishJson(res, 200, controller.openTerminal());
	} catch (cause) {
		reportError("open terminal", cause);
		finishJson(res, 500, error("terminal could not be opened"));
	}
}
/** Queue an orderly Desktop relaunch from an exact empty request. */
async function handleDesktopRestartRequest(req, res, expectedOrigin, controller, reportError = () => {}) {
	if (req.method !== "POST") return finishJson(res, 405, error("method not allowed"), "POST");
	if (!isSameOriginLoopbackRequest(req, expectedOrigin, true)) return finishJson(res, 403, error("forbidden"));
	const value = await parsePostBody(req, res);
	if (value === INVALID_BODY) return;
	if (!isEmptyRequest(value)) return finishJson(res, 400, error("invalid restart request"));
	finishPostResponse(res, 202, controller.restart(), "restart Desktop", reportError);
}
/** Queue an orderly recovery-mode relaunch from an exact empty request. */
async function handleDesktopRecoveryRestartRequest(req, res, expectedOrigin, controller, reportError = () => {}) {
	if (req.method !== "POST") return finishJson(res, 405, error("method not allowed"), "POST");
	if (!isSameOriginLoopbackRequest(req, expectedOrigin, true)) return finishJson(res, 403, error("forbidden"));
	const value = await parsePostBody(req, res);
	if (value === INVALID_BODY) return;
	if (!isEmptyRequest(value)) return finishJson(res, 400, error("invalid recovery restart request"));
	finishPostResponse(res, 202, controller.restartToRecovery(), "restart Desktop in recovery mode", reportError);
}
/** Reload the renderer after acknowledging an exact empty same-origin request. */
async function handleDesktopRendererReloadRequest(req, res, expectedOrigin, controller, reportError = () => {}) {
	if (req.method !== "POST") return finishJson(res, 405, error("method not allowed"), "POST");
	if (!isSameOriginLoopbackRequest(req, expectedOrigin, true)) return finishJson(res, 403, error("forbidden"));
	const value = await parsePostBody(req, res);
	if (value === INVALID_BODY) return;
	if (!isEmptyRequest(value)) return finishJson(res, 400, error("invalid renderer reload request"));
	finishPostResponse(res, 202, controller.reloadRenderer(), "reload renderer", reportError);
}
/** Toggle Developer Tools from an exact empty same-origin request. */
async function handleDesktopDeveloperToolsToggleRequest(req, res, expectedOrigin, controller, reportError = () => {}) {
	if (req.method !== "POST") return finishJson(res, 405, error("method not allowed"), "POST");
	if (!isSameOriginLoopbackRequest(req, expectedOrigin, true)) return finishJson(res, 403, error("forbidden"));
	const value = await parsePostBody(req, res);
	if (value === INVALID_BODY) return;
	if (!isEmptyRequest(value)) return finishJson(res, 400, error("invalid Developer Tools request"));
	try {
		finishJson(res, 200, controller.toggleDeveloperTools());
	} catch (cause) {
		reportError("toggle Developer Tools", cause);
		finishJson(res, 500, error("Developer Tools could not be toggled"));
	}
}
/** Run the generation-owned interactive update flow from an exact empty request. */
async function handleDesktopUpdateCheckRequest(req, res, expectedOrigin, checkNow, reportError = () => {}) {
	if (req.method !== "POST") return finishJson(res, 405, error("method not allowed"), "POST");
	if (!isSameOriginLoopbackRequest(req, expectedOrigin, true)) return finishJson(res, 403, error("forbidden"));
	const value = await parsePostBody(req, res);
	if (value === INVALID_BODY) return;
	if (!isEmptyRequest(value)) return finishJson(res, 400, error("invalid update check request"));
	try {
		await checkNow();
		finishJson(res, 200, { accepted: true });
	} catch (cause) {
		reportError("check for updates", cause);
		finishJson(res, 500, error("updates could not be checked"));
	}
}
/** Export diagnostics from an exact empty same-origin request. */
async function handleDesktopDiagnosticsExportRequest(req, res, expectedOrigin, controller, reportError = () => {}) {
	if (req.method !== "POST") return finishJson(res, 405, error("method not allowed"), "POST");
	if (!isSameOriginLoopbackRequest(req, expectedOrigin, true)) return finishJson(res, 403, error("forbidden"));
	const value = await parsePostBody(req, res);
	if (value === INVALID_BODY) return;
	if (!isEmptyRequest(value)) return finishJson(res, 400, error("invalid diagnostic export request"));
	try {
		finishJson(res, 200, await controller.exportDiagnostics());
	} catch (cause) {
		reportError("export diagnostics", cause);
		finishJson(res, 500, error("diagnostics could not be exported"));
	}
}
/** Open the isolated native Profile creator from an exact empty request. */
async function handleDesktopProfileCreateWindowRequest(req, res, expectedOrigin, controller, reportError = () => {}) {
	if (req.method !== "POST") return finishJson(res, 405, error("method not allowed"), "POST");
	if (!isSameOriginLoopbackRequest(req, expectedOrigin, true)) return finishJson(res, 403, error("forbidden"));
	const value = await parsePostBody(req, res);
	if (value === INVALID_BODY) return;
	if (!isEmptyRequest(value)) return finishJson(res, 400, error("invalid Profile creator request"));
	try {
		finishJson(res, 200, controller.openProfileCreator());
	} catch (cause) {
		reportError("open Profile creator", cause);
		finishJson(res, 500, error("Profile creator could not be opened"));
	}
}
Object.freeze({ maxBodyBytes: MAX_SETTINGS_BODY_BYTES });
//#endregion
export { DESKTOP_RESTART_PATH as C, DESKTOP_UPDATE_CHECK_PATH as E, DESKTOP_RENDERER_RELOAD_PATH as S, DESKTOP_TERMINAL_OPEN_PATH as T, DESKTOP_PROFILE_CREATE_PATH as _, handleDesktopProfileCreateWindowRequest as a, DESKTOP_PROFILE_SELECT_PATH as b, handleDesktopRecoveryRestartRequest as c, handleDesktopSettingsRequest as d, handleDesktopTerminalOpenRequest as f, DESKTOP_MARKET_SELECT_PATH as g, DESKTOP_DIAGNOSTICS_EXPORT_PATH as h, handleDesktopProfileCreateRequest as i, handleDesktopRendererReloadRequest as l, DESKTOP_DEVELOPER_TOOLS_TOGGLE_PATH as m, handleDesktopDiagnosticsExportRequest as n, handleDesktopProfileDeleteRequest as o, handleDesktopUpdateCheckRequest as p, handleDesktopMarketSelectRequest as r, handleDesktopProfileSelectRequest as s, handleDesktopDeveloperToolsToggleRequest as t, handleDesktopRestartRequest as u, DESKTOP_PROFILE_CREATE_WINDOW_PATH as v, DESKTOP_SETTINGS_PATH as w, DESKTOP_RECOVERY_RESTART_PATH as x, DESKTOP_PROFILE_DELETE_PATH as y };

//# sourceMappingURL=desktop-settings-route-D1KGHwVl.js.ma