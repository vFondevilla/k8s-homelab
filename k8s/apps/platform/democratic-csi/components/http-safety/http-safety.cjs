"use strict";

// Temporary compatibility patch for democratic-csi v1.9.5. Apply before the
// driver loads. Keep credentials out of probe errors, gRPC replies and logs.
const { Client } = require("/home/csi/app/src/driver/freenas/http");

const commonOptions = Client.prototype.getRequestCommonOptions;
Client.prototype.getRequestCommonOptions = function () {
  if (this.options.protocol !== "https") {
    throw new Error("TrueNAS API requires HTTPS; no request was sent");
  }
  return commonOptions.call(this);
};

// Never log request options, response bodies, headers or Axios error objects.
Client.prototype.log_repsonse = function (_error, response, _body, options) {
  const status = Number(response?.statusCode) || 0;
  const duration = Number(response?.duration) || 0;
  this.logger.debug(
    `TrueNAS HTTP ${options.method}: status=${status} duration_ms=${duration}`
  );
};

for (const method of ["get", "post", "put", "delete"]) {
  const request = Client.prototype[method];
  Client.prototype[method] = async function (...args) {
    try {
      const response = await request.apply(this, args);
      const statusCode = Number(response.statusCode);
      // Axios responses include config.headers and request._header. Neither
      // belongs in a CSI response. Successful bodies remain unchanged.
      return {
        statusCode,
        body: statusCode >= 200 && statusCode < 300
          ? response.body
          : `TrueNAS HTTP request failed (status ${statusCode})`,
      };
    } catch (error) {
      // Do not retain the cause: it can contain the request and API key.
      const status = Number(error.response?.statusCode || error.response?.status);
      const code = ["ECONNREFUSED", "ECONNRESET", "ETIMEDOUT", "ECONNABORTED",
        "ENOTFOUND", "EHOSTUNREACH", "UNABLE_TO_VERIFY_LEAF_SIGNATURE",
        "CERT_HAS_EXPIRED", "DEPTH_ZERO_SELF_SIGNED_CERT"].includes(error.code)
        ? error.code : "REQUEST_FAILED";
      throw new Error(Number.isInteger(status) && status >= 100 && status <= 599
        ? `TrueNAS HTTP request failed (status ${status})`
        : `TrueNAS HTTP request failed (${code}); check HTTPS and API access`);
    }
  };
}
