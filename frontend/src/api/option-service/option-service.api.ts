import { Creanova } from "../open-hands-axios";
import { ModelsResponse, WebClientConfig } from "./option.types";
import {
  isLocalGatewayAdmin,
  LOCAL_GATEWAY_WEB_CLIENT_CONFIG,
} from "#/utils/local-gateway-admin";

/**
 * Service for handling API options endpoints
 */
class OptionService {
  /**
   * Retrieve the structured models response from the backend.
   *
   * The backend is the single source of truth for verified models,
   * verified providers, and provider assignment for bare model names.
   */
  static async getModels(): Promise<ModelsResponse> {
    const { data } = await Creanova.get<ModelsResponse>("/api/options/models");
    return data;
  }

  /**
   * Retrieve the list of security analyzers available
   * @returns List of security analyzers available
   */
  static async getSecurityAnalyzers(): Promise<string[]> {
    const { data } = await Creanova.get<string[]>(
      "/api/options/security-analyzers",
    );
    return data;
  }

  /**
   * Get the web client configuration from the server
   * @returns Web client configuration response
   */
  static async getConfig(): Promise<WebClientConfig> {
    if (isLocalGatewayAdmin()) {
      return {
        ...LOCAL_GATEWAY_WEB_CLIENT_CONFIG,
        updated_at: new Date().toISOString(),
      };
    }
    const { data } = await Creanova.get<WebClientConfig>(
      "/api/v1/web-client/config",
    );
    return data;
  }
}

export default OptionService;
