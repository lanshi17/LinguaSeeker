import { describe, expect, it } from "vitest";
import {
  APP_TIME_ZONE,
  formatAppIsoTimestamp,
  formatFilenameTimestamp,
  formatTime,
} from "../../src/lib/utils/format";

describe("frontend time formatting", () => {
  it("formats UTC backend timestamps in the configured app time zone", () => {
    const timestamp = "2026-07-08T16:30:45Z";

    expect(APP_TIME_ZONE).toBe("Asia/Shanghai");
    expect(formatTime(timestamp, "en-GB")).toBe("00:30:45");
    expect(formatAppIsoTimestamp(timestamp)).toBe("2026-07-09T00:30:45+08:00");
    expect(formatFilenameTimestamp(timestamp)).toBe("2026-07-09_00-30-45");
  });
});
