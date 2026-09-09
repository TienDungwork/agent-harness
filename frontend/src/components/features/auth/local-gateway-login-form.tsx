import React from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { I18nKey } from "#/i18n/declaration";
import CreanovaLogoWhite from "#/assets/branding/Creanova-logo-white.svg?react";
import { localGatewayLogin } from "#/api/local-gateway-admin.api";
import { displayErrorToast } from "#/utils/custom-toast-handlers";

export function LocalGatewayLoginForm() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      await localGatewayLogin(username, password);
      await queryClient.invalidateQueries({ queryKey: ["user"] });
    } catch {
      displayErrorToast(t(I18nKey.AUTH$LOCAL_LOGIN_FAILED));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="flex flex-col items-center w-full gap-8"
      data-testid="local-gateway-login-form"
    >
      <CreanovaLogoWhite width={128} height={32} />
      <p className="text-sm text-gray-400 text-center max-w-sm">
        {t(I18nKey.AUTH$LOCAL_LOGIN_HINT)}
      </p>
      <form
        className="flex flex-col gap-3 items-center"
        onSubmit={handleSubmit}
      >
        <label
          className="flex flex-col gap-1 w-[301.5px]"
          htmlFor="local-username"
        >
          <span className="text-sm text-white">
            {t(I18nKey.AUTH$LOCAL_USERNAME)}
          </span>
          <input
            id="local-username"
            name="username"
            autoComplete="username"
            className="h-10 rounded p-2 bg-[#050505] border border-[#242424] text-white"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
          />
        </label>
        <label
          className="flex flex-col gap-1 w-[301.5px]"
          htmlFor="local-password"
        >
          <span className="text-sm text-white">
            {t(I18nKey.AUTH$LOCAL_PASSWORD)}
          </span>
          <input
            id="local-password"
            name="password"
            type="password"
            autoComplete="current-password"
            className="h-10 rounded p-2 bg-[#050505] border border-[#242424] text-white"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        <button
          type="submit"
          disabled={submitting}
          className="w-[301.5px] h-10 rounded p-2 bg-white text-black text-sm font-medium cursor-pointer hover:opacity-90 disabled:opacity-50"
        >
          {t(I18nKey.AUTH$LOCAL_SIGN_IN)}
        </button>
      </form>
    </div>
  );
}
