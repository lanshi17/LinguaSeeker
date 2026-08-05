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

  it("extracts the message from the structured backend error envelope", () => {
    const backendError = new AxiosError(
      "Request failed with status code 400",
      "ERR_BAD_REQUEST",
      undefined,
      undefined,
      {
        data: {
          error: {
            code: "BAD_REQUEST",
            message: "No matching nodes found for the provided entities",
          },
          request_id: "test-request-id",
        },
        status: 400,
        statusText: "Bad Request",
        headers: {},
        config: {},
      } as never,
    );

    const normalized = normalizeError(backendError);

    expect(normalized).toMatchObject({
      status: 400,
      backendMessage: "No matching nodes found for the provided entities",
    });
    expect(normalized.message).toBe(
      "Request failed: No matching nodes found for the provided entities",
    );
  });
});
