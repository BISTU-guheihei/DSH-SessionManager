
import { C as DESKTOP_RESTART_PATH, S as DESKTOP_RENDERER_RELOAD_PATH, T as DESKTOP_TERMINAL_OPEN_PATH, _ as DESKTOP_PROFILE_CREATE_PATH, a as handleDesktopProfileCreateWindowRequest, b as DESKTOP_PROFILE_SELECT_PATH, c as handleDesktopRecoveryRestartRequest, d as handleDesktopSettingsRequest, f as handleDesktopTerminalOpenRequest, g as DESKTOP_MARKET_SELECT_PATH, h as DESKTOP_DIAGNOSTICS_EXPORT_PATH, i as handleDesktopProfileCreateRequest, l as handleDesktopRendererReloadRequest, m as DESKTOP_DEVELOPER_TOOLS_TOGGLE_PATH, n as handleDesktopDiagnosticsExportRequest, o as handleDesktopProfileDeleteRequest, r as handleDesktopMarketSelectRequest, s as handleDesktopProfileSelectRequest, t as handleDesktopDeveloperToolsToggleRequest, u as handleDesktopRestartRequest, v as DESKTOP_PROFILE_CREATE_WINDOW_PATH, w as DESKTOP_SETTINGS_PATH, x as DESKTOP_RECOVERY_RESTART_PATH, y as DESKTOP_PROFILE_DELETE_PATH } from "./desktop-settings-route-D1KGHwVl.js";
import { t as DESKTOP_DEFAULT_WEB_PORT } from "./desktop-port-DWrq-_UM.js";
import { a as desktopNetworkExposureForBrowserAccess, n as desktopBrowserAccessEnabled, o as desktopWebServerHost, t as desktopBrowserAccessAvailable } from "./desktop-network-sx9NhTqd.js";
import { n as DEFAULT_WINDOWS_WINDOW_MATERIAL, r as effectiveDesktopWindowMaterial, s as windowsSupportsMica, t as DEFAULT_MACOS_WINDOW_MATERIAL } from "./window-material-0cOktjGz.js";
import { fileURLToPath } from "node:url";
import z from "@deepseek-ai/schemastery";
import { LOCALE_SETTINGS_NAMESPACE } from "@deepseek-ai/dsh-client-locale";
import { THEME_SETTINGS_NAMESPACE } from "@deepseek-ai/dsh-client-ui-theme";
import { settingsNamespace } from "@deepseek-ai/dsh-settings";
//#region src/renderer-boot-contract.ts
/** Loopback Host endpoint reserved for one renderer generation's terminal boot report. */
const RENDERER_BOOT_REPORT_PATH = "/_dsh/desktop/renderer-boot";
//#endregion
//#region src/renderer-boot.ts
const MAX_REPORT_BYTES = 16 * 1024;
const MAX_FAILED_PLUGINS = 64;
function isRecord(value) {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}
function parseReport(value) {
	if (!isRecord(value)) return void 0;
	if (value.status === "healthy") return { status: "healthy" };
	if (value.status !== "failed" || !Array.isArray(value.plugins) || value.plugins.length > MAX_FAILED_PLUGINS) return;
	if (!value.plugins.every((plugin) => typeof plugin === "string" && plugin.length > 0 && plugin.length <= 512)) return;
	if (value.error !== void 0 && (typeof value.error !== "string" || value.error.length > 12 * 1024)) return;
	return {
		status: "failed",
		plugins: [...value.plugins],
		...value.error === void 0 ? {} : { error: value.error }
	};
}
async function readReport(req) {
	const chunks = [];
	let size = 0;
	for await (const chunk of req) {
		const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
		size += bytes.byteLength;
		if (size > MAX_REPORT_BYTES) return void 0;
		chunks.push(bytes);
	}
	try {
		return parseReport(JSON.parse(Buffer.concat(chunks).toString("utf8")));
	} catch {
		return;
	}
}
function finish(res, statusCode) {
	res.statusCode = statusCode;
	res.end();
}
/** Validate and forward one same-origin renderer Loader outcome. */
async function handleRendererBootRequest(req, res, expectedOrigin, report) {
	if (req.method !== "POST") return finish(res, 405);
	if (req.headers.origin !== expectedOrigin) return finish(res, 403);
	if (req.headers["content-type"]?.split(";", 1)[0]?.trim().toLowerCase() !== "application/json") return finish(res, 415);
	const value = await readReport(req);
	if (value === void 0) return finish(res, 400);
	report(value);
	finish(res, 204);
}
//#endregion
//#region src/directory-picker-contract.ts
/** Same-origin endpoint used by the Windows browse panel's native-picker shortcut. */
const DESKTOP_DIRECTORY_PICKER_PATH = "/_dsh/desktop/pick-directory";
/** Same-origin endpoint used before either workspace picker accepts a path. */
const DESKTOP_DIRECTORY_VALIDATOR_PATH = "/_dsh/desktop/validate-directory";
//#endregion
//#region src/directory-picker-route.ts
const MAX_VALIDATION_BODY_BYTES = 16 * 1024;
function finishJson(res, statusCode, value) {
	res.statusCode = statusCode;
	res.setHeader("content-type", "application/json; charset=utf-8");
	res.end(JSON.stringify(value));
}
async function readJson(req) {
	let size = 0;
	const chunks = [];
	for await (const chunk of req) {
		const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
		size += buffer.length;
		if (size > MAX_VALIDATION_BODY_BYTES) throw new Error("request body is too large");
		chunks.push(buffer);
	}
	return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}
function isValidationRequest(value) {
	if (typeof value !== "object" || value === null || !("path" in value)) return false;
	const path = value.path;
	return typeof path === "string" && path.trim().length > 0;
}
/** Validate and serve one native directory-picker request from the desktop renderer. */
async function handleDesktopDirectoryPickerRequest(req, res, expectedOrigin, pickDirectory, reportError = () => {}) {
	if (req.method !== "POST") return finishJson(res, 405, { error: "method not allowed" });
	if (req.headers.origin !== expectedOrigin) return finishJson(res, 403, { error: "forbidden" });
	try {
		finishJson(res, 200, { path: await pickDirectory() });
	} catch (cause) {
		reportError(cause);
		finishJson(res, 500, { error: "native directory picker failed" });
	}
}
/** Validate one renderer-selected workspace before it can be persisted. */
async function handleDesktopDirectoryValidationRequest(req, res, expectedOrigin, validateDirectory, reportError = () => {}) {
	if (req.method !== "POST") return finishJson(res, 405, { error: "method not allowed" });
	if (req.headers.origin !== expectedOrigin) return finishJson(res, 403, { error: "forbidden" });
	if (req.headers["content-type"]?.split(";", 1)[0]?.trim().toLowerCase() !== "application/json") return finishJson(res, 415, { error: "content type must be application/json" });
	let value;
	try {
		value = await readJson(req);
	} catch (cause) {
		reportError(cause);
		return finishJson(res, 400, { error: "invalid directory validation request" });
	}
	if (!isValidationRequest(value)) return finishJson(res, 400, { error: "invalid directory validation request" });
	try {
		finishJson(res, 200, { allowed: await validateDirectory(value.path) });
	} catch (cause) {
		reportError(cause);
		finishJson(res, 500, { error: "directory validation failed" });
	}
}
//#endregion
//#region src/desktop-boot-recovery.ts
/** The bounded same-origin request used to restart into Recovery Mode. */
const DESKTOP_RECOVERY_RESTART_REQUEST = Object.freeze({
	method: "POST",
	headers: { "content-type": "application/json" },
	body: "{}",
	credentials: "same-origin"
});
/** Minimal presentation for the one early-boot Recovery Mode action. */
const DESKTOP_BOOT_RECOVERY_STYLE = `
[data-dsh-desktop-recovery] {
  --dsh-recovery-primary-bg: var(--dsw-alias-button-primary-fill, var(--dsh-boot-brand, #0f1115));
  --dsh-recovery-primary-hover: var(--dsw-alias-button-primary-hover, #303238);
  --dsh-recovery-primary-fg: var(--dsw-alias-label-primary-foreground, #fff);
  display: flex;
  justify-content: center;
  width: min(480px, calc(100vw - 48px));
  color: var(--dsh-recovery-primary-fg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
[data-dsh-desktop-recovery] button {
  min-height: 40px;
  padding: 0 18px;
  border: 0;
  border-radius: 20px;
  background: var(--dsh-recovery-primary-bg);
  color: var(--dsh-recovery-primary-fg);
  cursor: pointer;
  font: 500 14px/22px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
[data-dsh-desktop-recovery] button:hover:not(:disabled),
[data-dsh-desktop-recovery] button:active:not(:disabled) {
  background: var(--dsh-recovery-primary-hover);
}
[data-dsh-desktop-recovery] button:focus-visible {
  outline: 2px solid #5b8def;
  outline-offset: 2px;
}
[data-dsh-desktop-recovery] button:disabled {
  cursor: progress;
  opacity: 0.52;
}
body[data-ds-dark-theme] [data-dsh-desktop-recovery] {
  --dsh-recovery-primary-bg: #f9fafb;
  --dsh-recovery-primary-hover: #dfe3e6;
  --dsh-recovery-primary-fg: #151517;
}
@media (prefers-color-scheme: dark) {
  [data-dsh-desktop-recovery] {
    --dsh-recovery-primary-bg: #f9fafb;
    --dsh-recovery-primary-hover: #dfe3e6;
    --dsh-recovery-primary-fg: #151517;
  }
}
@media (max-width: 520px) {
  [data-dsh-desktop-recovery] { width: calc(100vw - 32px); }
  [data-dsh-desktop-recovery] button { width: 100%; }
}
`;
/** Replace the upstream plugin-failure report with one Recovery Mode button. */
const DESKTOP_BOOT_RECOVERY_SCRIPT = `(() => {
  const endpoint = ${JSON.stringify(DESKTOP_RECOVERY_RESTART_PATH)};
  const request = ${JSON.stringify(DESKTOP_RECOVERY_RESTART_REQUEST)};
  const label = '打开恢复模式 / Open Recovery Mode';
  const element = (tag, attributes, content) => {
    const node = document.createElement(tag);
    for (const [name, value] of Object.entries(attributes || {})) {
      if (name === 'dataset') Object.assign(node.dataset, value);
      else node.setAttribute(name, value);
    }
    if (content !== undefined) node.textContent = content;
    return node;
  };
  const attach = () => {
    const root = document.querySelector('[data-dsh-boot]');
    if (!root || root.querySelector('[data-dsh-desktop-recovery]')) return;
    const title = [...root.querySelectorAll('div')].find((node) =>
      node.childElementCount === 0 && node.textContent?.trim() === 'Failed to load plugins'
    );
    const report = title?.parentElement;
    const container = report?.parentElement;
    if (!container) return;
    const panel = element('section', {
      'aria-label': label,
      dataset: { dshDesktopRecovery: '' },
    });
    const button = element('button', { type: 'button', 'aria-label': label }, label);
    button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        const response = await fetch(endpoint, request);
        if (!response.ok) throw new Error('Desktop recovery request failed');
      } catch {
        button.disabled = false;
      }
    });
    panel.append(button);
    container.replaceChildren(panel);
  };
  new MutationObserver(attach).observe(document.documentElement, { childList: true, subtree: true });
  attach();
})();`;
/** Structured rows consumed by both the loopback server and static boot renderer. */
function desktopBootRecoveryInjections() {
	return [{
		kind: "style",
		text: DESKTOP_BOOT_RECOVERY_STYLE
	}, {
		kind: "script",
		placement: "body",
		text: DESKTOP_BOOT_RECOVERY_SCRIPT
	}];
}
//#endregion
//#region src/index.ts
/** DSH Desktop Host plugin: owns the selected native shell generation. */
/** Stable Cordis plugin name. */
const name = "desktop-shell";
/** Services required before the shell can register its renderer generation. */
/** Services required by the desktop shell; `desktopRuntime` is probed, not required. */
const inject = [
	"webServer",
	"webRuntime",
	"appExit",
	"settings"
];
/** Standard settings namespace shared by tray and configuration surfaces. */
const DESKTOP_SETTINGS_NAMESPACE = settingsNamespace("dsh-desktop");
const UI_THEME_SETTINGS_NAMESPACE = settingsNamespace(THEME_SETTINGS_NAMESPACE);
const UI_LOCALE_SETTINGS_NAMESPACE = settingsNamespace(LOCALE_SETTINGS_NAMESPACE);
/** Schema registered with the standard settings service. */
const DesktopSettingsSchema = z.object({
	mode: z.union([
		"compatibility",
		"extended",
		"advanced"
	]).default("compatibility"),
	macosMaterial: z.union(["off", "transparent"]).default(DEFAULT_MACOS_WINDOW_MATERIAL),
	windowsMaterial: z.union([
		"off",
		"acrylic",
		"mica"
	]).default(DEFAULT_WINDOWS_WINDOW_MATERIAL),
	port: z.number().step(1).min(0).max(65535).default(DESKTOP_DEFAULT_WEB_PORT),
	openBrowser: z.boolean().default(false),
	networkExposure: z.union(["loopback", "lan"]).default("loopback"),
	logLevel: z.union([
		"debug",
		"info",
		"warn",
		"error"
	]).default("info")
});
/** Validated native window configuration. */
const Config = z.object({
	mode: z.union([
		"compatibility",
		"extended",
		"advanced"
	]).default("compatibility"),
	macosMaterial: z.union(["off", "transparent"]).default(DEFAULT_MACOS_WINDOW_MATERIAL),
	windowsMaterial: z.union([
		"off",
		"acrylic",
		"mica"
	]).default(DEFAULT_WINDOWS_WINDOW_MATERIAL),
	port: z.number().step(1).min(0).max(65535).default(DESKTOP_DEFAULT_WEB_PORT),
	networkExposure: z.union(["loopback", "lan"]).default("loopback"),
	width: z.number().step(1).min(800).default(1280),
	height: z.number().step(1).min(600).default(840),
	minWidth: z.number().step(1).min(640).default(900),
	minHeight: z.number().step(1).min(480).default(640)
});
/**
* Construct the unmodified upstream Web root URL.
* @param port - active loopback Web server port.
* @param mode - active native presentation mode.
* @param platform - active Electron platform.
* @returns the URL loaded by the BrowserWindow.
*/
function desktopRendererUrl(port, mode, platform, appVersion, material = "off", windowsBuild) {
	const url = new URL(`http://127.0.0.1:${String(port)}/`);
	url.searchParams.set("dsh-desktop-mode", mode);
	url.searchParams.set("dsh-desktop-platform", platform);
	url.searchParams.set("dsh-desktop-version", appVersion);
	url.searchParams.set("dsh-desktop-material", material);
	if (mode === "extended" || mode === "compatibility" && platform !== "linux") url.searchParams.set("dsh-desktop-titlebar-inset", String(36));
	if (platform === "win32") url.searchParams.set("dsh-desktop-mica", windowsSupportsMica(windowsBuild) ? "1" : "0");
	return url.href;
}
/**
* Register the Electron shell from active Web carrier values.
* @param ctx - Host context carrying the Electron adapter and Web carrier.
* @param config - validated native window values.
*/
function apply(ctx, config) {
	const runtime = ctx.get("desktopRuntime");
	if (runtime === void 0) {
		process.stderr.write("dsh-plugin-desktop: this profile is composed with the DSH Desktop shell, which requires the desktop launcher (desktopRuntime).\nStart it with `dsh-desktop`, or select this profile inside the packaged DSH Desktop application.\nThe desktop terminal, profile, and update rows stay inactive in an ordinary DSH boot.\n");
		return;
	}
	const appExit = ctx.get("appExit");
	if (appExit === void 0) throw new Error("dsh-plugin-desktop: the launcher did not provide ctx.appExit");
	const browserAccess = ctx.get("desktopBrowserAccess");
	if (browserAccess === void 0) throw new Error("dsh-plugin-desktop: the launcher did not provide ctx.desktopBrowserAccess");
	if (ctx.webServer.host !== desktopWebServerHost(config.networkExposure)) throw new Error("dsh-plugin-desktop: desktop shell WebServer host does not match networkExposure");
	const iconFilename = runtime.platform === "darwin" ? "app-icon-mac.png" : "app-icon.png";
	const iconPath = fileURLToPath(new URL(`../build/${iconFilename}`, import.meta.url));
	const trayIcons = {
		templatePath: fileURLToPath(new URL("../build/tray-iconTemplate.png", import.meta.url)),
		bluePath: fileURLToPath(new URL("../build/tray-icon-blue.png", import.meta.url))
	};
	const settings = ctx.settings.register(DESKTOP_SETTINGS_NAMESPACE, DesktopSettingsSchema, {
		applies: "restart",
		validate: (value) => {
			if (!desktopBrowserAccessAvailable(value.mode) && (value.openBrowser || value.networkExposure === "lan")) throw new Error("dsh-plugin-desktop: browser and LAN access require compatibility mode");
			if (value.mode !== "compatibility" && runtime.platform === "linux") throw new Error("dsh-plugin-desktop: custom desktop shell modes are supported on macOS and Windows");
		}
	});
	const rendererOrigin = `http://127.0.0.1:${String(ctx.webServer.port)}`;
	ctx.on("webserver/index-inject", (table) => {
		table.push(...desktopBootRecoveryInjections());
	});
	const desktopSettings = ctx.get("desktopSettingsController");
	if (desktopSettings !== void 0) {
		const reportSettingsError = (operation, cause) => {
			ctx.logger.error(`dsh-plugin-desktop: failed to ${operation}: ${cause instanceof Error ? cause.message : String(cause)}`);
		};
		const settingsRoutes = [
			[DESKTOP_SETTINGS_PATH, handleDesktopSettingsRequest],
			[DESKTOP_PROFILE_CREATE_PATH, handleDesktopProfileCreateRequest],
			[DESKTOP_PROFILE_CREATE_WINDOW_PATH, handleDesktopProfileCreateWindowRequest],
			[DESKTOP_PROFILE_DELETE_PATH, handleDesktopProfileDeleteRequest],
			[DESKTOP_PROFILE_SELECT_PATH, handleDesktopProfileSelectRequest],
			[DESKTOP_MARKET_SELECT_PATH, handleDesktopMarketSelectRequest],
			[DESKTOP_TERMINAL_OPEN_PATH, handleDesktopTerminalOpenRequest],
			[DESKTOP_RESTART_PATH, handleDesktopRestartRequest],
			[DESKTOP_RECOVERY_RESTART_PATH, handleDesktopRecoveryRestartRequest],
			[DESKTOP_RENDERER_RELOAD_PATH, handleDesktopRendererReloadRequest],
			[DESKTOP_DEVELOPER_TOOLS_TOGGLE_PATH, handleDesktopDeveloperToolsToggleRequest],
			[DESKTOP_DIAGNOSTICS_EXPORT_PATH, handleDesktopDiagnosticsExportRequest]
		];
		for (const [path, handler] of settingsRoutes) ctx.effect(() => ctx.webServer.register({
			kind: "exact",
			path,
			handler: (req, res) => handler(req, res, rendererOrigin, desktopSettings, reportSettingsError)
		}), `dsh-plugin-desktop: private settings route ${path}`);
	}
	ctx.effect(() => ctx.webServer.register({
		kind: "exact",
		path: RENDERER_BOOT_REPORT_PATH,
		handler: (req, res) => handleRendererBootRequest(req, res, rendererOrigin, (report) => {
			runtime.reportRendererBoot(report);
		})
	}), "dsh-plugin-desktop: renderer boot report route");
	if (runtime.platform === "win32") {
		ctx.effect(() => ctx.webServer.register({
			kind: "exact",
			path: DESKTOP_DIRECTORY_PICKER_PATH,
			handler: (req, res) => handleDesktopDirectoryPickerRequest(req, res, rendererOrigin, () => runtime.pickDirectory(), (cause) => {
				ctx.logger.error(`dsh-plugin-desktop: native directory picker failed: ${cause instanceof Error ? cause.message : String(cause)}`);
			})
		}), "dsh-plugin-desktop: native directory picker route");
		ctx.effect(() => ctx.webServer.register({
			kind: "exact",
			path: DESKTOP_DIRECTORY_VALIDATOR_PATH,
			handler: (req, res) => handleDesktopDirectoryValidationRequest(req, res, rendererOrigin, (path) => runtime.validateDirectory(path), (cause) => {
				ctx.logger.error(`dsh-plugin-desktop: workspace directory validation failed: ${cause instanceof Error ? cause.message : String(cause)}`);
			})
		}), "dsh-plugin-desktop: workspace directory validation route");
	}
	ctx.effect(() => {
		let pending;
		const stopWatching = settings.watch((next) => {
			const nextBrowserAccess = desktopBrowserAccessEnabled(next.mode, next.openBrowser, next.networkExposure);
			const nextNetworkExposure = desktopNetworkExposureForBrowserAccess(nextBrowserAccess, next.networkExposure);
			if (next.mode === config.mode && next.port === config.port && nextNetworkExposure === config.networkExposure && nextBrowserAccess === browserAccess.ordinaryBrowserEnabled && next.macosMaterial === config.macosMaterial && next.windowsMaterial === config.windowsMaterial) {
				if (pending !== void 0) clearImmediate(pending);
				pending = void 0;
				return;
			}
			pending ??= setImmediate(() => {
				pending = void 0;
				runtime.requestRestart().catch((cause) => {
					ctx.logger.error("dsh-plugin-desktop: failed to restart after startup setting change");
					ctx.logger.error(cause);
				});
			});
		});
		return () => {
			stopWatching();
			if (pending !== void 0) clearImmediate(pending);
		};
	}, "dsh-plugin-desktop: restart after startup setting change");
	if (runtime.platform !== "linux") ctx.on("settings/updated", (namespace, next) => {
		if (namespace !== UI_THEME_SETTINGS_NAMESPACE) return;
		runtime.setThemeSource(next.preference);
	});
	ctx.on("settings/updated", (namespace, next) => {
		if (namespace !== UI_LOCALE_SETTINGS_NAMESPACE) return;
		runtime.setLocalePreference(next.preference);
	});
	ctx.effect(() => {
		const material = effectiveDesktopWindowMaterial(config.mode, runtime.platform, config.macosMaterial, config.windowsMaterial, runtime.windowsBuild);
		return runtime.schedule({
			...config,
			material,
			...runtime.windowsBuild === void 0 ? {} : { windowsBuild: runtime.windowsBuild },
			url: desktopRendererUrl(ctx.webServer.port, config.mode, runtime.platform, runtime.updates.currentVersion, material, runtime.windowsBuild),
			rendererAccessHeader: browserAccess.rendererHeader,
			productName: "DSH Desktop",
			windowTitle: "DeepSeek Harness Desktop",
			iconPath,
			trayIcons,
			readLocalePreference: () => {
				return ctx.settings.get(UI_LOCALE_SETTINGS_NAMESPACE)?.preference;
			},
			readThemeSource: () => {
				const theme = ctx.settings.get(UI_THEME_SETTINGS_NAMESPACE);
				if (theme === void 0) throw new Error("dsh-plugin-desktop: custom shell requires the ui-theme settings namespace");
				return theme.preference;
			},
			requestQuit: appExit,
			requestModeChange: async (mode) => {
				const current = settings.get();
				const storedBrowserCapability = current.openBrowser || current.networkExposure === "lan";
				await settings.update(mode !== "compatibility" && storedBrowserCapability ? {
					mode,
					openBrowser: false,
					networkExposure: "loopback"
				} : { mode });
			}
		});
	}, "dsh-plugin-desktop: native shell generation");
}
//#endregion
export { desktopRendererUrl as a, apply as i, DESKTOP_SETTINGS_NAMESPACE as n, inject as o, DesktopSettingsSchema as r, name as s, Config as t };

//# sourceMappingURL=src-BPyeBlWF.js.ma