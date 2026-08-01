import { AxiosError } from "axios";
import { describe, expect, it } from "vitest";

import { normalizeError } from "@/lib/api/error";

describe("normalizeError", () => {
  it.each(["ECONNABORTED", "ETIMEDOUT"])(
    "reports Axios timeout code %s separately from a generic network failure",
    (timeoutCode) => {
      const timeoutError = new AxiosError(
        "timeout of 60000ms exceeded",
        timeoutCode,
      );
      const networkError = new AxiosError("Network Error");

      const normalizedTimeout = normalizeError(timeoutError);
      const normalizedNetwork = normalizeError(networkError);

      expect(normalizedTimeout).toMatchObject({
        status: 0,
        message: "Request timed out — please try again.",
        backendMessage: "Request timed out — please try again.",
      });
      expect(normalizedNetwork).toMatchObject({
        status: 0,
        message: "Network error — please check your connection.",
      });
      expect(normalizedTimeout.message).not.toBe(normalizedNetwork.message);
    },
  );
});
