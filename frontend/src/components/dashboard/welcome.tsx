import {
  Activity,
  CheckCheck,
  ChevronRight,
  FlaskConical,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Upload } from "../datasets/upload";
export function Welcome({
  onLoad,
  busy,
  progress,
  maxSize,
}: {
  onLoad: (source: File | "plants" | "environment") => void;
  busy: boolean;
  progress: number;
  maxSize: number;
}) {
  return (
    <>
      <div className="welcome-banner">
        <div className="welcome-orbit">
          <FlaskConical size={26} />
        </div>
        <div>
          <span className="eyebrow">
            A LITTLE DATA. A WORLD OF POSSIBILITIES.
          </span>
          <h2>Make room for your next insight.</h2>
          <p>
            Explore scientific data with thoughtful visualizations
            <br className="desktop-break" /> and an AI assistant that does the
            math with you.
          </p>
        </div>
        <div className="banner-spark">
          <Sparkles size={40} strokeWidth={1} />
        </div>
      </div>
      <div className="empty-steps">
        <span>
          <b>01</b> Import your dataset
        </span>
        <ChevronRight size={14} />
        <span>
          <b>02</b> Explore the patterns
        </span>
        <ChevronRight size={14} />
        <span>
          <b>03</b> Ask better questions
        </span>
      </div>
      <Upload
        onFile={onLoad}
        onSample={onLoad}
        busy={busy}
        progress={progress}
        maxSize={maxSize}
      />
      <div className="trust-strip">
        <span>
          <ShieldCheck size={16} />
          Local AI. No paid APIs.
        </span>
        <span>
          <CheckCheck size={16} />
          Verified calculations
        </span>
        <span>
          <Activity size={16} />
          Built for scientific curiosity
        </span>
      </div>
    </>
  );
}
