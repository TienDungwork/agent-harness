import { Creanova } from "../open-hands-axios";
import { AuthenticateResponse, GitHubAccessTokenResponse } from "./auth.types";
import { WebClientConfig } from "../option-service/option.types";
import { isLocalGatewayAdmin } from "#/utils/local-gateway-admin";
import { localGatewayLogout } from "../local-gateway-admin.api";

/**
 * Authentication service for handling all authentication-related API calls
 */
class AuthService {
  /**
   * Authenticate with GitHub token
   * @param appMode The application mode (saas or oss)
   * @returns Response with authentication status and user info if successful
   */
  static async authenticate(
    appMode: WebClientConfig["app_mode"],
  ): Promise<boolean> {
    if (isLocalGatewayAdmin()) {
      await Creanova.get("/api/auth/me");
      return true;
    }
    if (appMode === "oss") return true;

    // Just make the request, if it succeeds (no exception thrown), return true
    await Creanova.post<AuthenticateResponse>("/api/authenticate");
    return true;
  }

  /**
   * Get GitHub access token from Keycloak callback
   * @param code Code provided by GitHub
   * @returns GitHub access token
   */
  static async getGitHubAccessToken(
    code: string,
  ): Promise<GitHubAccessTokenResponse> {
    const { data } = await Creanova.post<GitHubAccessTokenResponse>(
      "/api/keycloak/callback",
      {
        code,
      },
    );
    return data;
  }

  /**
   * Logout user from the application
   * @param appMode The application mode (saas or oss)
   */
  static async logout(appMode: WebClientConfig["app_mode"]): Promise<void> {
    if (isLocalGatewayAdmin()) {
      await localGatewayLogout();
      return;
    }
    const endpoint =
      appMode === "saas" ? "/api/logout" : "/api/unset-provider-tokens";
    await Creanova.post(endpoint);
  }
}

export default AuthService;
