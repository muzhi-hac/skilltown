// The room: four bare walls, a door, and one visitor at a time.
//
// Everything here is presentation. Who knocks, what they teach and what counts
// as learned is decided by the server.

export type VisitorPhase = "outside" | "entering" | "teaching" | "leaving";

export interface RoomProps {
  /** Sprite index 1-4, one per teacher. */
  spriteIndex: number;
  /** Optional CSS filter, for the one sheet that has to serve two people. */
  tint?: string;
  visitorName: string;
  phase: VisitorPhase;
}

const SPRITE_W = 48;
const SPRITE_H = 80;
const SCALE = 2;

function sprite(index: number, walking: boolean, tint?: string) {
  return {
    width: SPRITE_W * SCALE,
    height: SPRITE_H * SCALE,
    backgroundImage: `url(/sprites/char${index}.png)`,
    backgroundSize: `${SPRITE_W * 4 * SCALE}px ${SPRITE_H * SCALE}px`,
    imageRendering: "pixelated" as const,
    animation: walking ? "walk 0.5s steps(4) infinite" : undefined,
    backgroundPosition: walking ? undefined : "0 0",
    // No hue-rotate on people: it turns skin green. Teachers get their own
    // sheet, and the one reused sheet gets a mild wardrobe shift instead.
    filter: tint,
  };
}

export function Room({ spriteIndex, tint, visitorName, phase }: RoomProps) {
  const walking = phase === "entering" || phase === "leaving";
  const visitorStyle: React.CSSProperties = {
    ...sprite(spriteIndex, walking, tint),
    position: "absolute",
    left: "50%",
    marginLeft: 24,
    transition: "top 900ms linear, opacity 250ms linear",
    top: phase === "outside" ? -60 : phase === "teaching" ? 128 : 40,
    opacity: phase === "outside" ? 0 : 1,
    zIndex: 3,
  };

  return (
    <div className="room" aria-label="Your room">
      <div className="room-wall">
        <div className="room-window" />
        <div className="room-door">
          <span className="room-door-knob" />
        </div>
      </div>
      <div className="room-floor">
        <div className="room-table" />
        {/* The learner keeps their own sheet, unfiltered. */}
        <div
          className="learner"
          style={{ ...sprite(1, false), position: "absolute", left: 128, top: 128, zIndex: 2 }}
          aria-label="You"
        />
        <div style={visitorStyle} aria-label={visitorName || "No visitor"}>
          {phase === "teaching" && <span className="visitor-tag">{visitorName}</span>}
        </div>
      </div>
    </div>
  );
}
