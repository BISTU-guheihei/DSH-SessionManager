p//#region src/desktop-network.ts
/**
* Parse the browser-access preference.
*
* `openBrowser` is retained as the persisted key for compatibility. Desktop
* never projects it into the upstream default-browser handoff.
*/
function parseDesktopOpenBrowser(value) {
	if (value === void 0) return false;
	if (typeof value === "boolean") return value;
	throw new Error("dsh-plugin-desktop: dsh-desktop.openBrowser must be a boolean");
}
/** Browser access can only be granted by an explicitly selected compatibility shell. */
function desktopBrowserAccessAvailable(mode) {
	return mode === "compatibility";
}
/**
* Resolve browser access while preserving already-exposed legacy LAN setups
* only when the selected shell is compatible with an ordinary browser.
*/
function desktopBrowserAccessEnabled(mode, storedOpenBrowser, exposure) {
	return desktopBrowserAccessAvailable(mode) && (storedOpenBrowser || exposure === "lan");
}
/** LAN exposure is meaningful only while ordinary-browser access is enabled. */
function desktopNetworkExposureForBrowserAccess(browserAccess, exposure) {
	return browserAccess ? exposure : "loopback";
}
/** Parse the restart-applied listener exposure preference. */
function parseDesktopNetworkExposure(value) {
	if (value === void 0) return "loopback";
	if (value === "loopback" || value === "lan") return value;
	throw new Error("dsh-plugin-desktop: dsh-desktop.networkExposure must be \"loopback\" or \"lan\"");
}
/** Project a persisted exposure preference into the supported WebServer host literal. */
function desktopWebServerHost(exposure) {
	return exposure === "lan" ? "0.0.0.0" : "127.0.0.1";
}
/** Marker-free URL suitable for an ordinary local browser. */
function desktopLoopbackBrowserUrl(port) {
	return `http://127.0.0.1:${String(port)}/`;
}
/** Marker-free URLs advertised for the Web runtime's startup-sampled LAN addresses. */
function desktopLanBrowserUrls(port, addresses) {
	return Object.freeze(addresses.map((address) => `http://${address}:${String(port)}/`));
}
//#endregion
export { desktopNetworkExposureForBrowserAccess as a, parseDesktopOpenBrowser as c, desktopLoopbackBrowserUrl as i, desktopBrowserAccessEnabled as n, desktopWebServerHost as o, desktopLanBrowserUrls as r, parseDesktopNetworkExposure as s, desktopBrowserAccessAvailable as t };

//# sourceMappingURL=desktop-network-sx9NhTqd.js.ma