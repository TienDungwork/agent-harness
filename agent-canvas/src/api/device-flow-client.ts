import {
  pollForToken as sdkPollForToken,
  startDeviceFlow as sdkStartDeviceFlow,
  isOpenHandsCloudHost,
} from "@Creanova/typescript-client/client/device-flow-client";
import type {
  DeviceAuthorizationResponse,
  DeviceTokenResponse,
  PollDeviceTokenOptions,
} from "@Creanova/typescript-client/client/device-flow-client";
import { AGENT_CANVAS_CLIENT_HEADERS } from "./client-source";

export { DeviceFlowError } from "@Creanova/typescript-client/client/device-flow-client";

/** Creanova-branded alias of the upstream cloud-host detector. */
export const isCreanovaCloudHost = isOpenHandsCloudHost;

export function startDeviceFlow(
  host: string,
): Promise<DeviceAuthorizationResponse> {
  return sdkStartDeviceFlow(host, { headers: AGENT_CANVAS_CLIENT_HEADERS });
}

export function pollForToken(
  host: string,
  deviceCode: string,
  options: PollDeviceTokenOptions,
): Promise<DeviceTokenResponse> {
  return sdkPollForToken(host, deviceCode, {
    ...options,
    headers: AGENT_CANVAS_CLIENT_HEADERS,
  });
}

export type {
  DeviceAuthorizationResponse,
  DeviceTokenResponse,
  PollDeviceTokenOptions as PollOptions,
} from "@Creanova/typescript-client/client/device-flow-client";
