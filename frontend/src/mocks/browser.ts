import { setupWorker } from "msw/browser";
import { handlers as wsHandlers } from "./handlers.ws";
import { handlers, prepareMockBrowserDefaults } from "./handlers";

prepareMockBrowserDefaults();

export const worker = setupWorker(...handlers, ...wsHandlers);
