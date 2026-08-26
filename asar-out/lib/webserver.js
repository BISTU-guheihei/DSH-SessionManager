pimport { n as decideDesktopBrowserAccess } from "./desktop-browser-access-B6cep7Gf.js";
import { Service } from "@deepseek-ai/cordis";
import WebServer from "@deepseek-ai/dsh-host-webserver";
//#region src/webserver.ts
function isAddressInUse(cause) {
	return cause?.code === "EADDRINUSE";
}
/** Close an unbound server left behind by a failed listen attempt. */
function closeFailedServer(instance) {
	const server = instance?.server;
	if (typeof server?.close !== "function") return;
	try {
		server.close(() => {});
	} catch {}
}
function rejectBrowserRequest(res) {
	res.statusCode = 403;
	res.setHeader("cache-control", "no-store");
	res.setHeader("content-type", "text/plain; charset=utf-8");
	res.setHeader("x-content-type-options", "nosniff");
	res.end("forbidden");
}
function rejectBrowserUpgrade(socket) {
	socket.end([
		"HTTP/1.1 403 Forbidden",
		"Connection: close",
		"Content-Type: text/plain; charset=utf-8",
		"Content-Length: 9",
		"",
		"forbidden"
	].join("\r\n"));
}
/** Reuse the upstream WebServer while retrying only real bind collisions. */
var DesktopWebServer = class extends WebServer {
	static Config = WebServer.Config;
	desktopConfig;
	constructor(ctx, config) {
		if (config.host !== "127.0.0.1" && config.host !== "0.0.0.0") throw new Error("dsh-plugin-desktop: Desktop WebServer requires a supported host");
		super(ctx, config);
		this.desktopConfig = config;
	}
	permits(request) {
		const access = this.ctx.get("desktopBrowserAccess");
		return access === void 0 || decideDesktopBrowserAccess(access, request) !== "denied";
	}
	register(route) {
		return super.register({
			...route,
			handler: async (req, res) => {
				if (!this.permits(req)) return rejectBrowserRequest(res);
				await route.handler(req, res);
			}
		});
	}
	registerFallback(handler) {
		return super.registerFallback(async (req, res) => {
			if (!this.permits(req)) return rejectBrowserRequest(res);
			await handler(req, res);
		});
	}
	registerUpgrade(route) {
		return super.registerUpgrade({
			...route,
			handler: (req, socket, head) => {
				if (!this.permits(req)) return rejectBrowserUpgrade(socket);
				return route.handler(req, socket, head);
			}
		});
	}
	async [Service.init]() {
		const requestedPort = this.desktopConfig.port;
		if (requestedPort === 0) {
			await super[Service.init]();
			return;
		}
		for (let attempt = 0;; attempt += 1) try {
			await super[Service.init]();
			return;
		} catch (cause) {
			const nextPort = requestedPort + attempt + 1;
			if (!isAddressInUse(cause) || attempt >= 32 || nextPort > 65535) throw cause;
			closeFailedServer(this);
			this.desktopConfig.port = nextPort;
		}
	}
};
//#endregion
export { DesktopWebServer, DesktopWebServer as default };

//# sourceMappingURL=webserver.js.ma