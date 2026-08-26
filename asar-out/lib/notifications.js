
import z from "@deepseek-ai/schemastery";
import { settingsNamespace } from "@deepseek-ai/dsh-settings";
//#region src/notifications.ts
const name = "desktop-notifications";
const inject = ["desktopRuntime"];
const DESKTOP_NOTIFICATIONS_SETTINGS_NAMESPACE = settingsNamespace("dsh-desktop-notifications");
const DesktopNotificationSettingsSchema = z.object({
	enabled: z.boolean().default(true),
	notifyOnTurnCompletion: z.boolean().default(true),
	notifyOnTurnFailure: z.boolean().default(true),
	notifyOnJobCompletion: z.boolean().default(true),
	notifyOnJobFailure: z.boolean().default(true)
});
const DEFAULT_SETTINGS = DesktopNotificationSettingsSchema({});
const NOTIFICATION_COPY = {
	en: {
		"turn-completed": {
			title: "User Turn Completed",
			body: "A user-initiated turn has finished."
		},
		"turn-failed": {
			title: "User Turn Failed",
			body: "A user-initiated turn could not finish. Open DSH Desktop for details."
		},
		"job-completed": {
			title: "Background Job Completed",
			body: "A background job has finished."
		},
		"job-failed": {
			title: "Background Job Failed",
			body: "A background job could not finish. Open DSH Desktop for details."
		}
	},
	zh: {
		"turn-completed": {
			title: "用户回合已完成",
			body: "一个由你发起的回合已完成。"
		},
		"turn-failed": {
			title: "用户回合失败",
			body: "一个由你发起的回合未能完成，请打开 DSH Desktop 查看详情。"
		},
		"job-completed": {
			title: "后台任务已完成",
			body: "有一个后台任务已结束。"
		},
		"job-failed": {
			title: "后台任务失败",
			body: "一个后台任务未能完成，请打开 DSH Desktop 查看详情。"
		}
	}
};
function notifyJob(runtime, settings, snapshot) {
	if (!settings.enabled) return;
	if (snapshot.status === "completed" && settings.notifyOnJobCompletion) runtime.notifyAttention(NOTIFICATION_COPY[runtime.locale]["job-completed"]);
	else if (snapshot.status === "failed" && settings.notifyOnJobFailure) runtime.notifyAttention(NOTIFICATION_COPY[runtime.locale]["job-failed"]);
}
function trackTurn(runtime, settings, openTurns, session, event) {
	if (!settings.enabled) return;
	if (session.header.origin === "subagent") return;
	const sessionId = String(session.header.id);
	if (event.type === "turn/start") {
		openTurns.set(sessionId, {
			turn: event.data.turn,
			userInitiated: false
		});
		return;
	}
	if (event.type === "user/message") {
		const openTurn = openTurns.get(sessionId);
		if (openTurn !== void 0 && event.data.source.kind === "user") openTurn.userInitiated = true;
		return;
	}
	if (event.type !== "turn/end") return;
	const openTurn = openTurns.get(sessionId);
	if (openTurn === void 0 || openTurn.turn !== event.data.turn) return;
	openTurns.delete(sessionId);
	if (!openTurn.userInitiated) return;
	const reason = event.data.reason.kind;
	if (reason === "completed" && settings.notifyOnTurnCompletion) runtime.notifyAttention(NOTIFICATION_COPY[runtime.locale]["turn-completed"]);
	else if ((reason === "error" || reason === "max-tokens") && settings.notifyOnTurnFailure) runtime.notifyAttention(NOTIFICATION_COPY[runtime.locale]["turn-failed"]);
}
/** Register independently optional settings, job, and live-session observers. */
function apply(ctx) {
	let settings = DEFAULT_SETTINGS;
	ctx.inject(["settings"], (settingsCtx) => {
		settingsCtx.effect(() => {
			const scope = settingsCtx.settings.register(DESKTOP_NOTIFICATIONS_SETTINGS_NAMESPACE, DesktopNotificationSettingsSchema, { applies: "live" });
			settings = scope.get();
			const stopWatching = scope.watch((next) => {
				settings = next;
			});
			return () => {
				stopWatching();
				settings = DEFAULT_SETTINGS;
			};
		}, "dsh-plugin-desktop: native notification settings");
	});
	ctx.inject(["jobs"], (jobsCtx) => {
		jobsCtx.effect(() => jobsCtx.jobs.onJobDone((snapshot) => {
			notifyJob(jobsCtx.desktopRuntime, settings, snapshot);
		}), "dsh-plugin-desktop: background job attention");
	});
	ctx.inject(["sessions"], (sessionsCtx) => {
		sessionsCtx.effect(() => {
			const openTurns = /* @__PURE__ */ new Map();
			const stopEvents = sessionsCtx.on("session/event", (session, event) => {
				trackTurn(sessionsCtx.desktopRuntime, settings, openTurns, session, event);
			});
			const stopDisposed = sessionsCtx.on("session/disposed", (session) => {
				openTurns.delete(String(session.header.id));
			});
			return () => {
				stopDisposed();
				stopEvents();
			};
		}, "dsh-plugin-desktop: direct user turn attention");
	});
}
//#endregion
export { DESKTOP_NOTIFICATIONS_SETTINGS_NAMESPACE, DesktopNotificationSettingsSchema, apply, inject, name };

//# sourceMappingURL=notifications.js.ma