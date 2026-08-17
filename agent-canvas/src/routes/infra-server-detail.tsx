import React from "react";
import { Link, Navigate, useParams } from "react-router";
import { BrandButton } from "#/components/features/settings/brand-button";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import {
  fetchInfraGpu,
  fetchInfraServers,
  fetchInfraServices,
  infraServiceAction,
  type InfraServer,
} from "#/api/infra/client";
import { isLocalAuthEnabled } from "#/api/local-auth/client";
import { useLocalAuthUser } from "#/api/local-auth/hooks";

export default function InfraServerDetailScreen() {
  const { serverId } = useParams();
  const enabled = isLocalAuthEnabled();
  const { data: me, isLoading } = useLocalAuthUser();
  const [server, setServer] = React.useState<InfraServer | null>(null);
  const [gpus, setGpus] = React.useState<Array<Record<string, unknown>>>([]);
  const [gpuReason, setGpuReason] = React.useState<string | null>(null);
  const [services, setServices] = React.useState<
    Array<{
      unit_name: string;
      active_state: string | null;
      sub_state: string | null;
      description: string | null;
    }>
  >([]);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!me || !serverId) return;
    void (async () => {
      try {
        const list = await fetchInfraServers();
        setServer(list.find((s) => s.id === serverId) || null);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, [me, serverId]);

  if (!enabled) return <Navigate to="/" replace />;
  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }
  if (!me?.is_admin) return <Navigate to="/" replace />;

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-4 p-6">
      <Link to="/admin/infra" className="text-xs text-neutral-400 underline">
        ← Servers
      </Link>
      <h1 className="text-xl font-semibold text-white">
        {server?.name || serverId}
      </h1>
      {error ? <p className="text-sm text-red-400">{error}</p> : null}

      <div className="flex gap-2">
        <BrandButton
          type="button"
          variant="primary"
          onClick={async () => {
            if (!serverId) return;
            try {
              const r = await fetchInfraGpu(serverId);
              setGpus(r.gpus);
              setGpuReason(r.reason);
            } catch (err) {
              setError(err instanceof Error ? err.message : String(err));
            }
          }}
        >
          Refresh GPU
        </BrandButton>
        <BrandButton
          type="button"
          variant="secondary"
          onClick={async () => {
            if (!serverId) return;
            try {
              const r = await fetchInfraServices(serverId);
              setServices(r.services);
            } catch (err) {
              setError(err instanceof Error ? err.message : String(err));
            }
          }}
        >
          List services
        </BrandButton>
      </div>

      <section>
        <h2 className="mb-2 text-sm font-medium text-neutral-300">GPU</h2>
        {gpuReason ? (
          <p className="text-xs text-neutral-500">{gpuReason}</p>
        ) : null}
        <pre className="overflow-auto rounded border border-neutral-800 bg-neutral-950 p-2 text-xs text-neutral-200">
          {JSON.stringify(gpus, null, 2)}
        </pre>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-medium text-neutral-300">Services</h2>
        <ul className="divide-y divide-neutral-800 rounded border border-neutral-800 text-sm">
          {services.slice(0, 40).map((s) => (
            <li
              key={s.unit_name}
              className="flex items-center justify-between gap-2 px-3 py-1.5"
            >
              <span>
                {s.unit_name}{" "}
                <span className="text-neutral-500">
                  {s.active_state}/{s.sub_state}
                </span>
              </span>
              <BrandButton
                type="button"
                variant="secondary"
                onClick={async () => {
                  if (!serverId) return;
                  try {
                    await infraServiceAction(serverId, s.unit_name, "restart");
                  } catch (err) {
                    setError(err instanceof Error ? err.message : String(err));
                  }
                }}
              >
                Restart
              </BrandButton>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
