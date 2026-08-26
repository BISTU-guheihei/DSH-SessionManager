plet electron = require("electron");
//#endregion
//#region src/preload.ts
/** Minimal context-isolated bridge for resolving operating-system drag payloads. */
electron.contextBridge.exposeInMainWorld("__DSH_DESKTOP_FILE_PATH__", { 
/** Resolve only genuine disk-backed Web File objects selected by the operator. */
getPathForFile(file) {
	return electron.webUtils.getPathForFile(file);
} });
//#endregion

//# sourceMappingURL=preload.cjs.ma