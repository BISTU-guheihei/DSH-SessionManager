pimport { i as desktopTrayLabel } from "./tray-locale-CyKag4v-.js";
//#region src/diagnostics.ts
/** Stable Cordis plugin name. */
const name = "desktop-diagnostics";
/** Native adapter required to create diagnostic archives and reveal them. */
const inject = ["desktopRuntime"];
/** Register the diagnostic export command for one Host generation. */
function apply(ctx) {
	ctx.effect(() => {
		const registration = ctx.desktopRuntime.registerTrayItem({
			group: "tools",
			order: 20,
			label: () => desktopTrayLabel(ctx.desktopRuntime.locale, "exportDiagnostics"),
			invoke: () => ctx.desktopRuntime.exportDiagnostics()
		});
		return () => {
			registration.dispose();
		};
	}, "dsh-plugin-desktop: diagnostic export tray command");
}
//#endregion
export { apply, inject, name };

//# sourceMappingURL=diagnostics.js.ma