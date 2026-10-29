// The logo for now: a yellow squircle and the name.
import { APP_NAME } from "./api";

export function Mark({ version }: { version?: string }) {
  return (
    <div className="mark">
      <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 0C3 0 0 3 0 12s3 12 12 12 12-3 12-12S21 0 12 0z" fill="#FFD21F" />
      </svg>
      <span className="mark-name">{APP_NAME}</span>
      {version && <span className="ver">{version}</span>}
    </div>
  );
}

