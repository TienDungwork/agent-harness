import { Creanova } from "../open-hands-axios";
import { Settings, SettingsSchema } from "#/types/settings";
import { isLocalGatewayAdmin } from "#/utils/local-gateway-admin";

/**
 * Settings service for managing application settings
 */
class SettingsService {
  /**
   * Get the settings from the server or use the default settings if not found
   */
  static async getSettings(): Promise<Settings> {
    const path = isLocalGatewayAdmin() ? "/api/settings" : "/api/v1/settings";
    const { data } = await Creanova.get<Settings>(path);
    return data;
  }

  /**
   * Get the AgentSettings schema used to render schema-driven settings pages.
   */
  static async getSettingsSchema(): Promise<SettingsSchema> {
    const path = isLocalGatewayAdmin()
      ? "/api/settings/agent-schema"
      : "/api/v1/settings/agent-schema";
    const { data } = await Creanova.get<SettingsSchema>(path);
    return data;
  }

  static async getConversationSettingsSchema(): Promise<SettingsSchema> {
    const path = isLocalGatewayAdmin()
      ? "/api/settings/conversation-schema"
      : "/api/v1/settings/conversation-schema";
    const { data } = await Creanova.get<SettingsSchema>(path);
    return data;
  }

  /**
   * Save the settings to the server. Only valid settings are saved.
   * @param settings - the settings to save
   */
  static async saveSettings(
    settings: Partial<Settings> & Record<string, unknown>,
  ): Promise<boolean> {
    if (isLocalGatewayAdmin()) {
      const response = await Creanova.patch("/api/settings", settings);
      return response.status === 200;
    }
    const response = await Creanova.post("/api/v1/settings", settings);
    return response.status === 200;
  }
}

export default SettingsService;
