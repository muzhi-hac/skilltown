// Room mode in the browser: teachers knock, you let them in one at a time.
//
// The queue is not scripted here. GET /api/v1/town marks each teacher "review"
// (a skill this learner answered wrong) or "recommended" (no evidence yet), and
// the town is refreshed after every lesson, so what you just answered decides
// who knocks next.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as api from "./api";
import type { Attempt, Passport, Recommendation, TaskSummary, Town, TownNpc } from "./api";
import { Room, type VisitorPhase } from "./Room";
import { Lesson, Progress } from "./Lesson";
import "./styles.css";

// Four sprite sheets for four teachers plus the learner, so one sheet is reused
// with a wardrobe shift rather than a hue rotation that would recolour skin.
const SPRITES: Record<string, number> = { Alex: 2, Sam: 3, Mira: 4, Jo: 3 };
const TINTS: Record<string, string | undefined> = {
  Jo: "saturate(0.55) brightness(1.12)",
};
const WALK_MS = 950;

type View = "room" | "lesson" | "progress";

export default function App() {
  const [town, setTown] = useState<Town | null>(null);
  const [queue, setQueue] = useState<string[]>([]);
  const [current, setCurrent] = useState("");
  const [phase, setPhase] = useState<VisitorPhase>("outside");
  const [view, setView] = useState<View>("room");
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [taskTitle, setTaskTitle] = useState("");
  const [headline, setHeadline] = useState("Getting the room ready…");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [screening, setScreening] = useState<TaskSummary | null>(null);
  const [screeningPending, setScreeningPending] = useState(false);
  const [passport, setPassport] = useState<Passport | null>(null);
  const [plan, setPlan] = useState<Recommendation[]>([]);
  const [confirmClear, setConfirmClear] = useState(false);
  const [error, setError] = useState("");
  const firstVisitChecked = useRef(false);

  const npcs: TownNpc[] = town?.npcs ?? [];
  const byName = useMemo(
    () => new Map(npcs.map((npc) => [npc.name, npc])),
    [npcs],
  );

  const npcNameById = useCallback(
    (id: string) => npcs.find((npc) => npc.id === id)?.name ?? id,
    [npcs],
  );
  const taskTitleById = useCallback(
    (scenarioId: string) => {
      for (const npc of npcs) {
        for (const task of npc.tasks) {
          if (task.scenario_id === scenarioId) return task.title;
        }
      }
      return screening?.scenario_id === scenarioId ? screening.title : scenarioId;
    },
    [npcs, screening],
  );

  const orderFrom = (list: TownNpc[]): string[] => {
    const review = list.filter((n) => n.recommendation_state === "review").map((n) => n.name);
    const fresh = list.filter((n) => n.recommendation_state === "recommended").map((n) => n.name);
    const rest = list.filter((n) => n.recommendation_state === "none").map((n) => n.name);
    return [...review, ...fresh, ...rest];
  };

  const refreshTown = useCallback(async () => {
    const next = await api.getTown();
    setTown(next);
    setScreening(next.screening ?? null);
    setQueue(orderFrom(next.npcs));
    return next;
  }, []);

  // Boot: session, town, and whether this guest has any record at all.
  useEffect(() => {
    (async () => {
      try {
        await api.ensureSession();
        const next = await refreshTown();
        if (!firstVisitChecked.current) {
          firstVisitChecked.current = true;
          const record = await api.getPassport();
          const hasEvidence = record.skills.some((skill) => skill.evidence.length > 0);
          setScreeningPending(!hasEvidence && Boolean(next.screening));
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        setHeadline("Could not reach the learning service.");
      }
    })();
  }, [refreshTown]);

  // Announce whoever is at the door whenever the room is idle.
  useEffect(() => {
    if (view !== "room" || phase !== "outside" || !town) return;
    if (screeningPending) {
      setCurrent("Mira");
      setHeadline("Mira is knocking — here for a quick skill check.");
      return;
    }
    if (queue.length === 0) {
      setCurrent("");
      setHeadline("No one is waiting right now.");
      return;
    }
    setCurrent(queue[0]);
    setHeadline(`${queue[0]} is knocking at the door.`);
  }, [view, phase, town, queue, screeningPending]);

  const openDoor = useCallback(async () => {
    if (phase !== "outside" || view !== "room") return;
    if (!current) {
      setHeadline("Asking who is available…");
      await refreshTown().catch(() => undefined);
      return;
    }
    setPhase("entering");
    setHeadline(`${current} is coming in…`);
    window.setTimeout(async () => {
      setPhase("teaching");
      const task = screeningPending
        ? screening
        : (byName.get(current)?.tasks?.[0] ?? null);
      setScreeningPending(false);
      if (!task) {
        setHeadline(`${current} has nothing to teach right now.`);
        setPhase("leaving");
        window.setTimeout(() => setPhase("outside"), WALK_MS);
        return;
      }
      setQueue((rest) => rest.filter((name) => name !== current));
      setTaskTitle(task.title);
      setView("lesson");
      setBusy(true);
      setStatus("Opening the task…");
      try {
        const mode = task.available_modes.includes("practice")
          ? "practice"
          : task.available_modes[0];
        setAttempt(await api.startAttempt(task.scenario_id, mode));
        setHeadline(`In a lesson with ${current}.`);
        setStatus("");
      } catch (err) {
        setStatus(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(false);
      }
    }, WALK_MS);
  }, [phase, view, current, screening, screeningPending, byName, refreshTown]);

  // The door is the only thing to do while someone knocks, so E works too.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (view !== "room") return;
      if (["e", "E", "Enter", " "].includes(event.key)) {
        event.preventDefault();
        void openDoor();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [view, openDoor]);

  const closeLesson = useCallback(async () => {
    if (attempt) void api.recordActivity(attempt.attempt_id, "end");
    setView("room");
    setAttempt(null);
    setTaskTitle("");
    setHeadline(`${current} is heading out.`);
    setPhase("leaving");
    window.setTimeout(async () => {
      setPhase("outside");
      await refreshTown().catch(() => undefined);
    }, WALK_MS);
  }, [attempt, current, refreshTown]);

  const send = useCallback(
    async (text: string) => {
      if (!attempt) return;
      setBusy(true);
      setStatus("Reading your answer…");
      try {
        setAttempt(await api.answer(attempt.attempt_id, attempt.revision, text));
        setStatus("");
      } catch (err) {
        if (err instanceof api.ApiError && err.code === "revision_conflict") {
          setStatus("Progress was out of sync; reloaded the latest state.");
          setAttempt(await api.getAttempt(attempt.attempt_id));
        } else {
          setStatus(err instanceof Error ? err.message : String(err));
        }
      } finally {
        setBusy(false);
      }
    },
    [attempt],
  );

  const hint = useCallback(async () => {
    if (!attempt) return;
    setBusy(true);
    try {
      const result = await api.requestHint(attempt.attempt_id, attempt.revision);
      setAttempt({ ...attempt, revision: result.revision, assisted: true });
      setStatus(`Hint: ${result.hint} (this task is now marked as assisted)`);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [attempt]);

  const doRewind = useCallback(async () => {
    if (!attempt) return;
    setBusy(true);
    try {
      setAttempt(await api.rewind(attempt.attempt_id, attempt.revision));
      setStatus("Back at the decision point.");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [attempt]);

  const openProgress = useCallback(async () => {
    setView("progress");
    setPassport(null);
    try {
      const [record, recommendations] = await Promise.all([
        api.getPassport(),
        api.getRecommendations(3),
      ]);
      setPassport(record);
      setPlan(recommendations.items);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    }
  }, []);

  const startTask = useCallback(
    async (scenarioId: string) => {
      setView("lesson");
      setBusy(true);
      setTaskTitle(taskTitleById(scenarioId));
      try {
        setAttempt(await api.startAttempt(scenarioId, "practice"));
      } catch (err) {
        setStatus(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(false);
      }
    },
    [taskTitleById],
  );

  const clearRecord = useCallback(async () => {
    if (!confirmClear) {
      setConfirmClear(true);
      setHeadline("Clearing deletes every answer in this guest session.");
      window.setTimeout(() => setConfirmClear(false), 5000);
      return;
    }
    setConfirmClear(false);
    try {
      await api.deleteSession();
      firstVisitChecked.current = false;
      setAttempt(null);
      setView("room");
      setPhase("outside");
      setPassport(null);
      setPlan([]);
      await api.createSession();
      const next = await refreshTown();
      setScreeningPending(Boolean(next.screening));
      setHeadline("Record cleared. Fresh guest session started.");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    }
  }, [confirmClear, refreshTown]);

  // Learning time only counts while a lesson is actually open.
  useEffect(() => {
    if (view !== "lesson" || !attempt) return;
    void api.recordActivity(attempt.attempt_id, "start");
    const timer = window.setInterval(
      () => void api.recordActivity(attempt.attempt_id, "heartbeat"),
      15000,
    );
    return () => window.clearInterval(timer);
  }, [view, attempt?.attempt_id]);

  const teacher = byName.get(current);
  const waiting = queue.filter((name) => name !== current);

  return (
    <main className="app">
      <header className="hud">
        <div>
          <h1>{headline}</h1>
          <p className="waiting">
            {waiting.length > 0 ? `Waiting: ${waiting.join(", ")}` : "No one else waiting."}
          </p>
        </div>
        <div className="hud-actions">
          <button className="ghost" onClick={openProgress}>
            My progress
          </button>
          <button className="ghost" onClick={clearRecord}>
            {confirmClear ? "Confirm clearing" : "Clear my record"}
          </button>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      <div className={view === "room" ? "stage" : "split"}>
        <div className="stage">
        <Room
          spriteIndex={SPRITES[current] ?? 2}
          tint={TINTS[current]}
          visitorName={current}
          phase={view === "room" ? phase : "teaching"}
        />
          {view === "room" && phase === "outside" && (
            <div className="door-cta">
              {current && <p className="knock">* knock knock *</p>}
              <button className="door" onClick={openDoor}>
                {current ? "Open the door  (E)" : "Invite the next teacher  (E)"}
              </button>
            </div>
          )}
        </div>

        {view === "lesson" && (
        <Lesson
          teacher={current || "SkillTown"}
          teacherTitle={
            teacher ? `${teacher.title} · ${teacher.category === "ethics_compliance" ? "Ethics & Compliance" : "Personal Development"}` : ""
          }
          taskTitle={taskTitle}
          attempt={attempt}
          busy={busy}
          status={status}
          onAnswer={send}
          onHint={hint}
          onRewind={doRewind}
            onClose={closeLesson}
          />
        )}

        {view === "progress" && (
          <Progress
          passport={passport}
          plan={plan}
          npcNameById={npcNameById}
          taskTitleById={taskTitleById}
          onStart={startTask}
            onClose={() => setView("room")}
          />
        )}
      </div>

      <footer className="disclaimer">
        Every scenario is a fictional training case and the policy is a fictional training policy;
        nothing here is legal advice. Your record belongs to this guest session only.
      </footer>
    </main>
  );
}
